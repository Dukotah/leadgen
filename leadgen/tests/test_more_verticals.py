"""
Scoring tests for the six newer verticals (ecommerce_ready, booking_gap,
outdated_site, social_media_mgmt, new_business, restaurant_menu_gap).

Each test imports the vertical's module directly so importing this file is enough
to register it (no dependence on the package __init__ wiring), fetches it via
get_vertical(key), and asserts tiers on hand-built records. The audit-driven
verticals are exercised with a fully-formed rec["audit"] so the signals branches
run with no network.

Run:  python leadgen/tests/test_more_verticals.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen import get_vertical
# Direct imports trigger each module's register(...) call.
import leadgen.verticals.ecommerce_ready        # noqa: F401
import leadgen.verticals.booking_gap            # noqa: F401
import leadgen.verticals.outdated_site          # noqa: F401
import leadgen.verticals.social_media_mgmt      # noqa: F401
import leadgen.verticals.new_business           # noqa: F401
import leadgen.verticals.restaurant_menu_gap    # noqa: F401


def _audit(html: str) -> dict:
    """A live-looking audit dict (reachable/https/mobile) with the given HTML, so
    the signals-based branches run offline."""
    return {"reachable": True, "https": True, "mobile_viewport": True,
            "builder": "", "html": html}


# ── ecommerce_ready ───────────────────────────────────────────────────────────

def test_ecommerce_real_site_no_store_is_A():
    v = get_vertical("ecommerce_ready")
    rec = {"name": "Shop", "website": "https://shop.example",
           "audit": _audit("<html><body>Welcome to our boutique</body></html>")}
    _, tier, why = v.score(rec)
    assert tier == "A" and "no online store" in why, (tier, why)


def test_ecommerce_has_store_is_C():
    v = get_vertical("ecommerce_ready")
    rec = {"name": "Shop", "website": "https://shop.example",
           "audit": _audit("<html>cdn.shopify.com add to cart</html>")}
    _, tier, why = v.score(rec)
    assert tier == "C" and "already sells online" in why, (tier, why)


def test_ecommerce_no_site_is_B():
    v = get_vertical("ecommerce_ready")
    _, tier, why = v.score({"name": "Shop", "website": ""})
    assert tier == "B" and "no real site" in why, (tier, why)


# ── booking_gap ───────────────────────────────────────────────────────────────

def test_booking_real_site_no_booking_is_A():
    v = get_vertical("booking_gap")
    rec = {"name": "Salon", "website": "https://salon.example",
           "audit": _audit("<html><body>Call us for an appointment</body></html>")}
    _, tier, why = v.score(rec)
    assert tier == "A" and "no online scheduling" in why, (tier, why)


def test_booking_has_booking_is_C():
    v = get_vertical("booking_gap")
    rec = {"name": "Salon", "website": "https://salon.example",
           "audit": _audit("<html>book now via calendly.com/salon</html>")}
    _, tier, why = v.score(rec)
    assert tier == "C" and "already books online" in why, (tier, why)


def test_booking_no_site_is_B():
    v = get_vertical("booking_gap")
    _, tier, why = v.score({"name": "Salon", "website": ""})
    assert tier == "B" and "no real site" in why, (tier, why)


# ── outdated_site ─────────────────────────────────────────────────────────────

def test_outdated_stale_year_is_A():
    v = get_vertical("outdated_site")
    rec = {"name": "Biz", "website": "https://biz.example",
           "audit": _audit("<footer>&copy; 2019 Biz LLC</footer>")}
    _, tier, why = v.score(rec)
    assert tier == "A" and "stale since 2019" in why, (tier, why)


def test_outdated_recent_year_is_C():
    v = get_vertical("outdated_site")
    rec = {"name": "Biz", "website": "https://biz.example",
           "audit": _audit("<footer>&copy; 2026 Biz LLC</footer>")}
    _, tier, why = v.score(rec)
    assert tier == "C" and "recent copyright (2026)" in why, (tier, why)


def test_outdated_no_site_is_B():
    v = get_vertical("outdated_site")
    _, tier, why = v.score({"name": "Biz", "website": ""})
    assert tier == "B" and "no real site" in why, (tier, why)


# ── social_media_mgmt ─────────────────────────────────────────────────────────

def test_smm_social_is_A():
    v = get_vertical("social_media_mgmt")
    _, tier, why = v.score({"name": "X", "website": "https://facebook.com/x"})
    assert tier == "A" and "social only" in why, (tier, why)


def test_smm_no_site_is_B():
    v = get_vertical("social_media_mgmt")
    _, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "B" and "no online presence" in why, (tier, why)


def test_smm_real_site_is_C():
    v = get_vertical("social_media_mgmt")
    _, tier, why = v.score({"name": "X", "website": "https://xownsite.com"})
    assert tier == "C" and "real website" in why, (tier, why)


# ── new_business ──────────────────────────────────────────────────────────────

def test_new_business_license_no_site_is_A():
    v = get_vertical("new_business")
    _, tier, why = v.score({"name": "X", "website": "", "source": "socrata"})
    assert tier == "A" and "newly listed (socrata), no site" in why, (tier, why)


def test_new_business_other_source_no_site_is_B():
    v = get_vertical("new_business")
    _, tier, why = v.score({"name": "X", "website": "", "source": "osm"})
    assert tier == "B" and "no website yet" in why, (tier, why)


def test_new_business_has_site_is_C():
    v = get_vertical("new_business")
    _, tier, why = v.score({"name": "X", "website": "https://x.example", "source": "npi"})
    assert tier == "C" and "already has a site" in why, (tier, why)


# ── restaurant_menu_gap ───────────────────────────────────────────────────────

def test_restaurant_no_menu_is_A():
    v = get_vertical("restaurant_menu_gap")
    rec = {"name": "Diner", "website": "https://diner.example",
           "audit": _audit("<html><body>Open daily, family owned since 1990</body></html>")}
    _, tier, why = v.score(rec)
    assert tier == "A" and "no online menu/ordering" in why, (tier, why)


def test_restaurant_has_menu_is_C():
    v = get_vertical("restaurant_menu_gap")
    rec = {"name": "Diner", "website": "https://diner.example",
           "audit": _audit("<html><a href='/menu'>Our Menu</a> order on doordash</html>")}
    _, tier, why = v.score(rec)
    assert tier == "C" and "menu/online ordering present" in why, (tier, why)


def test_restaurant_no_site_is_B():
    v = get_vertical("restaurant_menu_gap")
    _, tier, why = v.score({"name": "Diner", "website": ""})
    assert tier == "B" and "no real site" in why, (tier, why)


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
