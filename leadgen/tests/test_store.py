"""
Pure (offline) tests for leadgen.store.RunStore: save→get round-trips leads+meta,
list_runs reflects saved runs. Uses a temp db file + an injected clock.
Run:  python leadgen/tests/test_store.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.store import RunStore


def _tmp_db():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    os.unlink(path)  # let RunStore create it fresh
    return path


def test_save_then_get_roundtrips():
    path = _tmp_db()
    try:
        store = RunStore(path, now=lambda: "2026-06-11T00:00:00+00:00")
        leads = [{"name": "Joe's Tacos", "score": 91, "tier": "A", "why": ["no site"]},
                 {"name": "Bright Smile", "score": 40, "tier": "C"}]
        meta = {"vertical": "web_design", "market": "austin_tx", "sources": ["osm"]}
        rid = store.save_run(meta, leads)
        assert isinstance(rid, int) and rid >= 1

        got = store.get_run(rid)
        assert got is not None
        assert got["leads"] == leads               # full round-trip
        assert got["meta"]["vertical"] == "web_design"
        assert got["meta"]["sources"] == ["osm"]
    finally:
        os.path.exists(path) and os.unlink(path)


def test_list_runs_reports_saved_run():
    path = _tmp_db()
    try:
        store = RunStore(path, now=lambda: "2026-06-11T12:00:00+00:00")
        store.save_run({"vertical": "seo_audit", "market": "reno_nv"},
                       [{"name": "A"}, {"name": "B"}, {"name": "C"}])
        runs = store.list_runs()
        assert len(runs) == 1
        r = runs[0]
        assert r["vertical"] == "seo_audit" and r["market"] == "reno_nv"
        assert r["total"] == 3
        assert r["when"] == "2026-06-11T12:00:00+00:00"
        assert isinstance(r["id"], int)
    finally:
        os.path.exists(path) and os.unlink(path)


def test_list_runs_newest_first_and_get_missing():
    path = _tmp_db()
    try:
        store = RunStore(path, now=lambda: "2026-06-11T00:00:00+00:00")
        r1 = store.save_run({"market": "m1"}, [{"name": "x"}])
        r2 = store.save_run({"market": "m2"}, [{"name": "y"}])
        runs = store.list_runs()
        assert [r["id"] for r in runs] == [r2, r1]   # newest first
        assert store.get_run(999999) is None         # missing id
    finally:
        os.path.exists(path) and os.unlink(path)


def test_explicit_when_in_meta_wins():
    path = _tmp_db()
    try:
        store = RunStore(path, now=lambda: "INJECTED")
        rid = store.save_run({"when": "EXPLICIT", "market": "m"}, [])
        assert store.list_runs()[0]["when"] == "EXPLICIT"
        assert store.get_run(rid)["leads"] == []
        assert store.list_runs()[0]["total"] == 0
    finally:
        os.path.exists(path) and os.unlink(path)


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
