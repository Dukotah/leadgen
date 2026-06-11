"""
Tests for the pure (non-network) engine logic: scoring, suppression parsing,
dedupe, and export. Run:  python -m pytest leadgen/tests -q
or simply:  python leadgen/tests/test_engine.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import leadgen
from leadgen import get_vertical
from leadgen.suppression import norm, _candidates_from_html
from leadgen.export import write_csv
from leadgen.pipeline import _dedupe


def test_verticals_registered():
    keys = set(leadgen.all_verticals())
    assert "web_design" in keys


def test_norm_strips_legal_suffixes():
    assert norm("Acme Plumbing, LLC") == norm("Acme Plumbing Group")
    assert norm("The Smith Team") == norm("Smith")
    assert norm("") == ""


def test_web_design_no_site_is_tier_a():
    v = get_vertical("web_design")
    score, tier, why = v.score({"name": "Summit Plumbing", "website": "", "phone": "555"})
    assert tier == "A" and "NO WEBSITE" in why and score >= 60


def test_web_design_social_only_is_tier_a():
    v = get_vertical("web_design")
    score, tier, why = v.score({"name": "Bella Hair", "website": "https://facebook.com/bella"})
    assert tier == "A" and "non-site link" in why


def test_web_design_clean_site_is_tier_c():
    v = get_vertical("web_design")
    rec = {"name": "Bright Dental", "website": "https://bright.example",
           "audit": {"reachable": True, "https": True, "mobile_viewport": True, "builder": ""}}
    _, tier, why = v.score(rec)
    assert tier == "C" and "no obvious issues" in why


def test_web_design_diy_http_site_is_tier_b():
    v = get_vertical("web_design")
    rec = {"name": "Joe's Diner", "website": "http://joes.example",
           "audit": {"reachable": True, "https": False, "mobile_viewport": False, "builder": "Wix"}}
    score, tier, why = v.score(rec)
    assert tier == "B" and "no HTTPS" in why and "Wix" in why


def test_suppression_parsing():
    html = '''
      <blockquote>Great service! — Jane Doe, Acme Plumbing</blockquote>
      <img alt="Summit Auto Repair" src="logo.png">
      <cite>Harbor Cafe</cite>
    '''
    names = _candidates_from_html(html)
    assert any("acme" in n.lower() for n in names)
    assert any("summit" in n.lower() for n in names)


def test_dedupe_merges_and_fills():
    leads = [
        {"name": "Acme Plumbing LLC", "website": "", "phone": "111"},
        {"name": "Acme Plumbing Group", "website": "http://acme.example", "phone": ""},
    ]
    out = _dedupe(leads)
    assert len(out) == 1
    assert out[0]["website"] == "http://acme.example"  # filled from the duplicate
    assert out[0]["phone"] == "111"


def test_export_csv_uses_vertical_columns():
    v = get_vertical("web_design")
    rows = [{"name": "Joe's Diner", "tier": "A", "score": 64, "city": "Tampa"}]
    with tempfile.TemporaryDirectory() as d:
        p = write_csv(rows, v.columns, os.path.join(d, "out.csv"))
        content = open(p, encoding="utf-8").read()
    assert "Business" in content and "Joe's Diner" in content and "Tier" in content


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
