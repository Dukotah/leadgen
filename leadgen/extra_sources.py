"""
Extra no-key data sources — supplementary collectors that complement
leadgen.sources without touching it.

All collectors return the same normalized lead-dict shape as sources.py so the
rest of the pipeline stays source-agnostic:
  {name, category, website, phone, email, address, city, state, zip,
   lat, lon, brand, source, source_url}

Every function FAILS SOFT: any network/parse error returns [] (never raises)
and progress is reported through a `log=print` callback.

Collectors:
  - localfile_collect(): read a local .csv / .xlsx of businesses, map columns.
  - url_csv_collect():    fetch a public CSV by URL, map columns.
  - wikidata_collect():   Wikidata SPARQL items with coords + official website.
  - ckan_collect():       best-effort data.gov CKAN business-license datasets.
"""
from __future__ import annotations

import csv
import io

import requests

from .audit import UA
# Reuse the column-alias heuristic and dict-unwrapping field reader from sources.
from .sources import _first_field, _socrata_map_row

__all__ = [
    "localfile_collect", "url_csv_collect", "wikidata_collect", "ckan_collect",
    "map_business_rows",
]


# ─────────────────── reusable pure column mapper ─────────────────────────────
def map_business_rows(rows, source: str, source_url: str = "",
                      limit: int | None = None) -> list[dict]:
    """Map an iterable of dict rows to normalized lead dicts (no network).

    Reuses sources._socrata_map_row's alias-based column heuristic, then stamps
    the given source/source_url. Nameless rows are dropped. Pure + bounded.
    """
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rec = _socrata_map_row(row)
        if not rec:
            continue
        rec["source"] = source
        rec["category"] = rec.get("category") or "business"
        rec["source_url"] = source_url
        out.append(rec)
        if limit and len(out) >= limit:
            break
    return out


# ─────────────────── local file (.csv / .xlsx) ──────────────────────────────
def _read_csv_text(text: str):
    """Yield dict rows from CSV text (no network). [] on any parse error."""
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except Exception:
        return []


def _read_xlsx_rows(path: str):
    """Yield dict rows from the first sheet of an .xlsx via openpyxl."""
    try:
        import openpyxl
    except ImportError:
        return []
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            wb.close()
            return []
        header = [("" if h is None else str(h)).strip() for h in header]
        out = []
        for r in rows:
            rec = {}
            for i, val in enumerate(r):
                if i < len(header) and header[i]:
                    rec[header[i]] = "" if val is None else val
            if any(v not in ("", None) for v in rec.values()):
                out.append(rec)
        wb.close()
        return out
    except Exception:
        return []


def localfile_collect(path, limit=None, log=print) -> list[dict]:
    """Read a local .csv or .xlsx of businesses; map columns heuristically.

    Column mapping reuses the same alias idea as sources._socrata_map_row, so a
    file with e.g. business_name / phone / city columns maps cleanly. Fails soft.
    """
    p = str(path or "")
    low = p.lower()
    try:
        if low.endswith(".xlsx") or low.endswith(".xlsm"):
            rows = _read_xlsx_rows(p)
        elif low.endswith(".csv") or low.endswith(".tsv") or low.endswith(".txt"):
            with open(p, "r", encoding="utf-8-sig", newline="") as fh:
                rows = _read_csv_text(fh.read())
        else:
            log(f"  localfile: unsupported file type ({p}); want .csv/.xlsx")
            return []
    except FileNotFoundError:
        log(f"  localfile: file not found ({p})")
        return []
    except Exception as e:
        log(f"  localfile read failed ({p}): {type(e).__name__}: {e}")
        return []
    out = map_business_rows(rows, source="localfile", source_url=p, limit=limit)
    log(f"  localfile: {len(out)} businesses from {p}")
    return out


# ─────────────────── public CSV by URL ──────────────────────────────────────
def url_csv_collect(url, limit=None, log=print) -> list[dict]:
    """Fetch a public CSV by URL, parse with csv.DictReader, map columns. Soft."""
    if not url:
        return []
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        if r.status_code != 200:
            log(f"  url_csv: HTTP {r.status_code} for {url}")
            return []
        rows = _read_csv_text(r.text)
    except Exception as e:
        log(f"  url_csv read failed ({url}): {type(e).__name__}: {e}")
        return []
    out = map_business_rows(rows, source="url_csv", source_url=str(url), limit=limit)
    log(f"  url_csv: {len(out)} businesses from {url}")
    return out


# ─────────────────── Wikidata SPARQL (no key) ───────────────────────────────
# Wikidata items with a coordinate location (P625) inside the bbox that also
# carry an official website (P856). Bounded by LIMIT, fails soft.
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


def _wikidata_query(bbox, limit: int) -> str:
    """Build the SPARQL query body (no network). bbox = (south, west, north, east)."""
    south, west, north, east = bbox
    # Wikidata's wikibase:box wants SW corner then NE corner as Point(lon lat).
    return f"""
SELECT ?item ?itemLabel ?website ?coord WHERE {{
  SERVICE wikibase:box {{
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point({west} {south})"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point({east} {north})"^^geo:wktLiteral .
  }}
  ?item wdt:P856 ?website .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {int(limit)}
""".strip()


def _parse_wkt_point(wkt: str):
    """'Point(lon lat)' -> (lat, lon) floats, or (None, None)."""
    try:
        inner = wkt[wkt.index("(") + 1:wkt.index(")")]
        lon_s, lat_s = inner.split()
        return float(lat_s), float(lon_s)
    except Exception:
        return None, None


def wikidata_collect(bbox, limit=None, log=print) -> list[dict]:
    """Wikidata items with coords inside bbox AND an official website. Soft."""
    try:
        south, west, north, east = bbox
    except Exception:
        log("  wikidata: bad bbox; skipping.")
        return []
    cap = min(500, int(limit) if limit else 200)
    query = _wikidata_query((south, west, north, east), cap)
    try:
        r = requests.get(WIKIDATA_SPARQL, params={"query": query, "format": "json"},
                         headers={"User-Agent": UA, "Accept": "application/sparql-results+json"},
                         timeout=40)
        if r.status_code != 200:
            log(f"  wikidata: HTTP {r.status_code}")
            return []
        bindings = r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        log(f"  wikidata query failed: {type(e).__name__}: {e}")
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for b in bindings:
        name = (b.get("itemLabel", {}) or {}).get("value", "").strip()
        item_uri = (b.get("item", {}) or {}).get("value", "")
        if not name or name.startswith("Q") and name == item_uri.rsplit("/", 1)[-1]:
            continue  # unlabeled item (label fell back to the Q-id)
        key = item_uri or name.lower()
        if key in seen:
            continue
        seen.add(key)
        lat, lon = _parse_wkt_point((b.get("coord", {}) or {}).get("value", ""))
        out.append({
            "name": name,
            "category": "",
            "website": (b.get("website", {}) or {}).get("value") or None,
            "phone": None,
            "email": None,
            "address": "",
            "city": "",
            "state": "",
            "zip": "",
            "brand": "",
            "lat": lat, "lon": lon,
            "source": "wikidata",
            "source_url": item_uri,
        })
        if limit and len(out) >= limit:
            break
    log(f"  wikidata: {len(out)} items with a website")
    return out


# ─────────────────── data.gov CKAN (no key, best-effort) ─────────────────────
# data.gov's CKAN action API indexes thousands of government datasets. We search
# for "<place> business license" datasets and, for a couple that expose a CSV /
# datastore resource, pull a few rows and map columns. Supplementary; fails soft.
CKAN_BASE = "https://catalog.data.gov/api/3"


def _ckan_resource_rows(resource: dict, log) -> list[dict]:
    """Pull a few rows from one CKAN resource (datastore API, else raw CSV). Soft."""
    rid = resource.get("id", "")
    fmt = (resource.get("format", "") or "").lower()
    # 1) datastore_search (structured) if the resource is datastore-active.
    if rid and resource.get("datastore_active"):
        try:
            r = requests.get(f"{CKAN_BASE}/action/datastore_search",
                             params={"resource_id": rid, "limit": 50},
                             headers={"User-Agent": UA}, timeout=25)
            if r.status_code == 200:
                recs = r.json().get("result", {}).get("records", [])
                if recs:
                    return [x for x in recs if isinstance(x, dict)]
        except Exception as e:
            log(f"    ckan datastore failed ({rid}): {type(e).__name__}")
    # 2) fall back to fetching the raw CSV url.
    url = resource.get("url", "")
    if url and ("csv" in fmt or url.lower().endswith(".csv")):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
            if r.status_code == 200:
                return _read_csv_text(r.text)[:50]
        except Exception as e:
            log(f"    ckan csv failed ({url}): {type(e).__name__}")
    return []


def ckan_collect(place_label, limit=None, log=print) -> list[dict]:
    """Best-effort data.gov CKAN search for '<place> business license'. Soft."""
    place = str(place_label or "").replace("_", " ").split(",")[0].strip()
    if not place:
        log("  ckan: no place label; skipping.")
        return []
    try:
        r = requests.get(f"{CKAN_BASE}/action/package_search",
                         params={"q": f"{place} business license", "rows": 10},
                         headers={"User-Agent": UA}, timeout=25)
        if r.status_code != 200:
            log(f"  ckan: HTTP {r.status_code}")
            return []
        packages = r.json().get("result", {}).get("results", [])
    except Exception as e:
        log(f"  ckan search failed: {type(e).__name__}: {e}")
        return []

    out: list[dict] = []
    pulled = 0
    for pkg in packages:
        if pulled >= 2:                       # only a couple of datasets
            break
        resources = pkg.get("resources", []) or []
        # prefer datastore-active / CSV resources
        resources = sorted(
            resources,
            key=lambda res: 0 if (res.get("datastore_active")
                                  or "csv" in (res.get("format", "") or "").lower())
            else 1,
        )
        for res in resources[:2]:
            rows = _ckan_resource_rows(res, log)
            if not rows:
                continue
            src_url = pkg.get("name") and f"https://catalog.data.gov/dataset/{pkg['name']}" or ""
            mapped = map_business_rows(rows, source="ckan", source_url=src_url,
                                       limit=(limit - len(out)) if limit else None)
            out.extend(mapped)
            log(f"    {pkg.get('title') or pkg.get('name') or '?'}: {len(mapped)} records")
            pulled += 1
            break
        if limit and len(out) >= limit:
            break
    log(f"  ckan: {len(out)} businesses for '{place}'")
    return out[:limit] if limit else out
