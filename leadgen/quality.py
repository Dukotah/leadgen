"""
Data-quality / dedupe helpers — stdlib only.

These tools clean and collapse records that arrive from multiple data sources
(Overture, OSM, Socrata, NPI, …) where the same real business shows up more than
once, often with slightly different names, partial fields, and varying formatting.

Record shape (all keys optional / may be None):
    {name, category, website, phone, email, address, city, state, zip,
     lat, lon, brand, source, source_url}

Public API:
    normalize_phone(s, default_country="US") -> str   # E.164-ish or ""
    is_junk_name(name) -> bool
    haversine_m(lat1, lon1, lat2, lon2) -> float       # meters or inf
    geo_close(a, b, meters=75) -> bool
    dedupe_key(rec) -> str
    merge_records(primary, other) -> dict
    cross_source_dedupe(records, meters=75) -> list[dict]
"""
from __future__ import annotations

import math
import re

from .suppression import norm


# ── phones ────────────────────────────────────────────────────────────────────

def normalize_phone(s: str, default_country: str = "US") -> str:
    """Return an E.164-ish string ('+15125550100') for a plausible US phone.

    Strips all formatting. Accepts 10-digit numbers (assumed US) and 11-digit
    numbers that start with the US country code '1'. Returns "" for anything
    that is not a plausible US phone (too short, too long, all zeros, or an
    obvious placeholder like 555-555-5555 area-code/exchange that cannot start
    with 0 or 1). Non-US countries fall back to "" since we only know US rules.
    """
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))
    if not digits:
        return ""

    # 11 digits with leading US country code → drop it to a 10-digit number.
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]

    if len(digits) != 10:
        return ""

    # NANP sanity: area code and exchange cannot start with 0 or 1.
    if digits[0] in "01" or digits[3] in "01":
        return ""

    if (default_country or "US").upper() != "US":
        return ""

    return "+1" + digits


# ── names ─────────────────────────────────────────────────────────────────────

_PLACEHOLDER_NAMES = {
    "", "na", "n/a", "none", "null", "test", "testing", "unknown",
    "tbd", "xxx", "asdf", "business", "company", "no name", "noname",
    "sample", "example", "placeholder", "untitled",
}


def is_junk_name(name: str) -> bool:
    """True if a name is empty, a known placeholder, a test string, 'n/a',
    purely numeric, or too short to be a real business name."""
    if not name:
        return True
    raw = str(name).strip()
    low = raw.lower()
    if low in _PLACEHOLDER_NAMES:
        return True
    # numeric-only (allowing punctuation/spaces around the digits)
    if re.fullmatch(r"[\d\s.\-#/]+", raw):
        return True
    # overly-short once normalized to alphanumerics (e.g. "a", "..", "??")
    if len(norm(raw)) < 2:
        return True
    return False


# ── geo ───────────────────────────────────────────────────────────────────────

_EARTH_R_M = 6_371_000.0  # mean Earth radius, meters


def _coord(v):
    """Best-effort float; returns None on missing / unparseable values."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in meters between two lat/lon points.
    Returns float('inf') if any coordinate is None / unparseable."""
    a1, o1, a2, o2 = _coord(lat1), _coord(lon1), _coord(lat2), _coord(lon2)
    if None in (a1, o1, a2, o2):
        return float("inf")
    phi1, phi2 = math.radians(a1), math.radians(a2)
    dphi = math.radians(a2 - a1)
    dlam = math.radians(o2 - o1)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * _EARTH_R_M * math.asin(min(1.0, math.sqrt(h)))


def geo_close(a: dict, b: dict, meters: float = 75) -> bool:
    """True if both records carry coordinates and are within `meters`."""
    a = a or {}
    b = b or {}
    d = haversine_m(a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon"))
    return d <= meters


# ── dedupe ────────────────────────────────────────────────────────────────────

def dedupe_key(rec: dict) -> str:
    """A robust cross-source key: normalized name + normalized phone.

    When a phone is present it disambiguates two different businesses that share
    a generic name; when absent the key falls back to the normalized name alone.
    """
    rec = rec or {}
    name_key = norm(rec.get("name", ""))
    phone_key = normalize_phone(rec.get("phone", "") or "")
    if phone_key:
        return f"{name_key}|{phone_key}"
    return name_key


# Fields filled from `other` when `primary` is missing them (non-empty wins).
_FILL_FIELDS = (
    "category", "website", "phone", "email", "address", "city", "state",
    "zip", "lat", "lon", "brand", "source_url",
)


def _empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    return False


def merge_records(primary: dict, other: dict) -> dict:
    """Fill missing fields of `primary` from `other` and union their sources.

    A non-empty value already on `primary` is never overwritten. The `source`
    of both records is unioned into a `sources` list (order-preserving), and
    `primary["source"]` is left as the primary's own source. Returns `primary`
    (mutated in place)."""
    primary = primary if primary is not None else {}
    other = other or {}

    for f in _FILL_FIELDS:
        if _empty(primary.get(f)) and not _empty(other.get(f)):
            primary[f] = other.get(f)

    # name: keep primary's, but adopt other's if primary somehow lacks one.
    if _empty(primary.get("name")) and not _empty(other.get("name")):
        primary["name"] = other.get("name")

    # union sources (preserve first-seen order, no duplicates)
    sources: list[str] = []
    for src in list(primary.get("sources") or []):
        if src and src not in sources:
            sources.append(src)
    for s in (primary.get("source"), other.get("source")):
        if s and s not in sources:
            sources.append(s)
    for src in list(other.get("sources") or []):
        if src and src not in sources:
            sources.append(src)
    if sources:
        primary["sources"] = sources

    return primary


def cross_source_dedupe(records: list[dict], meters: float = 75) -> list[dict]:
    """Collapse duplicates across sources, preserving first-occurrence order.

    Two records are duplicates when EITHER:
      * they share a dedupe_key (normalized name [+ phone]), OR
      * they share a normalized name AND are geographically close (geo_close).

    Duplicates are merged into the first occurrence via merge_records().
    Junk-named records are kept as-is (they never match anything but each other
    only by exact key) so callers can still see / filter them downstream.
    """
    kept: list[dict] = []
    by_key: dict[str, dict] = {}
    # index of kept records that carry a usable name, for geo fallback matching
    by_name: dict[str, list[dict]] = {}

    for rec in records or []:
        rec = rec or {}
        key = dedupe_key(rec)
        name_key = norm(rec.get("name", ""))

        has_phone = bool(normalize_phone(rec.get("phone", "") or ""))
        target = None

        # 1. exact key match. A phone-bearing key (name+phone) is a strong
        #    identity match and merges regardless of distance. A name-only key
        #    only merges outright when neither record can be disambiguated by
        #    geography (see step 2 for the geo-aware case).
        if has_phone and key and key in by_key:
            target = by_key[key]

        # 2. same normalized name AND geographically close — OR same name where
        #    coordinates are absent on either side (so we can't tell them apart).
        if target is None and name_key:
            for cand in by_name.get(name_key, []):
                if geo_close(cand, rec, meters):
                    target = cand
                    break
                # no usable coords on one/both → fall back to name-only identity
                if haversine_m(cand.get("lat"), cand.get("lon"),
                               rec.get("lat"), rec.get("lon")) == float("inf"):
                    target = cand
                    break

        if target is not None:
            merge_records(target, rec)
            # a merge can change the target's key (e.g. it gains a phone);
            # re-register the (possibly new) key so later records still match.
            new_key = dedupe_key(target)
            by_key.setdefault(new_key, target)
            continue

        # new record
        kept.append(rec)
        if key:
            by_key.setdefault(key, rec)
        if name_key:
            by_name.setdefault(name_key, []).append(rec)

    return kept
