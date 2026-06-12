"""
Offline "recorded response" tests for the network data sources.

These cover the PARSING of each requests-based collector without touching the
internet: we monkeypatch requests.get / requests.post on the relevant module
(leadgen.sources.requests / leadgen.extra_sources.requests — both import
`requests` directly) to return small canned responses, then assert the
collectors normalize them into the expected lead dicts.

Every test restores the original requests functions in a `finally`, so a fake
never leaks into another test. To prove there is no network access, the runner
ALSO sets a global guard that raises if any un-patched requests.get/post is hit.

Run:  python leadgen/tests/test_sources_recorded.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen import sources as S
from leadgen import extra_sources as X


# ── fake Response + monkeypatch helpers ──────────────────────────────────────

class FakeResponse:
    """Minimal stand-in for a requests.Response: .status_code / .json() / .text."""

    def __init__(self, *, json_data=None, text="", status_code=200):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


def _make_get(responses):
    """Build a fake requests.get that returns canned responses in order.

    `responses` may be a single FakeResponse (always returned) or a list that is
    consumed one call at a time (the last one repeats once exhausted).
    """
    if isinstance(responses, FakeResponse):
        seq = [responses]
    else:
        seq = list(responses)
    calls = {"n": 0}

    def fake_get(url, *args, **kwargs):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]

    fake_get.calls = calls
    return fake_get


def _make_post(response):
    def fake_post(url, *args, **kwargs):
        return response
    return fake_post


# ── Socrata: catalog search JSON + dataset JSON ───────────────────────────────

def test_socrata_collect_catalog_then_dataset():
    # First requests.get -> catalog discovery; second -> the dataset rows.
    catalog = FakeResponse(json_data={"results": [
        {
            "metadata": {"domain": "data.austintexas.gov"},
            "resource": {"id": "abcd-1234", "name": "Austin Business Licenses"},
        },
        # noise row that must be filtered out (no domain/id)
        {"metadata": {}, "resource": {"name": "unrelated"}},
    ]})
    dataset = FakeResponse(json_data=[
        {"business_name": "Joe's Tacos", "address": "1 Main St",
         "city": "Austin", "state": "TX", "zip_code": "78701",
         "phone": "5125550100"},
        {"dba_name": "Bright Smile Dental", "city": "Austin"},
        {"city": "Austin"},  # nameless -> dropped
    ])
    orig = S.requests.get
    try:
        S.requests.get = _make_get([catalog, dataset])
        recs = S.socrata_collect("Austin, Texas", log=lambda *_: None)
    finally:
        S.requests.get = orig

    assert len(recs) == 2, recs
    by_name = {r["name"]: r for r in recs}
    assert "Joe's Tacos" in by_name and "Bright Smile Dental" in by_name
    joe = by_name["Joe's Tacos"]
    assert joe["city"] == "Austin"
    assert joe["phone"] == "5125550100"
    assert joe["source"] == "socrata"
    assert joe["source_url"] == "https://data.austintexas.gov/d/abcd-1234"


def test_socrata_collect_explicit_dataset_bypasses_catalog():
    # When datasets= is given, only the dataset read happens (one GET).
    dataset = FakeResponse(json_data=[
        {"company_name": "Acme LLC", "city": "Reno", "state": "NV"},
    ])
    orig = S.requests.get
    try:
        fake = _make_get(dataset)
        S.requests.get = fake
        recs = S.socrata_collect(
            "Reno, Nevada", log=lambda *_: None,
            datasets=[{"domain": "data.reno.gov", "id": "wxyz-9999"}],
        )
    finally:
        S.requests.get = orig

    assert len(recs) == 1
    assert recs[0]["name"] == "Acme LLC"
    assert recs[0]["source"] == "socrata"
    assert fake.calls["n"] == 1  # catalog search was bypassed


# ── NPI / NPPES JSON ──────────────────────────────────────────────────────────

def test_npi_collect_parses_nppes_json():
    page = FakeResponse(json_data={"results": [
        {
            "number": "1234567890",
            "basic": {"organization_name": "Cedar Dental Group"},
            "addresses": [
                {"address_purpose": "MAILING", "city": "Elsewhere"},
                {"address_purpose": "LOCATION", "address_1": "12 Oak St",
                 "city": "AUSTIN", "state": "TX", "postal_code": "787011234",
                 "telephone_number": "512-555-0100"},
            ],
            "taxonomies": [{"desc": "Dentist", "primary": True}],
        },
    ]})
    orig = S.requests.get
    try:
        # Same page for every call; the collector stops because len < 200.
        S.requests.get = _make_get(page)
        recs = S.npi_collect("Austin, Texas", limit=10, log=lambda *_: None)
    finally:
        S.requests.get = orig

    assert len(recs) == 1, recs
    r = recs[0]
    assert r["name"] == "Cedar Dental Group"
    assert r["phone"] == "512-555-0100"
    assert r["category"] == "Dentist"
    assert r["city"] == "Austin"
    assert r["zip"] == "78701"
    assert r["website"] is None
    assert r["source"] == "npi"
    assert r["source_url"].endswith("/1234567890")


# ── ArcGIS feature-service JSON ───────────────────────────────────────────────

def test_arcgis_collect_parses_features():
    feats = FakeResponse(json_data={"features": [
        {"attributes": {"business_name": "Lakeside Cafe", "city": "Boulder",
                        "state": "CO", "zip": "80301", "phone": "3035550100"}},
        {"attributes": {"licensee_name": "Mountain Spa", "city": "Boulder"}},
        {"attributes": {"city": "Boulder"}},  # nameless -> dropped
    ]})
    orig = S.requests.get
    try:
        S.requests.get = _make_get(feats)
        recs = S.arcgis_collect(
            "Boulder, Colorado", log=lambda *_: None,
            layers=["https://maps.example.gov/arcgis/rest/services/Lic/FeatureServer/0"],
        )
    finally:
        S.requests.get = orig

    assert len(recs) == 2, recs
    names = {r["name"] for r in recs}
    assert names == {"Lakeside Cafe", "Mountain Spa"}
    for r in recs:
        assert r["source"] == "arcgis"
        assert r["category"] == "business license"
        assert r["source_url"].endswith("/FeatureServer/0")
    cafe = next(r for r in recs if r["name"] == "Lakeside Cafe")
    assert cafe["city"] == "Boulder"
    assert cafe["phone"] == "3035550100"


# ── OSM via Overpass (requests.post) ──────────────────────────────────────────

def test_osm_collect_parses_overpass_elements():
    elements = FakeResponse(json_data={"elements": [
        {
            "type": "node", "id": 111, "lat": 30.27, "lon": -97.74,
            "tags": {
                "name": "Franklin BBQ", "amenity": "restaurant",
                "addr:housenumber": "900", "addr:street": "E 11th St",
                "addr:city": "Austin", "addr:state": "TX",
                "addr:postcode": "78702", "phone": "512-555-0199",
                "website": "https://franklinbbq.example",
            },
        },
        {
            "type": "way", "id": 222,
            "center": {"lat": 30.30, "lon": -97.70},
            "tags": {"operator": "Tiny Shop", "shop": "convenience"},
        },
        {"type": "node", "id": 333, "tags": {"amenity": "bench"}},  # no name -> dropped
    ]})
    orig = S.requests.post
    try:
        S.requests.post = _make_post(elements)
        recs = S.osm_collect(
            (30.10, -97.95, 30.52, -97.55), ["amenity=restaurant", "shop"],
            log=lambda *_: None,
        )
    finally:
        S.requests.post = orig

    assert len(recs) == 2, recs
    by_name = {r["name"]: r for r in recs}
    assert "Franklin BBQ" in by_name
    assert "Tiny Shop" in by_name  # name falls back to `operator`
    fb = by_name["Franklin BBQ"]
    assert fb["category"] == "restaurant"
    assert fb["phone"] == "512-555-0199"
    assert fb["website"] == "https://franklinbbq.example"
    assert fb["city"] == "Austin"
    assert fb["lat"] == 30.27 and fb["lon"] == -97.74
    assert fb["source"] == "osm"
    assert fb["source_url"] == "https://www.openstreetmap.org/node/111"
    shop = by_name["Tiny Shop"]
    assert shop["category"] == "convenience"
    assert shop["lat"] == 30.30  # pulled from `center`
    assert shop["source_url"] == "https://www.openstreetmap.org/way/222"


# ── extra_sources.url_csv_collect (requests.get -> CSV text) ──────────────────

def test_url_csv_collect_parses_csv_text():
    csv_text = (
        "business_name,address,city,state,zip,phone\r\n"
        "Joe's Tacos,1 Main St,Austin,TX,78701,5125550100\r\n"
        "Bright Smile,55 Oak Ave,Austin,TX,78702,5125550101\r\n"
        ",,,,,\r\n"  # blank/nameless row -> dropped
    )
    resp = FakeResponse(text=csv_text)
    orig = X.requests.get
    try:
        X.requests.get = _make_get(resp)
        recs = X.url_csv_collect("https://example.org/biz.csv", log=lambda *_: None)
    finally:
        X.requests.get = orig

    assert len(recs) == 2, recs
    names = {r["name"] for r in recs}
    assert names == {"Joe's Tacos", "Bright Smile"}
    for r in recs:
        assert r["source"] == "url_csv"
        assert r["source_url"] == "https://example.org/biz.csv"
        assert r["city"] == "Austin"


# ── BONUS: Wikidata SPARQL JSON ───────────────────────────────────────────────

def test_wikidata_collect_parses_sparql_json():
    resp = FakeResponse(json_data={"results": {"bindings": [
        {
            "item": {"value": "http://www.wikidata.org/entity/Q42"},
            "itemLabel": {"value": "Sample Museum"},
            "website": {"value": "https://museum.example"},
            "coord": {"value": "Point(-97.74 30.27)"},
        },
        # unlabeled item: label fell back to the Q-id -> dropped
        {
            "item": {"value": "http://www.wikidata.org/entity/Q99"},
            "itemLabel": {"value": "Q99"},
            "website": {"value": "https://nope.example"},
            "coord": {"value": "Point(-97.7 30.3)"},
        },
    ]}})
    orig = X.requests.get
    try:
        X.requests.get = _make_get(resp)
        recs = X.wikidata_collect((30.10, -97.95, 30.52, -97.55), log=lambda *_: None)
    finally:
        X.requests.get = orig

    assert len(recs) == 1, recs
    r = recs[0]
    assert r["name"] == "Sample Museum"
    assert r["website"] == "https://museum.example"
    assert r["lat"] == 30.27 and r["lon"] == -97.74
    assert r["source"] == "wikidata"
    assert r["source_url"] == "http://www.wikidata.org/entity/Q42"


# ── BONUS: data.gov CKAN JSON (package_search + datastore_search) ─────────────

def test_ckan_collect_parses_package_and_datastore():
    package_search = FakeResponse(json_data={"result": {"results": [
        {
            "name": "austin-business-licenses",
            "title": "Austin Business Licenses",
            "resources": [
                {"id": "res-1", "format": "CSV", "datastore_active": True},
            ],
        },
    ]}})
    datastore = FakeResponse(json_data={"result": {"records": [
        {"business_name": "Joe's Tacos", "city": "Austin", "state": "TX"},
        {"company_name": "Acme LLC", "city": "Austin"},
        {"city": "Austin"},  # nameless -> dropped
    ]}})
    orig = X.requests.get
    try:
        X.requests.get = _make_get([package_search, datastore])
        recs = X.ckan_collect("Austin", log=lambda *_: None)
    finally:
        X.requests.get = orig

    assert len(recs) == 2, recs
    names = {r["name"] for r in recs}
    assert names == {"Joe's Tacos", "Acme LLC"}
    for r in recs:
        assert r["source"] == "ckan"
        assert r["source_url"] == "https://catalog.data.gov/dataset/austin-business-licenses"


# ── runner with a hard no-network guard ───────────────────────────────────────

def _install_network_guard():
    """Replace requests.get/post on both modules with a guard that raises.

    Each test installs its OWN fake over these, so a properly-patched test never
    triggers the guard. If any code path reaches an un-patched requests call, the
    guard fires and the test ERRORs — proving the offline coverage is real.
    """
    def boom(*_a, **_k):
        raise AssertionError("network access attempted (requests not patched)")

    for mod in (S, X):
        mod.requests.get = boom
        mod.requests.post = boom


def _run_all():
    # Snapshot originals, install the global guard, run, then restore.
    saved = {
        "s_get": S.requests.get, "s_post": S.requests.post,
        "x_get": X.requests.get, "x_post": X.requests.post,
    }
    _install_network_guard()
    try:
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
    finally:
        S.requests.get, S.requests.post = saved["s_get"], saved["s_post"]
        X.requests.get, X.requests.post = saved["x_get"], saved["x_post"]


if __name__ == "__main__":
    raise SystemExit(_run_all())
