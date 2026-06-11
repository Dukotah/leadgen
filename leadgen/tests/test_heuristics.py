"""
Tests for the audit + enrichment heuristics against realistic website fixtures.
Run:  python leadgen/tests/test_heuristics.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.audit import audit_from_html, is_weak_url
from leadgen.enrich import estimate_roster, find_decision_maker, find_phrases
from leadgen.tests import fixtures as F

TITLES = ["Owner", "Managing Partner", "Office Manager", "Associate"]


def _pages(html):
    return {"http://x.test/": html}


# ── roster sizing ─────────────────────────────────────────────────────────────

def test_roster_count_distinct():
    # TEAM_PAGE: 4 distinct /team/ profile links
    assert estimate_roster(_pages(F.TEAM_PAGE)) == 4
    # DUP_LINKS: 3 people each linked twice → must be 3, not 6
    assert estimate_roster(_pages(F.DUP_LINKS)) == 3
    # CLEAN_SITE: no team → 0 ("unknown", not a real zero)
    assert estimate_roster(_pages(F.CLEAN_SITE)) == 0


# ── decision-maker extraction ─────────────────────────────────────────────────

def test_decision_maker_prefers_senior_title():
    name, title = find_decision_maker(_pages(F.TEAM_PAGE), TITLES)
    assert name == "Maria Reyes", (name, title)
    assert "owner" in title.lower()


def test_decision_maker_none_when_absent():
    name, title = find_decision_maker(_pages(F.DUP_LINKS), TITLES)
    assert name == "" and title == ""


# ── phrase detection ──────────────────────────────────────────────────────────

def test_find_phrases():
    present = find_phrases(_pages(F.WIX_SITE), ["wix", "shopify", "squarespace"])
    assert present == ["wix"]


# ── website audit signals ─────────────────────────────────────────────────────

def test_audit_flags_diy_and_http():
    a = audit_from_html(F.WIX_SITE, "http://joes.example", reachable=True)
    assert a["builder"] == "Wix"
    assert a["mobile_viewport"] is False
    assert a["https"] is False
    assert any("DIY" in n for n in a["audit_notes"])


def test_audit_passes_clean_site():
    a = audit_from_html(F.CLEAN_SITE, "https://bright.example", reachable=True)
    assert a["https"] is True
    assert a["mobile_viewport"] is True
    assert a["builder"] == ""
    assert a["reachable"] is True


def test_is_weak_url_host_boundary():
    assert is_weak_url("https://facebook.com/somebiz")[0] is True
    assert is_weak_url("https://www.instagram.com/x")[0] is True
    assert is_weak_url("https://fedex.com")[0] is False  # not "x.com"
    assert is_weak_url("https://joesdiner.com")[0] is False
    assert is_weak_url("")[0] is True


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
