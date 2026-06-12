"""
Pure (no-network) tests for the data-source helpers: the Overpass query builder
(incl. the new key-only broad tags) and the Socrata row mapping.
Run:  python leadgen/tests/test_sources.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.sources import (_overpass_body, _socrata_map_row, _first_field,
                             _locality_terms, _city_state, _npi_map)

BBOX = (30.10, -97.95, 30.52, -97.55)


# ── Overpass query building ───────────────────────────────────────────────────

def test_overpass_key_value_filter():
    body = _overpass_body(BBOX, ["amenity=restaurant"])
    assert 'nwr["amenity"="restaurant"](30.1,-97.95,30.52,-97.55);' in body
    assert "out center tags;" in body


def test_overpass_key_only_requires_name():
    body = _overpass_body(BBOX, ["shop"])
    # key-only must pull ANY value of the key, but require a name
    assert 'nwr["shop"]["name"](30.1,-97.95,30.52,-97.55);' in body


def test_overpass_mixed_and_empty():
    body = _overpass_body(BBOX, ["shop", "office", "amenity=cafe"])
    assert body.count("nwr[") == 3
    assert _overpass_body(BBOX, []) == ""


# ── Socrata mapping ───────────────────────────────────────────────────────────

def test_socrata_maps_common_columns():
    row = {"business_name": "Joe's Tacos", "business_address": "1 Main St",
           "city": "Austin", "state": "TX", "zip_code": "78701", "phone": "5125550100"}
    rec = _socrata_map_row(row)
    assert rec["name"] == "Joe's Tacos"
    assert rec["city"] == "Austin" and rec["phone"] == "5125550100"
    assert rec["address"] == "1 Main St, Austin"
    assert rec["source"] == "socrata"


def test_socrata_uses_dba_and_location_dict():
    row = {"dba_name": "Bright Smile", "location": {"human_address": "55 Oak Ave"}}
    rec = _socrata_map_row(row)
    assert rec["name"] == "Bright Smile"
    # _first_field should unwrap a dict-valued location/address column
    assert "55 Oak Ave" in _first_field(row, ("address", "location"))


def test_socrata_skips_nameless_rows():
    assert _socrata_map_row({"city": "Austin"}) is None


def test_locality_terms():
    assert _locality_terms("Austin, Texas") == "Austin"
    assert _locality_terms("austin_tx") == "austin"
    assert _locality_terms("Boulder, Boulder County, Colorado, United States") == "Boulder"


# ── NPI registry mapping ──────────────────────────────────────────────────────

def test_city_state_parsing():
    assert _city_state("Austin, Texas") == ("Austin", "TX")
    assert _city_state("austin_tx") == ("austin", "TX")
    assert _city_state("Boulder, Boulder County, Colorado, USA") == ("Boulder", "CO")
    assert _city_state("Nowhere") == ("Nowhere", "")  # no resolvable state


def test_npi_map_org_provider():
    res = {
        "number": "1234567890",
        "basic": {"organization_name": "Cedar Dental Group"},
        "addresses": [
            {"address_purpose": "MAILING", "city": "X"},
            {"address_purpose": "LOCATION", "address_1": "12 Oak St",
             "city": "AUSTIN", "state": "TX", "postal_code": "787011234",
             "telephone_number": "512-555-0100"},
        ],
        "taxonomies": [{"desc": "Dentist", "primary": True}],
    }
    rec = _npi_map(res)
    assert rec["name"] == "Cedar Dental Group"
    assert rec["phone"] == "512-555-0100" and rec["city"] == "Austin"
    assert rec["zip"] == "78701" and rec["category"] == "Dentist"
    assert rec["website"] is None and rec["source"] == "npi"
    assert rec["source_url"].endswith("/1234567890")


def test_npi_map_individual_and_empty():
    res = {"number": "9", "basic": {"first_name": "Jane", "last_name": "Doe"},
           "addresses": [{"address_purpose": "LOCATION", "city": "Reno", "state": "NV"}]}
    assert _npi_map(res)["name"] == "Jane Doe"
    assert _npi_map({"basic": {}}) is None


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
