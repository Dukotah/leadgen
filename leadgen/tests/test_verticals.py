"""
Scoring tests for the shipped verticals beyond web_design.
Run:  python leadgen/tests/test_verticals.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import leadgen
from leadgen import get_vertical


def test_all_three_registered():
    keys = set(leadgen.all_verticals())
    assert {"web_design", "seo_audit", "social_only"} <= keys, keys


# ── seo_audit: the buyer is "has a site but it underperforms" ─────────────────

def test_seo_no_site_is_not_a_lead():
    v = get_vertical("seo_audit")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "C" and "not SEO" in why


def test_seo_weak_site_flags_issues():
    v = get_vertical("seo_audit")
    rec = {"name": "X", "website": "http://x.example",
           "audit": {"reachable": True, "https": False, "mobile_viewport": False,
                     "load_ms": 5000, "builder": "Wix"}}
    score, tier, why = v.score(rec)
    assert tier == "A" and "no HTTPS" in why and "not mobile-friendly" in why


def test_seo_clean_site_is_low_priority():
    v = get_vertical("seo_audit")
    rec = {"name": "X", "website": "https://x.example",
           "audit": {"reachable": True, "https": True, "mobile_viewport": True,
                     "load_ms": 900, "builder": ""}}
    _, tier, why = v.score(rec)
    assert tier == "C" and "little to improve" in why


def test_seo_unreachable_is_urgent():
    v = get_vertical("seo_audit")
    rec = {"name": "X", "website": "https://x.example",
           "audit": {"reachable": False}}
    _, tier, why = v.score(rec)
    assert tier == "A" and "unreachable" in why


# ── social_only: the buyer is "no owned website" ──────────────────────────────

def test_social_facebook_is_top_lead():
    v = get_vertical("social_only")
    score, tier, why = v.score({"name": "X", "website": "https://facebook.com/x", "phone": "5"})
    assert tier == "A" and "social-only" in why


def test_social_no_site_is_secondary():
    v = get_vertical("social_only")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "B" and "no web presence" in why


def test_social_real_site_excluded():
    v = get_vertical("social_only")
    _, tier, why = v.score({"name": "X", "website": "https://xownsite.com"})
    assert tier == "C" and "already has a real website" in why


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
