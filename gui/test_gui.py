"""
Offline end-to-end test for the GUI: boots the Flask app via its test client,
monkeypatches the network collectors, runs a job, polls progress, and downloads
both output files — the exact request flow the browser uses. No network needed.

Run:  python gui/test_gui.py
Skips cleanly (exit 0) if Flask isn't installed.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "gui"))

try:
    import flask  # noqa: F401
except ImportError:
    print("SKIP gui test — Flask not installed (pip install -r gui/requirements.txt)")
    raise SystemExit(0)

import leadgen
import leadgen.sources as sources
import leadgen.pipeline as pipeline

_FAKE = [
    {"name": "Coastal Cafe", "category": "restaurant",
     "website": "http://coastalcafe.example", "phone": "707-555-0101", "email": "",
     "address": "1 Main St", "city": "Boulder", "state": "CO", "zip": "80302",
     "brand": "", "lat": 40.0, "lon": -105.2, "source": "overture", "source_url": ""},
    {"name": "Summit Plumbing", "category": "plumber", "website": "",
     "phone": "707-555-0102", "email": "", "address": "2 Oak Ave", "city": "Austin",
     "state": "TX", "zip": "78705", "brand": "", "lat": 30.2, "lon": -97.7,
     "source": "overture", "source_url": ""},
]


def _fake_overture(bbox, categories=None, limit=None, log=print):
    log(f"  [fake] {len(_FAKE)} businesses (offline test)")
    return [dict(r) for r in _FAKE]


def _fake_enrich(rec, ctx):
    """Stand in for the live website audit so the test needs no network."""
    if rec.get("website"):
        rec["audit"] = {"reachable": True, "https": rec["website"].startswith("https"),
                        "mobile_viewport": True, "builder": "", "load_ms": 800}
    return rec


def main():
    sources.overture_collect = _fake_overture
    pipeline.overture_collect = _fake_overture
    leadgen.get_vertical("web_design").enrich_fn = _fake_enrich

    import app as gui
    client = gui.app.test_client()

    r = client.get("/")
    assert r.status_code == 200 and b"web_design" in r.data
    print("PASS index renders")

    r = client.post("/run", json={"vertical": "web_design", "market": "austin_tx",
                                   "sources": ["overture"], "enrich": True, "enrich_cap": 50})
    jid = r.get_json()["job_id"]

    for _ in range(60):
        p = client.get(f"/progress/{jid}").get_json()
        if p["done"]:
            break
        time.sleep(0.2)
    assert p["done"] and not p["error"], f"job failed: {p.get('error')}"
    assert p["stats"]["total"] == 2, p["stats"]
    print("PASS run completed:", p["stats"])

    d = client.get(f"/download/csv/{jid}")
    assert d.status_code == 200 and b"Coastal Cafe" in d.data
    print("PASS CSV download")

    d = client.get(f"/download/xlsx/{jid}")
    assert d.status_code == 200 and len(d.data) > 1000
    print(f"PASS XLSX download ({len(d.data)} bytes)")

    # Demo mode — no network, no market required.
    r = client.post("/run", json={"vertical": "web_design", "demo": True})
    jid = r.get_json()["job_id"]
    for _ in range(60):
        p = client.get(f"/progress/{jid}").get_json()
        if p["done"]:
            break
        time.sleep(0.2)
    assert p["done"] and not p["error"], f"demo failed: {p.get('error')}"
    assert p["stats"]["total"] == 5, p["stats"]
    names = [l["name"] for l in p["leads"]]
    assert names[0] == "Summit Plumbing Co", names
    print("PASS demo mode:", p["stats"])

    # Demo + CRM dedupe — remove a known company.
    r = client.post("/run", json={"vertical": "web_design", "demo": True,
                                   "crm_csv": "Company name\nSummit Plumbing Co\n"})
    jid = r.get_json()["job_id"]
    for _ in range(60):
        p = client.get(f"/progress/{jid}").get_json()
        if p["done"]:
            break
        time.sleep(0.2)
    got = [l["name"] for l in p["leads"]]
    assert "Summit Plumbing Co" not in got and p["stats"]["total"] == 4, (p["stats"], got)
    print("PASS demo + CRM dedupe:", p["stats"])

    # Missing market without demo → friendly validation error.
    r = client.post("/run", json={"vertical": "web_design"})
    assert r.status_code == 400 and "market" in r.get_json()["error"].lower()
    print("PASS market-required validation")

    # Connectivity check endpoint returns structured results.
    c = client.get("/check").get_json()
    assert "results" in c and "summary" in c and isinstance(c["results"], list)
    print(f"PASS /check returns {len(c['results'])} probes")

    print("\nGUI END-TO-END OK")


if __name__ == "__main__":
    main()
