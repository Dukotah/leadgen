"""
Scoring tests for the five new verticals (restaurants, home_services, no_ssl,
healthcare_web, directory_only). Importing each module self-registers it.
Run:  python leadgen/tests/test_new_verticals.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import leadgen
from leadgen import get_vertical

# Importing each module triggers self-registration via register(Vertical(...)).
from leadgen.verticals import restaurants      # noqa: F401
from leadgen.verticals import home_services    # noqa: F401
from leadgen.verticals import no_ssl           # noqa: F401
from leadgen.verticals import healthcare_web   # noqa: F401
from leadgen.verticals import directory_only   # noqa: F401


def test_all_five_registered():
    keys = set(leadgen.all_verticals())
    assert {"restaurants", "home_services", "no_ssl",
            "healthcare_web", "directory_only"} <= keys, keys


# ── restaurants: web_design-style, targeted to food ──────────────────────────

def test_restaurants_no_site_is_top_lead():
    v = get_vertical("restaurants")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "A" and "NO WEBSITE" in why


def test_restaurants_weak_link_is_top_lead():
    v = get_vertical("restaurants")
    _, tier, why = v.score({"name": "X", "website": "https://facebook.com/x"})
    assert tier == "A" and "non-site link" in why


def test_restaurants_http_no_mobile_is_b():
    v = get_vertical("restaurants")
    rec = {"name": "X", "website": "http://x.example",
           "audit": {"reachable": True, "https": False, "mobile_viewport": False,
                     "load_ms": 1000, "builder": ""}}
    _, tier, why = v.score(rec)
    assert tier == "B" and "no HTTPS" in why


def test_restaurants_clean_site_is_c():
    v = get_vertical("restaurants")
    rec = {"name": "X", "website": "https://x.example",
           "audit": {"reachable": True, "https": True, "mobile_viewport": True,
                     "load_ms": 800, "builder": ""}}
    _, tier, why = v.score(rec)
    assert tier == "C" and "no obvious issues" in why


# ── home_services: web_design-style, trade-tuned opener ───────────────────────

def test_home_services_no_site_is_top_lead():
    v = get_vertical("home_services")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "A" and "NO WEBSITE" in why


def test_home_services_clean_site_is_c():
    v = get_vertical("home_services")
    rec = {"name": "X", "website": "https://x.example",
           "audit": {"reachable": True, "https": True, "mobile_viewport": True,
                     "load_ms": 700, "builder": ""}}
    _, tier, _ = v.score(rec)
    assert tier == "C"


def test_home_services_opener_mentions_trade_and_city():
    v = get_vertical("home_services")
    opener = v.opener_fn({"name": "X", "website": "", "category": "plumber",
                          "city": "Denver"})
    assert "plumber" in opener and "Denver" in opener


# ── no_ssl: real reachable http site is THE lead ──────────────────────────────

def test_no_ssl_http_site_is_top_lead():
    v = get_vertical("no_ssl")
    rec = {"name": "X", "website": "http://x.example",
           "audit": {"reachable": True, "https": False}}
    _, tier, why = v.score(rec)
    assert tier == "A" and "not secure" in why.lower()


def test_no_ssl_https_site_is_c():
    v = get_vertical("no_ssl")
    rec = {"name": "X", "website": "https://x.example",
           "audit": {"reachable": True, "https": True}}
    _, tier, why = v.score(rec)
    assert tier == "C" and "already secure" in why


def test_no_ssl_no_site_is_not_a_lead():
    v = get_vertical("no_ssl")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "C" and "not an SSL lead" in why


def test_no_ssl_weak_site_is_not_a_lead():
    v = get_vertical("no_ssl")
    _, tier, why = v.score({"name": "X", "website": "https://facebook.com/x"})
    assert tier == "C" and "not an SSL lead" in why


# ── healthcare_web: no website is the headline signal ─────────────────────────

def test_healthcare_no_site_is_top_lead():
    v = get_vertical("healthcare_web")
    _, tier, why = v.score({"name": "Dr X", "website": ""})
    assert tier == "A" and "NO WEBSITE" in why


def test_healthcare_social_is_top_lead():
    v = get_vertical("healthcare_web")
    _, tier, why = v.score({"name": "Dr X", "website": "https://facebook.com/drx"})
    assert tier == "A" and "social-only" in why


def test_healthcare_weak_is_top_lead():
    v = get_vertical("healthcare_web")
    _, tier, why = v.score({"name": "Dr X", "website": "https://yelp.com/biz/drx"})
    assert tier == "A" and "listing/directory" in why


def test_healthcare_real_site_is_c():
    v = get_vertical("healthcare_web")
    _, tier, why = v.score({"name": "Dr X", "website": "https://drx.com"})
    assert tier == "C" and "already has a real website" in why


# ── directory_only: only a directory link is the lead ─────────────────────────

def test_directory_yelp_is_top_lead():
    v = get_vertical("directory_only")
    _, tier, why = v.score({"name": "X", "website": "https://yelp.com/biz/x"})
    assert tier == "A" and "directory listing only" in why


def test_directory_no_site_is_b():
    v = get_vertical("directory_only")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "B" and "no web presence" in why


def test_directory_social_routes_to_b():
    v = get_vertical("directory_only")
    _, tier, why = v.score({"name": "X", "website": "https://facebook.com/x"})
    assert tier == "B" and "social_only vertical" in why


def test_directory_real_site_is_c():
    v = get_vertical("directory_only")
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
