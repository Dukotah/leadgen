"""
Offline (no-network) tests for leadgen.extra_sources.

Covers:
  - localfile_collect against a temp CSV and a temp XLSX (openpyxl).
  - the pure column mapper (map_business_rows) via in-memory dict rows.
  - wikidata_collect / ckan_collect return a list (not crash) on garbage input,
    with the network call patched so the test never touches the wire.
Run:  python leadgen/tests/test_extra_sources.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen import extra_sources
from leadgen.extra_sources import (localfile_collect, url_csv_collect,
                                   wikidata_collect, ckan_collect,
                                   map_business_rows)

BBOX = (30.10, -97.95, 30.52, -97.55)


def _quiet(*_a, **_k):
    pass


# ── pure column mapper ────────────────────────────────────────────────────────

def test_map_business_rows_maps_aliases():
    rows = [
        {"business_name": "Joe's Tacos", "business_address": "1 Main St",
         "city": "Austin", "state": "TX", "zip_code": "78701", "phone": "5125550100"},
        {"city": "Austin"},  # nameless -> dropped
    ]
    out = map_business_rows(rows, source="localfile", source_url="x.csv")
    assert len(out) == 1
    rec = out[0]
    assert rec["name"] == "Joe's Tacos"
    assert rec["city"] == "Austin" and rec["phone"] == "5125550100"
    assert rec["address"] == "1 Main St, Austin"
    assert rec["source"] == "localfile" and rec["source_url"] == "x.csv"


def test_map_business_rows_limit_and_nondict():
    rows = [{"name": "A"}, "garbage", {"name": "B"}, {"name": "C"}]
    out = map_business_rows(rows, source="url_csv", limit=2)
    assert len(out) == 2
    assert [r["name"] for r in out] == ["A", "B"]


# ── localfile_collect: CSV ────────────────────────────────────────────────────

def test_localfile_csv():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "biz.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("business_name,phone,city,state\n")
            fh.write("Cedar Dental,5125550100,Austin,TX\n")
            fh.write("Lone Star Plumbing,5125550199,Round Rock,TX\n")
        out = localfile_collect(path, log=_quiet)
        assert len(out) == 2
        assert out[0]["name"] == "Cedar Dental"
        assert out[0]["phone"] == "5125550100"
        assert out[0]["city"] == "Austin"
        assert out[0]["source"] == "localfile"


def test_localfile_csv_limit():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "biz.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write("name,city\nA,Austin\nB,Austin\nC,Austin\n")
        out = localfile_collect(path, limit=2, log=_quiet)
        assert len(out) == 2


# ── localfile_collect: XLSX (openpyxl) ────────────────────────────────────────

def test_localfile_xlsx():
    import openpyxl
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "biz.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["business_name", "phone", "city", "state"])
        ws.append(["Bright Smile", "5125550123", "Austin", "TX"])
        ws.append(["Hill Country HVAC", "5125550124", "Buda", "TX"])
        wb.save(path)
        out = localfile_collect(path, log=_quiet)
        assert len(out) == 2
        assert out[0]["name"] == "Bright Smile"
        assert out[0]["phone"] == "5125550123"
        assert out[0]["city"] == "Austin"
        assert out[1]["name"] == "Hill Country HVAC"


# ── failure-soft paths ────────────────────────────────────────────────────────

def test_localfile_missing_file_returns_list():
    out = localfile_collect("does/not/exist.csv", log=_quiet)
    assert out == []


def test_localfile_bad_extension_returns_list():
    out = localfile_collect("whatever.pdf", log=_quiet)
    assert out == []


def test_url_csv_empty_url():
    assert url_csv_collect("", log=_quiet) == []


# ── network-dependent collectors: patched so no real network is used ──────────

class _FakeResp:
    def __init__(self, status=500, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


def _patch_requests_get(monkey_value):
    """Swap extra_sources.requests.get; return the original to restore."""
    orig = extra_sources.requests.get
    extra_sources.requests.get = monkey_value
    return orig


def test_wikidata_garbage_returns_list():
    # Network "fails" -> []. Patch so no real request goes out.
    def boom(*_a, **_k):
        raise extra_sources.requests.exceptions.RequestException("no network")
    orig = _patch_requests_get(boom)
    try:
        out = wikidata_collect(BBOX, limit=5, log=_quiet)
        assert isinstance(out, list) and out == []
        # bad bbox also yields a list, not a crash
        assert wikidata_collect("garbage", log=_quiet) == []
    finally:
        extra_sources.requests.get = orig


def test_wikidata_non200_returns_list():
    orig = _patch_requests_get(lambda *_a, **_k: _FakeResp(status=503))
    try:
        assert wikidata_collect(BBOX, log=_quiet) == []
    finally:
        extra_sources.requests.get = orig


def test_ckan_garbage_returns_list():
    def boom(*_a, **_k):
        raise extra_sources.requests.exceptions.RequestException("no network")
    orig = _patch_requests_get(boom)
    try:
        out = ckan_collect("Zzqqx Nowhere", log=_quiet)
        assert isinstance(out, list) and out == []
        # empty place label -> [] without any request
        assert ckan_collect("", log=_quiet) == []
    finally:
        extra_sources.requests.get = orig


def test_ckan_empty_results_returns_list():
    orig = _patch_requests_get(
        lambda *_a, **_k: _FakeResp(status=200, payload={"result": {"results": []}}))
    try:
        assert ckan_collect("Austin", log=_quiet) == []
    finally:
        extra_sources.requests.get = orig


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
