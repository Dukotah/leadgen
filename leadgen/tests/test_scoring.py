"""
Pure (no-network) tests for the shared scoring helpers in leadgen/scoring.py:
normalize_score (incl. clamping), tier_from_score thresholds, reason_tags
mapping + slug fallback, and ScoreBuilder end-to-end.
Run:  python leadgen/tests/test_scoring.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.scoring import (normalize_score, tier_from_score, reason_tags,
                             ScoreBuilder)


# ── normalize_score ───────────────────────────────────────────────────────────

def test_normalize_basic_scaling():
    assert normalize_score(30, 60) == 50
    assert normalize_score(60, 60) == 100
    assert normalize_score(0, 60) == 0
    assert normalize_score(15, 60) == 25


def test_normalize_clamps_high_and_low():
    assert normalize_score(120, 100) == 100   # above max clamps to 100
    assert normalize_score(-10, 100) == 0     # negative clamps to 0


def test_normalize_bad_max_and_inputs():
    assert normalize_score(50, 0) == 0        # zero max -> undefined -> 0
    assert normalize_score(50, -5) == 0       # negative max -> 0
    assert normalize_score("x", 100) == 0     # non-numeric -> 0, no raise


def test_normalize_rounding():
    # 1/3 -> 33, 2/3 -> 67 (round-half-to-even/up both land here)
    assert normalize_score(1, 3) == 33
    assert normalize_score(2, 3) == 67


# ── tier_from_score ───────────────────────────────────────────────────────────

def test_tier_default_thresholds():
    assert tier_from_score(100) == "A"
    assert tier_from_score(60) == "A"        # boundary is inclusive
    assert tier_from_score(59) == "B"
    assert tier_from_score(30) == "B"        # boundary inclusive
    assert tier_from_score(29) == "C"
    assert tier_from_score(0) == "C"


def test_tier_custom_thresholds():
    assert tier_from_score(80, a=80, b=50) == "A"
    assert tier_from_score(79, a=80, b=50) == "B"
    assert tier_from_score(50, a=80, b=50) == "B"
    assert tier_from_score(49, a=80, b=50) == "C"


def test_tier_bad_input():
    assert tier_from_score("nope") == "C"     # non-numeric falls to C, no raise


# ── reason_tags ───────────────────────────────────────────────────────────────

def test_reason_tags_known_mapping():
    tags = reason_tags("NO WEBSITE; no HTTPS; not mobile-friendly")
    assert tags == ["no_website", "no_https", "not_mobile_friendly"]


def test_reason_tags_parameterized_reasons():
    # parameterized reasons still map via substring match
    assert reason_tags("slow (5200ms)") == ["slow_load"]
    assert reason_tags("DIY (Wix)") == ["diy_builder"]
    assert reason_tags("non-site link (facebook.com)") == ["social_only"]


def test_reason_tags_slug_fallback():
    # unmapped reason -> slug; parenthetical detail stripped from the slug
    assert reason_tags("Brand new thing (42 widgets)") == ["brand_new_thing"]
    assert reason_tags("Foo Bar Baz") == ["foo_bar_baz"]


def test_reason_tags_dedup_and_empty():
    # duplicate-mapping reasons collapse; empty/None -> []
    assert reason_tags("no HTTPS; http only") == ["no_https"]
    assert reason_tags("") == []
    assert reason_tags(None) == []
    assert reason_tags(";  ; ") == []


# ── ScoreBuilder ──────────────────────────────────────────────────────────────

def test_scorebuilder_end_to_end():
    sb = ScoreBuilder()
    sb.add(60, "NO WEBSITE", "no_website")
    sb.add(18, "no HTTPS")                    # code inferred from reason
    sb.add(4, "phone listed")
    score100, tier, reasons, tags = sb.result(max_raw=100)
    assert score100 == 82                     # 82/100
    assert tier == "A"
    assert reasons == "NO WEBSITE; no HTTPS; phone listed"
    assert tags == ["no_website", "no_https", "phone_listed"]


def test_scorebuilder_chaining_and_raw():
    sb = ScoreBuilder().add(10, "a").add(20, "b")
    assert sb.raw == 30
    # returns self for chaining
    assert isinstance(sb.add(5, "c"), ScoreBuilder)
    assert sb.raw == 35


def test_scorebuilder_normalizes_and_tiers():
    sb = ScoreBuilder()
    sb.add(15, "no HTTPS")                     # 15/100 -> 15 -> tier C
    score100, tier, _, _ = sb.result(max_raw=100)
    assert score100 == 15 and tier == "C"


def test_scorebuilder_blank_reason_counts_points_no_tag():
    sb = ScoreBuilder()
    sb.add(50, "")                             # points count, no reason/tag
    score100, tier, reasons, tags = sb.result(max_raw=100)
    assert score100 == 50 and tier == "B"
    assert reasons == "" and tags == []


def test_scorebuilder_clamps_over_max():
    sb = ScoreBuilder().add(150, "huge")
    score100, tier, _, _ = sb.result(max_raw=100)
    assert score100 == 100 and tier == "A"


def test_scorebuilder_empty():
    score100, tier, reasons, tags = ScoreBuilder().result(max_raw=100)
    assert score100 == 0 and tier == "C"
    assert reasons == "" and tags == []


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
