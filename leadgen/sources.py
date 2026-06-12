"""
Data sources — collect the raw business universe for a bbox.

Two free, no-key sources, both already proven in this repo:
  - overture_collect(): Overture Maps Places via DuckDuckDB+S3 (national, CC-BY)
  - osm_collect():      OpenStreetMap via Overpass (live, ODbL)

Both return a list of normalized lead dicts with the same shape so the rest of
the pipeline is source-agnostic:
  {name, category, website, phone, email, address, city, state, zip,
   lat, lon, brand, source, source_url}
"""
from __future__ import annotations

import time

import requests

from .audit import UA

# ───────────────────────── Overture (bulk, national) ─────────────────────────
FALLBACK_RELEASE = "2026-05-20.0"


def _overture_release(con) -> str:
    try:
        pat = ("s3://overturemaps-us-west-2/release/202[0-9]-*"
               "/theme=places/type=place/part-00000-*")
        rows = con.execute(
            "SELECT DISTINCT regexp_extract(file, 'release/([^/]+)/', 1) AS rel "
            f"FROM glob('{pat}') WHERE rel <> '' ORDER BY rel DESC LIMIT 1"
        ).fetchall()
        if rows and rows[0][0]:
            return rows[0][0]
    except Exception:
        pass
    return FALLBACK_RELEASE


def overture_collect(bbox, categories: list[str] | None = None,
                     limit: int | None = None, log=print) -> list[dict]:
    """Stream Overture Places for a bbox, optionally filtered to category substrings."""
    try:
        import duckdb
    except ImportError:
        raise RuntimeError("overture_collect needs duckdb: pip install duckdb")

    south, west, north, east = bbox
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    release = _overture_release(con)
    log(f"  Overture release {release}; streaming bbox…")
    s3 = (f"s3://overturemaps-us-west-2/release/{release}"
          f"/theme=places/type=place/*")

    cat_clause = ""
    if categories:
        ors = " OR ".join("lower(categories.primary) LIKE ?" for _ in categories)
        cat_clause = f"AND ({ors})"
    params = [f"%{c.lower()}%" for c in (categories or [])]

    sql = f"""
      SELECT names.primary AS name,
             categories.primary AS category,
             CASE WHEN length(websites)>0 THEN websites[1] END AS website,
             CASE WHEN length(phones)>0   THEN phones[1]   END AS phone,
             CASE WHEN length(emails)>0   THEN emails[1]   END AS email,
             addresses[1].freeform AS address,
             addresses[1].locality AS city,
             addresses[1].region   AS state,
             addresses[1].postcode AS zip,
             brand.names.primary AS brand,
             bbox.xmin AS lon, bbox.ymin AS lat
      FROM read_parquet('{s3}', hive_partitioning=1)
      WHERE bbox.xmin BETWEEN {west} AND {east}
        AND bbox.ymin BETWEEN {south} AND {north}
        AND names.primary IS NOT NULL
        {cat_clause}
      {f'LIMIT {int(limit)}' if limit else ''}
    """
    cols = ["name", "category", "website", "phone", "email", "address",
            "city", "state", "zip", "brand", "lon", "lat"]
    rows = con.execute(sql, params).fetchall()
    out = []
    for r in rows:
        rec = dict(zip(cols, r))
        rec["source"] = "overture"
        rec["source_url"] = ""
        out.append(rec)
    log(f"  Overture: {len(out)} businesses")
    return out


# ───────────────────────── OSM / Overpass (live) ─────────────────────────────
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
RETRY_STATUS = {429, 502, 503, 504}


def _overpass_body(bbox, tag_filters: list[str], timeout: int = 60) -> str:
    """Build the Overpass QL query body (no network). '' if no usable filters."""
    south, west, north, east = bbox
    bb = f"({south},{west},{north},{east})"
    parts = []
    for tf in tag_filters:
        if "=" in tf:
            k, v = tf.split("=", 1)
            parts.append(f'nwr["{k}"="{v}"]{bb};')
        else:
            # Key-only filter (e.g. "shop", "craft", "office"): match ANY value of
            # that key, but require a name so we get businesses, not unnamed nodes.
            parts.append(f'nwr["{tf}"]["name"]{bb};')
    if not parts:
        return ""
    return (f"[out:json][timeout:{timeout}];\n(\n  " + "\n  ".join(parts)
            + "\n);\nout center tags;")


def _overpass_query(bbox, tag_filters: list[str], timeout: int = 60) -> list[dict]:
    body = _overpass_body(bbox, tag_filters, timeout)
    if not body:
        return []
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                r = requests.post(endpoint, data=body, headers={"User-Agent": UA},
                                  timeout=timeout + 10)
                if r.status_code == 200:
                    return r.json().get("elements", [])
                errors.append(f"HTTP {r.status_code}")
                if r.status_code in RETRY_STATUS and attempt == 0:
                    time.sleep(2); continue
                break
            except requests.exceptions.RequestException as e:
                errors.append(type(e).__name__)
                if attempt == 0:
                    time.sleep(2); continue
                break
    raise RuntimeError("All Overpass mirrors failed (" + "; ".join(errors) + ")")


def osm_collect(bbox, osm_tags: list[str], log=print) -> list[dict]:
    """Query Overpass for the given OSM tags within bbox; normalize to lead dicts."""
    els = _overpass_query(bbox, osm_tags)
    out = []
    for el in els:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("operator")
        if not name:
            continue
        line1 = " ".join(tags.get(k, "") for k in ("addr:housenumber", "addr:street")).strip()
        category = (tags.get("shop") or tags.get("craft") or tags.get("office")
                    or tags.get("amenity") or tags.get("tourism") or "")
        out.append({
            "name": name.strip(),
            "category": category,
            "website": (tags.get("website") or tags.get("contact:website") or "").strip(),
            "phone": (tags.get("phone") or tags.get("contact:phone") or "").strip(),
            "email": (tags.get("email") or tags.get("contact:email") or "").strip(),
            "address": ", ".join(p for p in [line1, tags.get("addr:city", "")] if p),
            "city": tags.get("addr:city", ""),
            "state": tags.get("addr:state", ""),
            "zip": tags.get("addr:postcode", ""),
            "brand": tags.get("brand", ""),
            "lat": el.get("lat") or (el.get("center") or {}).get("lat"),
            "lon": el.get("lon") or (el.get("center") or {}).get("lon"),
            "source": "osm",
            "source_url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        })
    log(f"  OSM: {len(out)} named businesses")
    return out


# ─────────────────── Socrata open data (no key) ──────────────────────────────
# Many US cities/counties publish business-license / -registration data on
# Socrata portals. The Discovery API (no key) finds datasets; SODA reads them.
# Coverage is per-jurisdiction and patchy, but it surfaces a kind of lead the maps
# can't: brand-new, just-licensed businesses that don't have a website yet.
SOCRATA_CATALOG = "http://api.us.socrata.com/api/catalog/v1"

# Column-name aliases seen across portals → our normalized fields.
_SOCRATA_FIELDS = {
    "name": ("business_name", "dba_name", "dba", "doing_business_as", "company_name",
             "licensee_name", "account_name", "name", "ownername", "owner_name",
             "business"),
    "address": ("address", "business_address", "street_address", "full_address",
                "location_address", "premise_address", "site_address", "address_line_1",
                "location", "geocoded_column"),
    "city": ("city", "business_city", "physical_city", "mail_city"),
    "state": ("state", "business_state", "physical_state"),
    "zip": ("zip", "zip_code", "zipcode", "postal_code", "business_zip"),
    "phone": ("phone", "phone_number", "business_phone", "telephone"),
    "website": ("website", "url", "web", "web_address"),
}


def _first_field(row: dict, keys) -> str:
    for k in keys:
        v = row.get(k)
        if isinstance(v, dict):  # SODA "location"/"human_address" columns
            v = v.get("human_address") or v.get("address") or ""
        if v:
            return str(v).strip()
    return ""


def _socrata_map_row(row: dict) -> dict | None:
    name = _first_field(row, _SOCRATA_FIELDS["name"])
    if not name:
        return None
    city = _first_field(row, _SOCRATA_FIELDS["city"])
    addr = _first_field(row, _SOCRATA_FIELDS["address"])
    return {
        "name": name,
        "category": "business license",
        "website": _first_field(row, _SOCRATA_FIELDS["website"]) or None,
        "phone": _first_field(row, _SOCRATA_FIELDS["phone"]) or None,
        "email": None,
        "address": ", ".join(p for p in [addr, city] if p),
        "city": city,
        "state": _first_field(row, _SOCRATA_FIELDS["state"]),
        "zip": _first_field(row, _SOCRATA_FIELDS["zip"]),
        "brand": "",
        "lat": None, "lon": None,
        "source": "socrata",
        "source_url": "",
    }


def _locality_terms(market_label: str) -> str:
    """Best-effort 'city' string from a market label for catalog search.
    'Austin, Texas' → 'Austin';  'austin_tx' → 'austin';  display names → first part."""
    s = (market_label or "").replace("_", " ").strip()
    s = s.split(",")[0].strip()
    # drop a trailing 2-letter state token (e.g. 'austin tx')
    toks = s.split()
    if len(toks) > 1 and len(toks[-1]) == 2:
        toks = toks[:-1]
    return " ".join(toks).strip()


def socrata_collect(market_label: str, *, limit: int | None = None, log=print,
                    datasets: list[dict] | None = None) -> list[dict]:
    """Find recently-licensed businesses from Socrata open-data portals (no key).

    datasets: optional explicit [{"domain":..., "id":...}] to read directly,
    bypassing catalog search (the reliable path for a portal you already know).
    Otherwise we search the Discovery API for the market's locality.
    """
    city = _locality_terms(market_label)
    candidates: list[dict] = list(datasets or [])

    if not candidates:
        if not city:
            log("  Socrata: no locality to search; skipping.")
            return []
        try:
            r = requests.get(SOCRATA_CATALOG, params={
                "q": f"{city} business license", "only": "dataset", "limit": 20,
            }, headers={"User-Agent": UA}, timeout=20)
            results = r.json().get("results", []) if r.status_code == 200 else []
        except Exception as e:
            log(f"  Socrata catalog search failed: {e}")
            return []
        city_l = city.lower()
        for res in results:
            meta, resource = res.get("metadata", {}), res.get("resource", {})
            domain, ds_id = meta.get("domain", ""), resource.get("id", "")
            nm = (resource.get("name", "") or "").lower()
            if not domain or not ds_id:
                continue
            # keep license/registration datasets that look tied to this locality
            looks_license = any(w in nm for w in ("business", "licen", "registration", "tax certif"))
            looks_local = city_l in nm or city_l.replace(" ", "") in domain.lower()
            if looks_license and looks_local:
                candidates.append({"domain": domain, "id": ds_id, "name": resource.get("name", "")})
        log(f"  Socrata: '{city}' -> {len(candidates)} matching dataset(s)")

    out: list[dict] = []
    per = min(1000, limit or 1000)
    for ds in candidates[:3]:
        url = f"https://{ds['domain']}/resource/{ds['id']}.json"
        try:
            r = requests.get(url, params={"$limit": per}, headers={"User-Agent": UA}, timeout=25)
            rows = r.json() if r.status_code == 200 else []
        except Exception as e:
            log(f"  Socrata read failed ({ds['domain']}): {e}")
            continue
        got = 0
        for row in rows if isinstance(rows, list) else []:
            rec = _socrata_map_row(row)
            if rec:
                rec["source_url"] = f"https://{ds['domain']}/d/{ds['id']}"
                out.append(rec)
                got += 1
            if limit and len(out) >= limit:
                break
        log(f"    {ds.get('name') or ds['id']}: {got} records")
        if limit and len(out) >= limit:
            break
    log(f"  Socrata: {len(out)} businesses")
    return out
