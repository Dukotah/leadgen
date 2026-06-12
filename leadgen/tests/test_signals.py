"""
Pure (no-network) tests for the website-signal helpers in leadgen/signals.py.
Every function is exercised against small inline HTML fixtures; domain_resolves
is only asserted to return a bool and never raise (no network dependency).
Run:  python leadgen/tests/test_signals.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.signals import (find_emails, copyright_year, has_ecommerce,
                             has_booking, detect_socials, domain_resolves)


# ── find_emails ───────────────────────────────────────────────────────────────

def test_emails_basic_and_dedup():
    html = '''Reach us at <a href="mailto:info@acme.com">info@acme.com</a>
              or info@acme.com again, plus jane@acme.com.'''
    out = find_emails(html)
    assert "info@acme.com" in out
    assert "jane@acme.com" in out
    assert out.count("info@acme.com") == 1  # de-duplicated


def test_emails_best_first():
    html = "zach@acme.com hello@acme.com random@acme.com info@acme.com"
    out = find_emails(html)
    # info@ / hello@ preferred over personal addresses
    assert out[0] in ("info@acme.com", "hello@acme.com")
    assert out.index("info@acme.com") < out.index("zach@acme.com")


def test_emails_filters_junk():
    html = '''noreply@acme.com sentry@sentry.io foo@example.com
              logo@2x.png banner@3x.jpg postmaster@acme.com
              real@goodbiz.com hello@goodbiz.com'''
    out = find_emails(html)
    assert "real@goodbiz.com" in out and "hello@goodbiz.com" in out
    for junk in ("noreply@acme.com", "sentry@sentry.io", "foo@example.com",
                 "logo@2x.png", "banner@3x.jpg", "postmaster@acme.com"):
        assert junk not in out, junk


def test_emails_empty_and_none():
    assert find_emails("") == []
    assert find_emails(None) == []
    assert find_emails("no addresses here at all") == []


# ── copyright_year ────────────────────────────────────────────────────────────

def test_copyright_symbol_and_word():
    assert copyright_year("<footer>© 2019 Acme Inc.</footer>") == 2019
    assert copyright_year("Copyright 2021 Widgets LLC") == 2021
    assert copyright_year("&copy; 2018 Foo") == 2018


def test_copyright_range_and_most_recent():
    assert copyright_year("© 2019-2024 Acme") == 2024
    # most recent across multiple matches
    assert copyright_year("© 2010 ... footer © 2023 Acme") == 2023


def test_copyright_none_and_implausible():
    assert copyright_year("") is None
    assert copyright_year(None) is None
    assert copyright_year("no year here") is None
    assert copyright_year("© 1850 antique") is None  # < 1990, rejected


# ── has_ecommerce ─────────────────────────────────────────────────────────────

def test_ecommerce_positive():
    assert has_ecommerce('<script src="https://cdn.shopify.com/x.js"></script>')
    assert has_ecommerce("<button>Add to Cart</button>")
    assert has_ecommerce("powered by WooCommerce")
    assert has_ecommerce('<a href="/cart">View Cart</a>')


def test_ecommerce_negative():
    assert not has_ecommerce("<h1>About our law firm</h1>")
    assert not has_ecommerce("")
    assert not has_ecommerce(None)


# ── has_booking ───────────────────────────────────────────────────────────────

def test_booking_positive():
    assert has_booking('<a href="https://calendly.com/acme">Schedule</a>')
    assert has_booking("<button>Book Now</button>")
    assert has_booking("Schedule an appointment today")
    assert has_booking('<iframe src="https://acuityscheduling.com/x"></iframe>')
    assert has_booking('<a href="https://www.opentable.com/r/acme">Reserve</a>')


def test_booking_negative():
    assert not has_booking("<p>Open Monday to Friday, 9 to 5.</p>")
    assert not has_booking("")
    assert not has_booking(None)


# ── detect_socials ────────────────────────────────────────────────────────────

def test_socials_found():
    html = '''
      <a href="https://www.facebook.com/AcmeTacos">fb</a>
      <a href="https://instagram.com/acmetacos">ig</a>
      <a href="https://www.linkedin.com/company/acme-tacos">li</a>
      <a href="https://twitter.com/acmetacos">tw</a>
      <a href="https://www.tiktok.com/@acmetacos">tt</a>
      <a href="https://youtube.com/c/AcmeTacos">yt</a>
    '''
    s = detect_socials(html)
    assert s["facebook"] == "AcmeTacos"
    assert s["instagram"] == "acmetacos"
    assert s["linkedin"] == "company/acme-tacos"
    assert s["twitter"] == "acmetacos"
    assert s["tiktok"] == "@acmetacos"
    assert s["youtube"] == "c/AcmeTacos"


def test_socials_skips_share_buttons():
    html = '''<a href="https://www.facebook.com/sharer.php?u=x">share</a>
              <a href="https://twitter.com/intent/tweet?text=hi">tweet</a>'''
    s = detect_socials(html)
    assert s["facebook"] is None
    assert s["twitter"] is None


def test_socials_keys_and_empty():
    s = detect_socials("")
    assert set(s.keys()) == {"facebook", "instagram", "linkedin",
                             "twitter", "tiktok", "youtube"}
    assert all(v is None for v in s.values())
    # None input must not raise
    assert all(v is None for v in detect_socials(None).values())


# ── domain_resolves ───────────────────────────────────────────────────────────

def test_domain_resolves_returns_bool_no_raise():
    # Never raises; always a bool — for garbage, www-form, scheme, bare host.
    for arg in ("", None, "not a domain!!!", "http://example.com",
                "www.example.com", "definitely-not-a-real-domain-xyz123.invalid"):
        assert isinstance(domain_resolves(arg), bool)


def test_domain_resolves_garbage_is_false():
    assert domain_resolves("") is False
    assert domain_resolves(None) is False
    assert domain_resolves("###@@@") is False


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
