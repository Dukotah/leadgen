"""
Tests for the beginner-friendly features: offline demo mode, CRM dedupe,
friendly errors. Run:  python leadgen/tests/test_features.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen import get_vertical, run_pipeline
from leadgen.pipeline import load_crm_names
from leadgen.diagnostics import friendly_error, explain_empty_result


def test_demo_mode_runs_offline_and_tiers():
    v = get_vertical("web_design")
    leads = run_pipeline(v, market="(demo)", demo=True, enrich=True, log=lambda *_: None)
    assert len(leads) == 5, f"expected 5 demo leads, got {len(leads)}"
    # every lead got scored + an opener
    assert all("tier" in r and "opener" in r for r in leads)
    # the no-website business should be the top lead
    assert leads[0]["name"] == "Summit Plumbing Co", [l["name"] for l in leads]
    assert "NO WEBSITE" in leads[0]["why"]
    # the Wix/HTTP cafe was audited offline and flagged DIY → Tier B
    cafe = next(r for r in leads if r["name"] == "Sunrise Cafe")
    assert cafe["tier"] == "B" and cafe["audit"]["builder"] == "Wix"
    # the clean modern site lands in Tier C with no obvious issues
    dental = next(r for r in leads if r["name"] == "Evergreen Dental")
    assert dental["tier"] == "C" and "no obvious issues" in dental["why"]
    # the unreachable site is Tier A
    auto = next(r for r in leads if r["name"] == "Old Town Auto Repair")
    assert auto["tier"] == "A" and "unreachable" in auto["why"]


def test_crm_dedupe_removes_existing():
    csv_text = 'Company name,Phone\nSummit Plumbing Co,555\n"Evergreen Dental, LLC",555\n'
    names = load_crm_names(csv_text, is_text=True)
    assert names, "no names parsed"
    v = get_vertical("web_design")
    leads = run_pipeline(v, market="(demo)", demo=True, enrich=True,
                         exclude_names=names, log=lambda *_: None)
    got = {l["name"] for l in leads}
    assert "Summit Plumbing Co" not in got, "CRM dedupe failed to remove Summit"
    assert "Evergreen Dental" not in got, "normalized CRM match failed"
    assert "Bella Hair Studio" in got, "wrongly removed a non-CRM lead"


def test_load_crm_names_various_headers():
    assert load_crm_names("Business,City\nAcme Plumbing,Reno\n", is_text=True) == {"acmeplumbing"}
    assert load_crm_names("name\nThe Smith Team\n", is_text=True) == {"smith"}
    # no header match → falls back to first column
    assert load_crm_names("foo,bar\nWidget Co,x\n", is_text=True) == {"widget"}
    assert load_crm_names("", is_text=True) == set()


def test_friendly_error_translates():
    assert "place name" in friendly_error("could not resolve market 'Xyz'").lower()
    assert "openstreetmap" in friendly_error("All Overpass mirrors failed (HTTP 403)").lower()
    assert "network" in friendly_error("Host not in allowlist").lower()
    # unknown errors pass through unchanged
    assert friendly_error("some weird thing") == "some weird thing"


def test_explain_empty_result():
    msg = explain_empty_result("Tiny Town, MT", ("overture",), "web-design leads")
    assert "Tiny Town" in msg and "larger" in msg.lower()


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            import traceback
            failed += 1; print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
