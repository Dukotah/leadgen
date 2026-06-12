"""
Pure (no-network) tests for the *new* data-quality helpers in leadgen.quality:
parse_address, is_closed, looks_like_chain, field_confidence,
load_do_not_contact, filter_new.
Run:  python leadgen/tests/test_quality2.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.quality import (parse_address, is_closed, looks_like_chain,
                             field_confidence, load_do_not_contact, filter_new,
                             dedupe_key)


# ── parse_address ─────────────────────────────────────────────────────────────

def test_parse_address_full():
    p = parse_address("123 Main St, Austin, TX 78701")
    assert p["street"] == "123 Main St"
    assert p["city"] == "Austin"
    assert p["state"] == "TX"
    assert p["zip"] == "78701"


def test_parse_address_zip_plus_four_and_lower_state():
    p = parse_address("55 Oak Ave, Reno, nv 89501-1234")
    assert p["state"] == "NV"
    assert p["zip"] == "89501"
    assert p["city"] == "Reno"


def test_parse_address_partial_and_missing():
    p = parse_address("Just a street name")
    assert p["street"] == "Just a street name"
    assert p["state"] == "" and p["zip"] == "" and p["city"] == ""
    empty = parse_address("")
    assert empty == {"street": "", "city": "", "state": "", "zip": ""}
    assert parse_address(None)["zip"] == ""


def test_parse_address_does_not_treat_street_word_as_state():
    # "St" is a 2-letter token but not a US state abbreviation.
    p = parse_address("100 St James Pl, Dallas, TX 75201")
    assert p["state"] == "TX"


# ── is_closed ─────────────────────────────────────────────────────────────────

def test_is_closed_flags_and_phrases():
    assert is_closed({"closed": True})
    assert is_closed({"date_closed": "2024-01-01"})
    assert is_closed({"name": "Old Diner (closed)"})
    assert is_closed({"category": "disused:restaurant"})
    assert is_closed({"source_url": "http://x/abandoned/123"})
    assert is_closed({"name": "Foo", "category": "Permanently Closed"})


def test_is_closed_open_business():
    assert not is_closed({"name": "Cedar Dental Group", "category": "Dentist"})
    assert not is_closed({})
    assert not is_closed(None)


# ── looks_like_chain ──────────────────────────────────────────────────────────

def test_looks_like_chain_brand_field_and_default_list():
    assert looks_like_chain({"name": "Whatever", "brand": "Acme"})
    assert looks_like_chain({"name": "McDonald's"})
    assert looks_like_chain({"name": "Subway"})


def test_looks_like_chain_store_number_pattern():
    assert looks_like_chain({"name": "Subway #2031"})
    assert looks_like_chain({"name": "Quik Mart Store #14"})


def test_looks_like_chain_custom_brands_and_independent():
    assert looks_like_chain({"name": "Joe's Tacos"}, brands={"Joe's Tacos"})
    assert not looks_like_chain({"name": "Cedar Dental Group"})
    assert not looks_like_chain({})


# ── field_confidence ──────────────────────────────────────────────────────────

def test_field_confidence_verified():
    rec = {"name": "Cedar Dental Group", "website": "https://cedar.example",
           "phone": "+15125550100", "email": "hi@cedar.example",
           "address": "12 Oak St, Austin, TX 78701"}
    fc = field_confidence(rec)
    assert fc == {"name": "verified", "website": "verified", "phone": "verified",
                  "email": "verified", "address": "verified"}


def test_field_confidence_missing_and_guessed():
    rec = {"name": "x", "website": "", "phone": "call us",
           "email": "not-an-email", "address": ""}
    fc = field_confidence(rec)
    assert fc["name"] == "guessed"      # junk-ish but present
    assert fc["website"] == "missing"
    assert fc["phone"] == "guessed"     # present, not normalizable
    assert fc["email"] == "guessed"     # present, no valid shape
    assert fc["address"] == "missing"


def test_field_confidence_robust_to_empty():
    fc = field_confidence({})
    assert set(fc.values()) == {"missing"}
    assert field_confidence(None)["name"] == "missing"


# ── load_do_not_contact ───────────────────────────────────────────────────────

def test_load_do_not_contact_from_text():
    csv_text = "Company Name,City\nJoe's Tacos LLC,Austin\nCedar Dental Group,Austin\n"
    dnc = load_do_not_contact(csv_text, is_text=True)
    assert "joestacos" in dnc
    assert "cedardental" in dnc


def test_load_do_not_contact_first_column_fallback_and_empty():
    csv_text = "foo,bar\nAcme Realty,x\n"
    dnc = load_do_not_contact(csv_text, is_text=True)
    assert "acme" in dnc            # norm strips 'realty'
    assert load_do_not_contact("", is_text=True) == set()
    assert load_do_not_contact("only_header\n", is_text=True) == set()


# ── filter_new ────────────────────────────────────────────────────────────────

def test_filter_new_drops_seen_keys():
    records = [
        {"name": "Alpha Co", "phone": "5125550100"},
        {"name": "Beta Co", "phone": "5125550199"},
    ]
    seen = {dedupe_key(records[0])}
    out = filter_new(records, seen)
    assert [r["name"] for r in out] == ["Beta Co"]


def test_filter_new_keeps_all_when_empty_seen_and_order():
    records = [{"name": "A", "phone": "5125550100"},
               {"name": "B", "phone": "5125550199"}]
    out = filter_new(records, set())
    assert [r["name"] for r in out] == ["A", "B"]


def test_filter_new_robust_to_empty_keys():
    # records with no usable key are never dropped (empty key == never-seen)
    out = filter_new([{}, {"name": "Solo Biz"}], {""})
    assert len(out) == 2


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
