"""
Pure (no-network) tests for the data-quality / dedupe helpers in leadgen.quality.
Run:  python leadgen/tests/test_quality.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.quality import (normalize_phone, is_junk_name, haversine_m,
                             geo_close, dedupe_key, merge_records,
                             cross_source_dedupe)


# ── normalize_phone ───────────────────────────────────────────────────────────

def test_normalize_phone_formats():
    assert normalize_phone("(512) 555-0100") == "+15125550100"
    assert normalize_phone("1-512-555-0100") == "+15125550100"
    assert normalize_phone("512.555.0100") == "+15125550100"
    assert normalize_phone("5125550100") == "+15125550100"
    assert normalize_phone("+1 512 555 0100") == "+15125550100"


def test_normalize_phone_junk():
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""
    assert normalize_phone("call us") == ""
    assert normalize_phone("123") == ""            # too short
    assert normalize_phone("00000000000000") == ""  # too long / nonsense
    assert normalize_phone("0125550100") == ""     # area code starts with 0
    assert normalize_phone("5121550100") == ""     # exchange starts with 1


def test_normalize_phone_non_us():
    assert normalize_phone("5125550100", default_country="GB") == ""


# ── is_junk_name ──────────────────────────────────────────────────────────────

def test_is_junk_name():
    for bad in ("", None, "  ", "n/a", "N/A", "test", "TBD", "12345", "##",
                "none", "unknown", "x", "  -  "):
        assert is_junk_name(bad), f"expected junk: {bad!r}"
    for ok in ("Joe's Tacos", "Cedar Dental Group", "AB Realty", "3M"):
        assert not is_junk_name(ok), f"expected real: {ok!r}"


# ── haversine_m / geo_close ───────────────────────────────────────────────────

def test_haversine_sanity():
    # Austin TX area: two points ~ 0.001 deg of latitude apart ≈ 111 meters.
    d = haversine_m(30.2670, -97.7430, 30.2680, -97.7430)
    assert 100 < d < 125, d
    # same point → ~0 m
    assert haversine_m(30.0, -97.0, 30.0, -97.0) < 1e-6


def test_haversine_none_is_inf():
    assert haversine_m(None, -97.0, 30.0, -97.0) == float("inf")
    assert haversine_m(30.0, -97.0, 30.0, None) == float("inf")


def test_geo_close_threshold():
    a = {"lat": 30.2670, "lon": -97.7430}
    b = {"lat": 30.2680, "lon": -97.7430}  # ~111 m away
    assert geo_close(a, b, meters=150)
    assert not geo_close(a, b, meters=75)
    # missing coords are never "close"
    assert not geo_close({"lat": None, "lon": None}, b, meters=10_000)
    assert not geo_close({}, {}, meters=10_000)


# ── dedupe_key ────────────────────────────────────────────────────────────────

def test_dedupe_key_name_and_phone():
    rec = {"name": "Joe's Tacos LLC", "phone": "(512) 555-0100"}
    assert dedupe_key(rec) == "joestacos|+15125550100"
    # no phone → name-only key
    assert dedupe_key({"name": "Joe's Tacos LLC"}) == "joestacos"
    # robust to missing keys
    assert dedupe_key({}) == ""
    assert dedupe_key(None) == ""


# ── merge_records ─────────────────────────────────────────────────────────────

def test_merge_records_fills_and_unions_sources():
    primary = {"name": "Joe's Tacos", "phone": "5125550100",
               "website": "", "lat": None, "lon": None, "source": "overture"}
    other = {"name": "Joe's Tacos", "website": "https://joes.example",
             "email": "hi@joes.example", "lat": 30.27, "lon": -97.74,
             "source": "osm"}
    merged = merge_records(primary, other)
    assert merged is primary
    assert merged["website"] == "https://joes.example"
    assert merged["email"] == "hi@joes.example"
    assert merged["lat"] == 30.27 and merged["lon"] == -97.74
    assert merged["phone"] == "5125550100"          # non-empty primary kept
    assert merged["sources"] == ["overture", "osm"]


def test_merge_records_never_overwrites_nonempty():
    primary = {"name": "A", "website": "https://keep.me", "source": "overture"}
    other = {"name": "A", "website": "https://other.com", "source": "osm"}
    merged = merge_records(primary, other)
    assert merged["website"] == "https://keep.me"


# ── cross_source_dedupe ───────────────────────────────────────────────────────

def test_cross_source_dedupe_merges_overture_and_osm():
    records = [
        {"name": "Cedar Dental Group", "source": "overture",
         "website": "", "phone": "5125550100",
         "lat": 30.2670, "lon": -97.7430},
        {"name": "Cedar Dental Group", "source": "osm",
         "website": "https://cedardental.example",
         "lat": 30.2671, "lon": -97.7431},   # ~14 m away → geo_close
    ]
    out = cross_source_dedupe(records, meters=75)
    assert len(out) == 1
    rec = out[0]
    assert rec["website"] == "https://cedardental.example"
    assert sorted(rec["sources"]) == ["osm", "overture"]
    assert rec["phone"] == "5125550100"


def test_cross_source_dedupe_keeps_distinct_and_order():
    records = [
        {"name": "Alpha Co", "source": "overture", "phone": "5125550100"},
        {"name": "Beta Co", "source": "overture", "phone": "5125550199"},
        # same name + phone as Alpha → exact key dupe, different source
        {"name": "Alpha Co", "source": "osm",
         "website": "https://alpha.example", "phone": "512-555-0100"},
    ]
    out = cross_source_dedupe(records)
    assert [r["name"] for r in out] == ["Alpha Co", "Beta Co"]
    alpha = out[0]
    assert alpha["website"] == "https://alpha.example"
    assert sorted(alpha["sources"]) == ["osm", "overture"]


def test_cross_source_dedupe_same_name_far_apart_not_merged():
    # Same chain-ish name but two genuinely different locations far apart and
    # with no phone → should NOT merge.
    records = [
        {"name": "Quick Lube", "source": "overture",
         "lat": 30.27, "lon": -97.74},
        {"name": "Quick Lube", "source": "overture",
         "lat": 32.78, "lon": -96.80},  # Dallas, ~300 km away
    ]
    out = cross_source_dedupe(records, meters=75)
    assert len(out) == 2


def test_cross_source_dedupe_robust_to_missing_keys():
    out = cross_source_dedupe([{}, None, {"name": "Solo Biz", "source": "osm"}])
    # the two empties collapse by empty key; Solo Biz stays separate
    names = [r.get("name", "") for r in out]
    assert "Solo Biz" in names


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
