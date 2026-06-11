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


def _overpass_query(bbox, tag_filters: list[str], timeout: int = 60) -> list[dict]:
    south, west, north, east = bbox
    parts = []
    for tf in tag_filters:
        if "=" not in tf:
            continue
        k, v = tf.split("=", 1)
        parts.append(f'nwr["{k}"="{v}"]({south},{west},{north},{east});')
    if not parts:
        return []
    body = (f"[out:json][timeout:{timeout}];\n(\n  " + "\n  ".join(parts)
            + "\n);\nout center tags;")
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
        out.append({
            "name": name.strip(),
            "category": next((t for t in osm_tags if "=" in t), ""),
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
