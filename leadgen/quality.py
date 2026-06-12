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
    parse_address(addr) -> dict                         # {street,city,state,zip}
    is_closed(rec) -> bool
    looks_like_chain(rec, brands=None) -> bool
    field_confidence(rec) -> dict                       # {field: verified|guessed|missing}
    load_do_not_contact(path_or_text, is_text=False) -> set[str]
    filter_new(records, seen_keys) -> list[dict]
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


# ── address parsing ─────────────────────────────────────────────────────────────

_STATE_RE = re.compile(r"\b([A-Za-z]{2})\b")
_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

# Two-letter US state/territory abbreviations (so a random 2-letter word like
# "St" or "Dr" in a street name isn't mistaken for a state).
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC", "PR", "VI", "GU", "AS", "MP",
}


def parse_address(addr: str) -> dict:
    """Best-effort {street, city, state, zip} from a US address string.

    Heuristic and forgiving: state is a recognized 2-letter US abbreviation,
    zip is a 5-digit code (a trailing +4 is dropped). Anything that can't be
    found is returned as "". Typical comma-separated form is preferred
    ("123 Main St, Austin, TX 78701") but it also degrades gracefully on
    looser input.
    """
    out = {"street": "", "city": "", "state": "", "zip": ""}
    if not addr:
        return out
    s = str(addr).strip()
    if not s:
        return out

    # zip: last 5-digit (optionally +4) token wins.
    zm = None
    for zm in _ZIP_RE.finditer(s):
        pass
    if zm:
        out["zip"] = zm.group(1)

    # state: prefer a 2-letter US abbrev that appears just before the zip (or at
    # the tail); scan right-to-left so a street word like "St" doesn't win.
    upto = s[:zm.start()] if zm else s
    state_tok = ""
    for m in _STATE_RE.finditer(upto):
        cand = m.group(1).upper()
        if cand in _US_STATES:
            state_tok = cand
            state_pos = m.start()
    if state_tok:
        out["state"] = state_tok

    # Split the leading portion on commas to recover street / city.
    head = upto
    if out["state"]:
        head = upto[:state_pos]
    parts = [p.strip() for p in head.split(",") if p.strip()]
    if parts:
        out["street"] = parts[0]
    if len(parts) >= 2:
        out["city"] = parts[1]
    return out


# ── closed-business detection ───────────────────────────────────────────────────

_CLOSED_SIGNALS = (
    "disused", "abandoned", "permanently closed", "(closed)",
)


def is_closed(rec: dict) -> bool:
    """Heuristic: True if any signal suggests the business is closed.

    Signals: a truthy 'closed' or 'date_closed' key, or one of the closed
    phrases ('disused', 'abandoned', 'permanently closed', '(closed)')
    appearing in the record's category, source_url, or name.
    """
    rec = rec or {}
    if rec.get("closed") or rec.get("date_closed"):
        return True
    hay = " ".join(
        str(rec.get(k) or "") for k in ("category", "source_url", "name")
    ).lower()
    return any(sig in hay for sig in _CLOSED_SIGNALS)


# ── chain / franchise detection ─────────────────────────────────────────────────

_DEFAULT_BRANDS = {
    "mcdonalds", "starbucks", "subway", "walmart", "target", "burgerking",
    "wendys", "tacobell", "dunkin", "dunkindonuts", "kfc", "pizzahut",
    "dominos", "chipotle", "chickfila", "costco", "walgreens", "cvs",
    "cvspharmacy", "homedepot", "lowes", "bestbuy", "7eleven", "dollargeneral",
    "dollartree", "familydollar", "wellsfargo", "bankofamerica", "chase",
    "ups", "fedex", "shell", "chevron", "exxon", "circlek", "autozone",
    "oreillyautoparts", "jiffylube", "marriott", "hilton", "holidayinn",
    "applebees", "ihop", "dennys", "panerabread", "papajohns", "littlecaesars",
}

# Franchise/store-number patterns that scream "chain location".
_CHAIN_PATTERNS = (
    re.compile(r"#\s*\d+\b"),                 # "Subway #2031"
    re.compile(r"\bstore\s*#?\s*\d+\b", re.I),  # "Store #14"
)


def looks_like_chain(rec: dict, brands: set[str] | None = None) -> bool:
    """True if the record looks like a chain / franchise location.

    Matches when: rec['brand'] is set, the normalized name is in the provided
    (or built-in default) brand set, or the name carries an obvious franchise
    pattern such as a store number ("#2031", "Store #14").
    """
    rec = rec or {}
    if not _empty(rec.get("brand")):
        return True
    name = str(rec.get("name") or "")
    if not name:
        return False
    key = norm(name)
    brand_set = _DEFAULT_BRANDS if brands is None else {norm(b) for b in brands}
    if key and key in brand_set:
        return True
    return any(p.search(name) for p in _CHAIN_PATTERNS)


# ── per-field confidence ────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_RE = re.compile(r"^\+\d{8,15}$")


def field_confidence(rec: dict) -> dict:
    """Per-field {field: "verified"|"guessed"|"missing"} for the key contact
    fields (name, website, phone, email, address).

    "missing" when empty; "verified" when present AND well-formed (phone is
    E.164-ish, email has a local@domain.tld shape, website has a dot, name is
    not junk, address parses to a street); otherwise "guessed".
    """
    rec = rec or {}
    out: dict[str, str] = {}

    def verdict(field: str, ok: bool) -> str:
        if _empty(rec.get(field)):
            return "missing"
        return "verified" if ok else "guessed"

    name = str(rec.get("name") or "")
    out["name"] = verdict("name", bool(name) and not is_junk_name(name))

    website = str(rec.get("website") or "")
    out["website"] = verdict("website", "." in website and " " not in website.strip())

    phone = str(rec.get("phone") or "")
    out["phone"] = verdict("phone", bool(_E164_RE.match(phone))
                           or bool(normalize_phone(phone)))

    email = str(rec.get("email") or "")
    out["email"] = verdict("email", bool(_EMAIL_RE.match(email.strip())))

    address = str(rec.get("address") or "")
    out["address"] = verdict("address", bool(parse_address(address)["street"]))

    return out


# ── do-not-contact list ─────────────────────────────────────────────────────────

def load_do_not_contact(path_or_text: str, is_text: bool = False) -> set[str]:
    """Normalized business names to suppress, from a CSV (file path or raw text).

    Mirrors pipeline.load_crm_names: reads the first column that looks like a
    company/business/name field (else the first column) and returns normalized
    keys via norm(). A lead whose norm(name) is in this set should never be
    contacted.
    """
    import csv
    import io
    if not path_or_text:
        return set()
    if is_text:
        f = io.StringIO(path_or_text)
    else:
        f = open(path_or_text, newline="", encoding="utf-8-sig", errors="replace")
    try:
        rows = list(csv.reader(f))
    finally:
        if not is_text:
            f.close()
    if not rows:
        return set()
    header = [h.strip().lower() for h in rows[0]]
    name_keys = ("company name", "company", "business", "business name",
                 "brokerage", "name", "account name", "organization")
    col = next((i for i, h in enumerate(header) if h in name_keys), 0)
    out: set[str] = set()
    for row in rows[1:]:
        if col < len(row):
            k = norm(row[col])
            if k:
                out.add(k)
    return out


# ── cross-run dedupe ─────────────────────────────────────────────────────────────

def filter_new(records: list[dict], seen_keys: set[str]) -> list[dict]:
    """Drop records whose dedupe_key is already in `seen_keys` (cross-run dedupe).

    Order-preserving. An empty dedupe_key (no usable name) is treated as
    never-seen so junk records aren't all collapsed against one another here;
    the caller is responsible for persisting the keys of records it accepts.
    """
    seen = seen_keys or set()
    out: list[dict] = []
    for rec in records or []:
        key = dedupe_key(rec or {})
        if key and key in seen:
            continue
        out.append(rec)
    return out
