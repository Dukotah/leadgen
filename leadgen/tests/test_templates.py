"""
Pure tests for leadgen.templates — {token} opener rendering.
Run:  python leadgen/tests/test_templates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.templates import DEFAULT_OPENERS, render_opener, render_all

REC = {
    "name": "Joe's Tacos", "city": "Austin", "category": "restaurant",
    "website": "http://joes.com", "phone": "512-555-0100",
}


def test_render_opener_fills_tokens():
    out = render_opener("Hi {name} in {city} ({category}) — {website}", REC)
    assert out == "Hi Joe's Tacos in Austin (restaurant) — http://joes.com"


def test_render_opener_missing_token_is_blank():
    out = render_opener("Hi {name}, your site {website} and {nope} field", {"name": "Sam"})
    assert out == "Hi Sam, your site  and  field"
    # never raises on a fully empty record
    assert render_opener("{a} {b} {c}", {}) == "  "


def test_render_opener_none_value_renders_blank():
    out = render_opener("Site: {website}!", {"website": None})
    assert out == "Site: !"


def test_render_opener_malformed_braces_returned_as_is():
    tmpl = "Hello {name} and a stray { brace"
    # malformed format string is returned untouched rather than raising
    assert render_opener(tmpl, REC) == tmpl


def test_render_all_default_templates():
    out = render_all(REC)
    assert set(out.keys()) == set(DEFAULT_OPENERS.keys())
    assert "cold_email" in out
    # tokens actually substituted in the default templates
    assert "Joe's Tacos" in out["cold_email"]
    assert "Austin" in out["sms"]
    assert "{name}" not in out["cold_call"]


def test_render_all_custom_templates():
    out = render_all(REC, {"hi": "yo {name}", "loc": "{city}/{state}"})
    assert out == {"hi": "yo Joe's Tacos", "loc": "Austin/"}


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
