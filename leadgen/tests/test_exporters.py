"""
Pure tests for the extra output formats in leadgen.exporters.
Each test writes into a tempfile/tempdir and asserts on the content.
Run:  python leadgen/tests/test_exporters.py
"""
import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.exporters import (
    write_jsonl, write_json, write_vcard, write_per_tier,
    write_markdown_report, write_crm_csv, CRM_HEADER_PRESETS,
)

COLUMNS = [
    ("Name", "name"), ("Tier", "tier"), ("Score", "score"),
    ("City", "city"), ("Phone", "phone"), ("Website", "website"),
    ("Why", "why"),
]

LEADS = [
    {"name": "Joe's Tacos", "tier": "A", "score": 92, "city": "Austin",
     "phone": "512-555-0100", "website": "http://joes.com", "email": "joe@joes.com",
     "address": "1 Main St, Austin", "state": "TX", "zip": "78701",
     "why": "great fit"},
    {"name": "Bright Smile", "tier": "B", "score": 70, "city": "Reno",
     "phone": "", "website": "", "email": "", "address": "", "why": "maybe"},
    {"name": "Cedar Dental", "tier": "C", "score": 40, "city": "Boulder",
     "phone": "303-555-0199", "website": "http://cedar.com",
     "address": "12 Oak St", "why": "low"},
    {"name": "Acme A2", "tier": "A", "score": 88, "city": "Austin",
     "why": "second A"},
]


def test_jsonl_line_count_and_keys():
    with tempfile.TemporaryDirectory() as d:
        p = write_jsonl(LEADS, COLUMNS, os.path.join(d, "out.jsonl"))
        lines = [ln for ln in open(p, encoding="utf-8").read().splitlines() if ln]
        assert len(lines) == len(LEADS)
        first = json.loads(lines[0])
        assert first["name"] == "Joe's Tacos" and first["tier"] == "A"
        # only column keys are projected
        assert set(first.keys()) == {k for _, k in COLUMNS}


def test_json_is_array():
    with tempfile.TemporaryDirectory() as d:
        p = write_json(LEADS, COLUMNS, os.path.join(d, "out.json"))
        data = json.load(open(p, encoding="utf-8"))
        assert isinstance(data, list) and len(data) == len(LEADS)
        assert data[2]["name"] == "Cedar Dental"


def test_vcard_structure_and_skips_empty():
    with tempfile.TemporaryDirectory() as d:
        p = write_vcard(LEADS, os.path.join(d, "out.vcf"))
        text = open(p, encoding="utf-8").read()
        assert "BEGIN:VCARD" in text and "END:VCARD" in text
        assert text.count("BEGIN:VCARD") == len(LEADS)
        assert "FN:Joe's Tacos" in text
        assert "TEL:512-555-0100" in text
        assert "EMAIL:joe@joes.com" in text
        assert "URL:http://joes.com" in text
        assert "1 Main St, Austin" in text
        # Bright Smile has no phone/email/website/address -> none for it
        bright = text.split("END:VCARD")[1]
        assert "FN:Bright Smile" in bright
        assert "TEL:" not in bright and "URL:" not in bright


def test_per_tier_makes_three_files():
    with tempfile.TemporaryDirectory() as d:
        stem = os.path.join(d, "leads")
        out = write_per_tier(LEADS, COLUMNS, stem)
        assert set(out.keys()) == {"A", "B", "C"}
        for tier, path in out.items():
            assert os.path.exists(path)
            assert path.endswith(f"_{tier}.csv")
        # Tier A has 2 leads -> header + 2 rows = 3 lines
        rows = list(csv.reader(open(out["A"], encoding="utf-8")))
        assert len(rows) == 3
        assert rows[0] == [h for h, _ in COLUMNS]


def test_markdown_has_headers_and_table():
    with tempfile.TemporaryDirectory() as d:
        stem = os.path.join(d, "report")
        p = write_markdown_report(LEADS, stem, title="My Leads")
        assert p.endswith(".md")
        text = open(p, encoding="utf-8").read()
        assert "# My Leads" in text
        assert "## Counts per tier" in text
        assert "## Top 25 leads" in text
        assert "- Tier A: 2" in text
        assert "| name | tier |" in text or "| name |" in text
        # top lead by score should appear
        assert "Joe's Tacos" in text


def test_crm_csv_uses_preset_headers():
    with tempfile.TemporaryDirectory() as d:
        p = write_crm_csv(LEADS, os.path.join(d, "hub.csv"), "hubspot")
        rows = list(csv.reader(open(p, encoding="utf-8")))
        header = rows[0]
        assert "Company Name" in header
        assert "Phone Number" in header
        assert "Postal Code" in header
        # data row carries the value under the renamed column
        idx = header.index("Company Name")
        assert rows[1][idx] == "Joe's Tacos"


def test_crm_presets_exist():
    assert set(CRM_HEADER_PRESETS) >= {"hubspot", "pipedrive", "mailchimp"}
    with tempfile.TemporaryDirectory() as d:
        p = write_crm_csv(LEADS, os.path.join(d, "pd.csv"), "pipedrive")
        header = next(csv.reader(open(p, encoding="utf-8")))
        assert "Organization" in header


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
