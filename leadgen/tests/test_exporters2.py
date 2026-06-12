"""
Pure tests for the second batch of leadgen.exporters helpers:
write_tsv, append_to_master, run_completion_hook.
Run:  python leadgen/tests/test_exporters2.py
"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.exporters import write_tsv, append_to_master, run_completion_hook

COLUMNS = [
    ("Name", "name"), ("Tier", "tier"), ("City", "city"), ("Phone", "phone"),
]

LEADS = [
    {"name": "Joe's Tacos", "tier": "A", "city": "Austin", "phone": "512-555-0100"},
    {"name": "Bright Smile", "tier": "B", "city": "Reno", "phone": ""},
]


def test_tsv_content_is_tab_separated():
    with tempfile.TemporaryDirectory() as d:
        p = write_tsv(LEADS, COLUMNS, os.path.join(d, "out.tsv"))
        lines = open(p, encoding="utf-8").read().splitlines()
        assert lines[0] == "Name\tTier\tCity\tPhone"
        assert lines[1] == "Joe's Tacos\tA\tAustin\t512-555-0100"
        assert len(lines) == len(LEADS) + 1


def test_tsv_strips_tabs_and_newlines():
    with tempfile.TemporaryDirectory() as d:
        rec = [{"name": "A\tB", "tier": "x\ny", "city": "", "phone": ""}]
        p = write_tsv(rec, COLUMNS, os.path.join(d, "dirty.tsv"))
        lines = open(p, encoding="utf-8").read().splitlines()
        # header + exactly one data line (no embedded newline split it)
        assert len(lines) == 2
        assert lines[1] == "A B\tx y\t\t"


def test_append_to_master_adds_then_dedupes():
    with tempfile.TemporaryDirectory() as d:
        master = os.path.join(d, "master.csv")
        # first call: file doesn't exist -> created with header + 2 rows
        added1 = append_to_master(LEADS, COLUMNS, master)
        assert added1 == 2
        assert os.path.exists(master)

        # second call: same two leads + one new -> only the new one is added
        batch2 = LEADS + [
            {"name": "Cedar Dental", "tier": "C", "city": "Boulder", "phone": "303-555-0199"},
        ]
        added2 = append_to_master(batch2, COLUMNS, master)
        assert added2 == 1

        rows = list(csv.reader(open(master, encoding="utf-8")))
        assert rows[0] == ["Name", "Tier", "City", "Phone"]
        # header + 3 unique data rows
        assert len(rows) == 4
        names = [r[0] for r in rows[1:]]
        assert names == ["Joe's Tacos", "Bright Smile", "Cedar Dental"]


def test_append_to_master_custom_key_fn():
    with tempfile.TemporaryDirectory() as d:
        master = os.path.join(d, "m.csv")
        key = lambda r: (r.get("city") or "").lower()
        a = [{"name": "X", "tier": "A", "city": "Austin", "phone": "1"},
             {"name": "Y", "tier": "B", "city": "Austin", "phone": "2"}]
        # both share city "Austin" -> only first kept
        assert append_to_master(a, COLUMNS, master, key_fn=key) == 1


def test_run_completion_hook_success():
    rc = run_completion_hook(sys.executable + " -c \"import sys,json; json.load(sys.stdin)\"",
                             {"total": 3, "tier_a": 1})
    assert rc == 0


def test_run_completion_hook_bad_command_no_raise():
    # a command that exits nonzero must return nonzero (or -1) without raising
    rc = run_completion_hook(sys.executable + " -c \"import sys; sys.exit(7)\"", {})
    assert rc != 0
    # empty command -> -1, no raise
    assert run_completion_hook("", {"x": 1}) == -1


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
