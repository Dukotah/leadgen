"""
Scoring tests for the niche verticals (auto / fitness / pet / beauty / pro-services).
Each follows the web_design "needs a website" contract:
  - no website            => Tier A
  - real audited site, ok => Tier C

Run:  python leadgen/tests/test_niche_verticals.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import each module directly to trigger its register(Vertical(...)) side effect.
from leadgen.verticals import auto_services        # noqa: F401
from leadgen.verticals import fitness_wellness     # noqa: F401
from leadgen.verticals import pet_services         # noqa: F401
from leadgen.verticals import beauty               # noqa: F401
from leadgen.verticals import professional_services  # noqa: F401

from leadgen import get_vertical

KEYS = ["auto_services", "fitness_wellness", "pet_services", "beauty",
        "professional_services"]

# A clean, reachable real site that should score as low-priority (Tier C).
_GOOD_AUDIT = {"reachable": True, "https": True, "mobile_viewport": True,
               "load_ms": 800, "builder": "WordPress"}


def _check_no_site_is_tier_a(key: str) -> None:
    v = get_vertical(key)
    score, tier, why = v.score({"name": "X", "website": ""})
    assert tier == "A", f"{key}: expected A for no site, got {tier} ({why})"
    assert "NO WEBSITE" in why, f"{key}: missing reason ({why})"


def _check_real_site_is_tier_c(key: str) -> None:
    v = get_vertical(key)
    rec = {"name": "X", "website": "https://realbiz.example", "audit": dict(_GOOD_AUDIT)}
    score, tier, why = v.score(rec)
    assert tier == "C", f"{key}: expected C for clean real site, got {tier} ({why})"


def test_auto_services_no_site_is_tier_a():
    _check_no_site_is_tier_a("auto_services")


def test_auto_services_real_site_is_tier_c():
    _check_real_site_is_tier_c("auto_services")


def test_fitness_wellness_no_site_is_tier_a():
    _check_no_site_is_tier_a("fitness_wellness")


def test_fitness_wellness_real_site_is_tier_c():
    _check_real_site_is_tier_c("fitness_wellness")


def test_pet_services_no_site_is_tier_a():
    _check_no_site_is_tier_a("pet_services")


def test_pet_services_real_site_is_tier_c():
    _check_real_site_is_tier_c("pet_services")


def test_beauty_no_site_is_tier_a():
    _check_no_site_is_tier_a("beauty")


def test_beauty_real_site_is_tier_c():
    _check_real_site_is_tier_c("beauty")


def test_professional_services_no_site_is_tier_a():
    _check_no_site_is_tier_a("professional_services")


def test_professional_services_real_site_is_tier_c():
    _check_real_site_is_tier_c("professional_services")


def test_all_five_registered():
    import leadgen
    keys = set(leadgen.all_verticals())
    assert set(KEYS) <= keys, keys


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
