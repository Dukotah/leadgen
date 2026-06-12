"""
Lead Engine — web UI over the universal `leadgen` package.

Pick a vertical (what to prospect for) and a market (where), optionally paste
competitor pages to suppress or upload a CRM to de-dupe, then hit Run. Streams
live progress and serves the resulting CRM CSV + tiered XLSX for download, and
renders the top leads in-page.

Run:
    pip install -r gui/requirements.txt
    python gui/app.py            # then open the printed URL
    # or native window:  python gui/desktop_app.py
"""
import os
import sys
import time
import socket
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_file, render_template_string

# Make the repo root importable so `import leadgen` works regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import leadgen
from leadgen import get_vertical, all_verticals, run_pipeline
from leadgen.geo import MARKETS
from leadgen.pipeline import load_crm_names
from leadgen.diagnostics import check_connectivity, friendly_error, explain_empty_result

app = Flask(__name__)

# In-memory job store: job_id -> {log, done, error, stats, leads, files}
JOBS: dict[str, dict] = {}
# Last few completed runs this session, for the "recent runs" panel (newest first).
RECENT: list[dict] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_output")
os.makedirs(OUT_DIR, exist_ok=True)


# ───────────────────────────── job runner ────────────────────────────────────
def run_job(job_id: str, params: dict):
    job = JOBS[job_id]

    def log(msg):
        job["log"].append(f"[{datetime.now():%H:%M:%S}] {msg}")

    try:
        vertical = get_vertical(params["vertical"])
        demo = bool(params.get("demo"))
        market = (params.get("market") or "").strip() or ("(demo)" if demo else "")
        sources = tuple(params.get("sources") or ["overture"])
        enrich = bool(params.get("enrich", True))
        limit = params.get("limit") or None
        enrich_cap = params.get("enrich_cap") or 150

        override = {}
        comp = vertical.competitor_input
        urls = [u.strip() for u in (params.get("competitor_urls") or "").splitlines()
                if u.strip()]
        if comp and urls:
            override[comp["config_key"]] = urls
            log(f"Using {len(urls)} competitor page(s) for suppression.")

        # Existing-CRM dedupe: names pasted/uploaded so we never return a dupe.
        exclude = load_crm_names(params.get("crm_csv", ""), is_text=True) if params.get("crm_csv") else None
        if exclude:
            log(f"Loaded {len(exclude)} company names from your CRM — will skip those.")

        stem = os.path.join(
            OUT_DIR,
            f"{params['vertical']}_{_slug(market) or 'demo'}_{datetime.now():%Y%m%d_%H%M%S}")

        log(f"Vertical: {vertical.label}" + ("  (DEMO MODE)" if demo else ""))
        leads = run_pipeline(
            vertical, market,
            sources=sources, limit=limit, enrich=enrich, enrich_cap=enrich_cap,
            out_stem=stem, config_override=override or None,
            exclude_names=exclude, demo=demo, log=log,
        )

        files = run_pipeline.last_outputs  # (csv_path, xlsx_path) or None
        job["files"] = {
            "csv": os.path.basename(files[0]) if files else None,
            "xlsx": os.path.basename(files[1]) if files else None,
        }
        job["columns"] = vertical.columns
        # Keep a preview (top 1000) for in-page search/browse; full data is in the files.
        job["leads"] = leads[:1000]
        job["stats"] = _tier_counts(leads, total=len(leads))
        if not leads:
            job["notice"] = explain_empty_result(market, sources, vertical.label)
            log(job["notice"])
        else:
            log(f"Done. {len(leads)} leads — download below.")
            # Remember this run for the session "recent runs" panel.
            RECENT.insert(0, {
                "jid": job_id, "label": vertical.label,
                "market": market or "(sample)", "stats": job["stats"],
                "files": job["files"], "when": datetime.now().strftime("%H:%M"),
            })
            del RECENT[8:]
    except Exception as e:
        raw = f"{type(e).__name__}: {e}"
        job["error"] = friendly_error(str(e)) or raw
        log(f"ERROR: {job['error']}")
    finally:
        job["done"] = True


def _tier_counts(leads, total):
    n = {"A": 0, "B": 0, "C": 0}
    for r in leads:
        n[r.get("tier", "C")] = n.get(r.get("tier", "C"), 0) + 1
    return {"total": total, **n}


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


# ───────────────────────────── routes ────────────────────────────────────────
@app.route("/")
def index():
    verts = [{"key": k, "label": v.label, "description": v.description,
              "competitor_input": v.competitor_input,
              "default_sources": ["osm"] if not v.overture_categories and v.osm_tags else ["overture"]}
             for k, v in sorted(all_verticals().items())]
    markets = sorted(MARKETS.keys())
    return render_template_string(INDEX_HTML, verticals=verts, markets=markets)


@app.route("/run", methods=["POST"])
def start_run():
    params = request.get_json(force=True)
    if not params.get("vertical"):
        return jsonify({"error": "vertical is required"}), 400
    if not params.get("demo") and not params.get("market"):
        return jsonify({"error": "market is required (or use Demo mode)"}), 400
    jid = str(int(time.time() * 1000))
    JOBS[jid] = {"log": [], "done": False, "error": None, "notice": None,
                 "stats": None, "leads": None, "files": None, "columns": None}
    threading.Thread(target=run_job, args=(jid, params), daemon=True).start()
    return jsonify({"job_id": jid})


@app.route("/check")
def check():
    """Connectivity self-check — probe every data source, plain-English status."""
    return jsonify(check_connectivity())


@app.route("/recent")
def recent():
    """The last few completed runs this session (for the recent-runs panel)."""
    return jsonify(RECENT)


@app.route("/progress/<jid>")
def progress(jid):
    job = JOBS.get(jid)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    return jsonify({
        "log": job["log"], "done": job["done"], "error": job["error"],
        "notice": job.get("notice"),
        "stats": job["stats"], "files": job["files"],
        "leads": job["leads"] if job["done"] and not job["error"] else None,
        "columns": job["columns"],
    })


@app.route("/download/<kind>/<jid>")
def download(kind, jid):
    job = JOBS.get(jid)
    if not job or not job.get("files"):
        return "Not ready", 404
    fname = job["files"].get(kind)
    if not fname:
        return "No such file", 404
    path = os.path.join(OUT_DIR, fname)
    if not os.path.exists(path):
        return "File missing", 404
    return send_file(path, as_attachment=True, download_name=fname)


# ───────────────────────────── server bootstrap ──────────────────────────────
def free_port(default=5000):
    for p in (default, 5001, 5050, 8000, 8080, 8765):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return default


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Lead Engine</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--blue:#1F4E78;--green:#28a745;
  --bg:#fafbfc;--fg:#1d2733;--panel:#fff;--border:#dde2e8;--border2:#e3e8ee;
  --muted:#667;--muted2:#8a93a0;--field-border:#c4ccd6;--th:#eef2f7;--accent:#1F4E78;
  --tierA:#e8f8ec;--tierB:#fff8e1;--tierC:#fdecee;--ghosthover:#eef2f7;--code-bg:#0d1b2a;--code-fg:#c8e1ff}
html[data-theme=dark]{--blue:#5a9bd8;--green:#3fbf5f;--accent:#7fb6e6;
  --bg:#11161d;--fg:#dfe6ee;--panel:#1a212b;--border:#2c3742;--border2:#2c3742;
  --muted:#9aa7b4;--muted2:#7d8a97;--field-border:#3a4754;--th:#222c38;
  --tierA:#173324;--tierB:#332c14;--tierC:#3a1f23;--ghosthover:#222c38;--code-bg:#070d14;--code-fg:#a9cdf2}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;
  max-width:1080px;margin:0 auto;padding:24px 18px;color:var(--fg);background:var(--bg)}
h1{margin:0 0 2px}.sub{color:var(--muted);margin:0 0 18px;font-size:14px}
fieldset{border:1px solid var(--border);border-radius:10px;margin:0 0 16px;padding:14px 16px;background:var(--panel)}
legend{padding:0 8px;font-weight:650;color:var(--accent)}
.opt{font-weight:400;color:var(--muted2);font-size:12px}
.firsttime{background:#eaf4ff;border:1px solid #bcdcff;border-radius:9px;padding:11px 14px;margin-bottom:16px;font-size:13.5px;line-height:1.5;color:#1d2733}
html[data-theme=dark] .firsttime{background:#16314a;border-color:#27496b;color:#cfe2f5}
details.adv{border:1px solid var(--border2);border-radius:9px;background:var(--panel);padding:6px 14px;margin:0 0 16px}
details.adv>summary{cursor:pointer;font-weight:600;color:var(--accent);font-size:13.5px;padding:6px 0}
.legend{display:none;margin-top:10px;font-size:12.5px;color:var(--muted);background:var(--panel);border:1px solid var(--border2);border-radius:9px;padding:10px 13px;line-height:1.6}
label.fld{display:block;font-size:13px;font-weight:600;margin:10px 0 4px;color:var(--muted)}
input[type=text],input[type=number],select,textarea{
  width:100%;padding:9px 10px;font-size:14px;border:1px solid var(--field-border);border-radius:7px;font-family:inherit;background:var(--panel);color:var(--fg)}
textarea{resize:vertical;min-height:74px}
.row{display:flex;gap:14px;flex-wrap:wrap}.row>div{flex:1;min-width:220px}
.hint{color:var(--muted2);font-size:12px;margin-top:4px}
.checks label{display:inline-flex;align-items:center;gap:5px;margin-right:16px;font-size:14px;cursor:pointer}
button{background:var(--blue);color:#fff;border:none;padding:11px 22px;border-radius:8px;
  font-size:15px;font-weight:600;cursor:pointer}button:hover{filter:brightness(.9)}
button:disabled{background:#a9b2bd;cursor:not-allowed;filter:none}
button.ghost{background:var(--panel);color:var(--accent);border:1.5px solid var(--field-border)}
button.ghost:hover{background:var(--ghosthover);filter:none}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:4px}
input[type=file]{font-size:13px}
#checkout{margin-top:12px}
.probe{display:flex;align-items:center;gap:8px;font-size:13px;padding:4px 0}
.probe .dot{width:10px;height:10px;border-radius:50%;flex:none}
.dot.ok{background:#28a745}.dot.bad{background:#d6453f}
.banner{border-radius:9px;padding:11px 14px;margin-top:10px;font-size:13.5px}
.banner.good{background:#e8f8ec;border:1px solid #b6e3c2;color:#1d2733}
.banner.warn{background:#fff4e0;border:1px solid #f0d49a;color:#1d2733}
.banner.bad{background:#fdecee;border:1px solid #f0bcc0;color:#1d2733}
.vdesc{font-size:12.5px;color:var(--muted);margin-top:6px;line-height:1.45}
#status{display:none;margin-top:8px;background:var(--code-bg);color:var(--code-fg);border-radius:9px;
  padding:12px 14px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;
  max-height:260px;overflow:auto;white-space:pre-wrap;line-height:1.5}
#summary{display:none;margin-top:14px;gap:10px}
.stat{flex:1;text-align:center;background:var(--panel);border:1px solid var(--border);border-radius:9px;padding:10px}
.stat b{display:block;font-size:24px}.stat.A b{color:var(--green)}.stat.B b{color:#c79100}.stat.C b{color:#b04a52}
#dls{display:none;margin-top:12px;gap:10px}
a.dl{display:inline-block;padding:10px 16px;background:var(--green);color:#fff;text-decoration:none;border-radius:8px;font-weight:600}
a.dl.alt{background:#34507a}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:12.5px;display:none;background:var(--panel)}
th,td{border:1px solid var(--border2);padding:5px 7px;text-align:left;vertical-align:top}
th{background:var(--th);position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap}
th .arrow{color:var(--muted2);font-size:10px;margin-left:3px}
.tierA{background:var(--tierA)}.tierB{background:var(--tierB)}.tierC{background:var(--tierC)}
tr.tagged-contacted td{box-shadow:inset 4px 0 0 0 var(--green)}
tr.tagged-not_interested td{box-shadow:inset 4px 0 0 0 #b04a52;opacity:.6}
.tablewrap{max-height:440px;overflow:auto;border-radius:9px;border:1px solid var(--border2);margin-top:14px;display:none}
.recent{display:flex;flex-wrap:wrap;gap:8px}
.rcard{border:1px solid var(--border);border-radius:8px;padding:8px 11px;background:var(--panel);font-size:12.5px;min-width:210px}
.rcard b{color:var(--accent)}.rcard a{color:var(--green);text-decoration:none;font-weight:600}
.rcard .meta{color:var(--muted2);font-size:11.5px;margin:2px 0 5px}
#resultsearch{display:none;margin-top:14px}
#themetoggle{position:fixed;top:14px;right:14px;background:var(--panel);color:var(--accent);
  border:1.5px solid var(--field-border);padding:7px 12px;border-radius:8px;font-size:13px;z-index:50}
#themetoggle:hover{background:var(--ghosthover);filter:none}
.resulttools{display:none;flex-wrap:wrap;gap:8px;align-items:center;margin-top:14px}
.resulttools button{padding:7px 13px;font-size:13px}
.cellbtn{background:none;border:1px solid var(--field-border);color:var(--accent);
  padding:1px 5px;font-size:11px;border-radius:5px;cursor:pointer;font-weight:600;margin-left:4px;vertical-align:middle}
.cellbtn:hover{background:var(--ghosthover);filter:none}
td a{color:var(--accent);text-decoration:none}td a:hover{text-decoration:underline}
.tagbtns{display:inline-flex;gap:3px}
.tagbtns button{background:none;border:1px solid var(--field-border);color:var(--muted);
  padding:1px 5px;font-size:11px;border-radius:5px;cursor:pointer}
.tagbtns button.on-c{background:var(--green);color:#fff;border-color:var(--green)}
.tagbtns button.on-n{background:#b04a52;color:#fff;border-color:#b04a52}
#colmenu{position:relative;display:inline-block}
#colpanel{display:none;position:absolute;top:100%;left:0;z-index:40;background:var(--panel);
  border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin-top:4px;
  box-shadow:0 4px 14px rgba(0,0,0,.15);min-width:200px;max-height:300px;overflow:auto}
#colpanel label{display:block;font-size:13px;padding:3px 0;cursor:pointer;white-space:nowrap;font-weight:400;color:var(--fg)}
#colpanel input{margin-right:6px}
/* Settings panel */
details.settings>summary{cursor:pointer;font-weight:600;color:var(--accent);font-size:13.5px;padding:6px 0}
.setgrid{display:flex;flex-wrap:wrap;gap:14px;margin-top:8px}.setgrid>div{flex:1;min-width:200px}
.setchecks label{display:block;font-size:13px;padding:2px 0;cursor:pointer;font-weight:400;color:var(--fg)}
.setchecks input{margin-right:6px;width:auto}
.setactions{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.setactions .saved{color:var(--green);font-size:12.5px;font-weight:600}
/* Run queue */
.queuegrid{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.queuegrid>div{flex:1;min-width:160px}
.qlist{list-style:none;margin:12px 0 0;padding:0;display:flex;flex-direction:column;gap:6px}
.qitem{display:flex;align-items:center;gap:8px;border:1px solid var(--border);border-radius:8px;
  padding:7px 11px;background:var(--panel);font-size:13px}
.qitem .qmeta{flex:1}.qitem .qmeta b{color:var(--accent)}
.qitem .qstate{font-size:11.5px;color:var(--muted2);font-weight:600}
.qitem.active{border-color:var(--blue);box-shadow:inset 3px 0 0 0 var(--blue)}
.qitem.done{opacity:.65}.qitem.done .qstate{color:var(--green)}
.qitem.failed .qstate{color:#b04a52}
.qitem button.qrm{background:none;border:1px solid var(--field-border);color:var(--muted);
  padding:1px 7px;font-size:12px;border-radius:5px;cursor:pointer;font-weight:600}
/* Per-source tally + timer */
#runmeter{display:none;margin-top:10px;flex-wrap:wrap;gap:8px;align-items:center}
#runmeter .chip{background:var(--panel);border:1px solid var(--border);border-radius:20px;
  padding:4px 11px;font-size:12.5px;color:var(--fg)}
#runmeter .chip b{color:var(--accent)}
#runtimer{font-size:12.5px;color:var(--muted2);font-weight:600}
/* First-run tour */
#tour{display:none;position:fixed;inset:0;background:rgba(10,16,24,.55);z-index:100}
#tourcard{position:absolute;max-width:300px;background:var(--panel);color:var(--fg);
  border:1px solid var(--border);border-radius:11px;padding:15px 17px;box-shadow:0 8px 30px rgba(0,0,0,.35);font-size:13.5px;line-height:1.5}
#tourcard h3{margin:0 0 6px;color:var(--accent);font-size:15px}
#tourcard .tnav{display:flex;justify-content:space-between;align-items:center;margin-top:12px}
#tourcard .tnav .tstep{color:var(--muted2);font-size:12px}
#tourcard button{padding:6px 14px;font-size:13px}
#tourcard button.tskip{background:none;color:var(--muted);border:none;padding:6px 4px;font-weight:600}
.tourhi{position:relative;z-index:101;box-shadow:0 0 0 3px var(--blue),0 0 0 9px rgba(31,78,120,.3);border-radius:8px}
</style></head><body>
<button id="themetoggle" type="button" title="Toggle dark mode">🌙 Dark</button>
<h1>Lead Engine</h1>
<p class="sub">Find scored local-business leads from free public data — no accounts, no API keys.</p>

<div class="firsttime">
  <b>First time?</b> Click <b>“Try a sample”</b> at the bottom — it runs instantly with no internet and shows exactly what you’ll get. Then fill in the boxes below for a real search.
</div>

<details class="adv settings" id="settingswrap">
  <summary>⚙ Settings &amp; defaults</summary>
  <div class="setgrid">
    <div>
      <label class="fld">Default data sources</label>
      <div class="setchecks" id="set_sources">
        <label><input type="checkbox" data-src="overture"> Nationwide business directory</label>
        <label><input type="checkbox" data-src="osm"> Live map data</label>
        <label><input type="checkbox" data-src="socrata"> New-business records (open data)</label>
        <label><input type="checkbox" data-src="npi"> Healthcare providers (NPI)</label>
        <label><input type="checkbox" data-src="foursquare"> Foursquare (deep · slow)</label>
      </div>
      <div class="hint">Applied to the run form when you open the page. Picking a vertical may still override these.</div>
    </div>
    <div>
      <label class="fld">Default deep-check cap</label>
      <input type="number" id="set_enrich_cap" min="0" placeholder="150">
      <div class="hint">Pre-fills “Deep-check at most this many” under Advanced options.</div>
      <label class="fld">Crawler contact string (User-Agent)</label>
      <input type="text" id="set_ua" placeholder="LeadEngine/1.0 (you@example.com)">
      <div class="hint">Informational — a polite contact so site owners know who is crawling. Stored locally only.</div>
    </div>
  </div>
  <div class="setactions">
    <button type="button" id="set_save">Save defaults</button>
    <button type="button" class="ghost" id="set_clear">Reset</button>
    <span class="saved" id="set_saved" style="display:none">Saved ✓</span>
  </div>
</details>

<div id="recentwrap" style="display:none">
  <fieldset><legend>Recent runs <span class="opt">(this session)</span></legend>
    <div class="recent" id="recentlist"></div>
  </fieldset>
</div>

<form id="form">
  <fieldset>
    <legend>1 · What kind of leads?</legend>
    <label class="fld">Type of business to find</label>
    <select id="vertical"></select>
    <div class="vdesc" id="vdesc"></div>
  </fieldset>

  <fieldset>
    <legend>2 · Where should we look?</legend>
    <div class="row">
      <div>
        <label class="fld">Area</label>
        <input type="text" id="market" list="markets" placeholder="e.g. Austin, Texas">
        <datalist id="markets">{% for m in markets %}<option value="{{m}}">{% endfor %}</datalist>
        <div class="hint">Type any city, county, or metro — for example “Austin, Texas”. A few saved areas are in the dropdown.</div>
      </div>
      <div>
        <label class="fld">Where the data comes from</label>
        <div class="checks" style="padding-top:8px">
          <label><input type="checkbox" id="src_overture" checked> Nationwide business directory</label>
          <label><input type="checkbox" id="src_osm"> Live map data</label>
          <label><input type="checkbox" id="src_socrata"> New-business records (open data)</label>
          <label><input type="checkbox" id="src_npi"> Healthcare providers (NPI)</label>
          <label><input type="checkbox" id="src_foursquare"> Foursquare (deep · slow ~1–2 min)</label>
        </div>
        <div class="hint">Leave these as-is unless a search comes back empty — then try ticking another box. “New-business records” = just-licensed businesses (coverage varies by city); “Healthcare providers” = dentists/doctors/clinics; “Foursquare” is a deep scan that takes 1–2 minutes.</div>
      </div>
    </div>
  </fieldset>

  <fieldset id="competitor_box" style="display:none">
    <legend>3 · Skip anyone already using a competitor <span class="opt">(optional)</span></legend>
    <label class="fld" id="competitor_label"></label>
    <textarea id="competitor_urls" placeholder="https://a-competitor.com/testimonials&#10;https://another-competitor.com/reviews"></textarea>
    <div class="hint" id="competitor_help"></div>
    <div class="hint">One web address per line.</div>
  </fieldset>

  <fieldset>
    <legend>4 · Skip people already in your CRM <span class="opt">(optional)</span></legend>
    <label class="fld">Upload your current contact list (.csv)</label>
    <input type="file" id="crm_file" accept=".csv,text/csv">
    <div class="hint" id="crm_status">We match on company name and remove anyone you already have — so you never get a duplicate.</div>
  </fieldset>

  <details class="adv">
    <summary>Advanced options</summary>
    <div class="row" style="margin-top:10px">
      <div>
        <label class="fld"><input type="checkbox" id="enrich" checked style="width:auto"> Visit each website for deeper detail</label>
        <div class="hint">Audits each site (HTTPS, mobile, speed, DIY builder). Richer results, a bit slower. Recommended on.</div>
      </div>
      <div>
        <label class="fld">Deep-check at most this many</label>
        <input type="number" id="enrich_cap" value="150" min="0">
      </div>
      <div>
        <label class="fld">Stop after this many found</label>
        <input type="number" id="limit" placeholder="no limit">
      </div>
    </div>
  </details>

  <div class="btnrow">
    <button type="submit" id="go">🔍 Find leads</button>
    <button type="button" id="demo" class="ghost">▶ Try a sample (no internet needed)</button>
    <button type="button" id="check" class="ghost">📡 Check my connection</button>
    <button type="button" id="enqueue" class="ghost">➕ Add to queue</button>
  </div>
  <div id="checkout"></div>
  <div id="runmeter">
    <span id="runtimer">⏱ 0:00</span>
    <span id="runchips"></span>
  </div>
</form>

<details class="adv settings" id="queuewrap" style="display:none">
  <summary>📋 Run queue <span class="opt" id="queuecount"></span></summary>
  <div class="hint" style="margin:4px 0 0">Queued runs use the current sources / advanced options and run one after another.</div>
  <ul class="qlist" id="qlist"></ul>
  <div class="setactions">
    <button type="button" id="queuerun">▶ Run queue</button>
    <button type="button" class="ghost" id="queueclear">Clear queue</button>
  </div>
</details>

<div id="summary" class="row">
  <div class="stat"><b id="s_total">0</b>leads found</div>
  <div class="stat A"><b id="s_A">0</b>🟢 Call first</div>
  <div class="stat B"><b id="s_B">0</b>🟡 Worth a call</div>
  <div class="stat C"><b id="s_C">0</b>🔴 Lower priority</div>
</div>
<div id="dls" class="row"></div>
<div id="legend" class="legend"></div>
<details id="logwrap" class="adv" style="display:none"><summary>Show activity log</summary>
  <div id="status"></div>
</details>
<div id="resultsearch">
  <input type="text" id="r_filter" placeholder="Filter these results… (name, city, why a lead, pitch)">
</div>
<div class="resulttools" id="resulttools">
  <span id="colmenu">
    <button type="button" class="ghost" id="colbtn">☰ Columns</button>
    <div id="colpanel"></div>
  </span>
  <button type="button" class="ghost" id="exportbtn">⬇ Export filtered view (.csv)</button>
  <span class="hint" id="exportcount"></span>
</div>
<div class="tablewrap" id="tablewrap"><table id="preview"></table></div>

<div id="tour">
  <div id="tourcard">
    <h3 id="tourtitle"></h3>
    <div id="tourbody"></div>
    <div class="tnav">
      <button type="button" class="tskip" id="tourskip">Skip tour</button>
      <span class="tstep" id="tourstep"></span>
      <button type="button" id="tournext">Next →</button>
    </div>
  </div>
</div>

<script>
// ── Dark mode: respect prefers-color-scheme on first load, persist choice. ──
(function(){
  const tog=document.getElementById("themetoggle");
  function apply(t){
    document.documentElement.setAttribute("data-theme", t);
    tog.textContent = t==="dark" ? "☀️ Light" : "🌙 Dark";
  }
  let saved=null; try{ saved=localStorage.getItem("leadgen_theme"); }catch(e){}
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  apply(saved || (prefersDark ? "dark" : "light"));
  tog.addEventListener("click", ()=>{
    const next = document.documentElement.getAttribute("data-theme")==="dark" ? "light" : "dark";
    apply(next); try{ localStorage.setItem("leadgen_theme", next); }catch(e){}
  });
})();

const VERTS = {{ verticals|tojson }};
const vsel = document.getElementById("vertical");
VERTS.forEach(v => { const o=document.createElement("option"); o.value=v.key; o.textContent=v.label; vsel.appendChild(o); });

function syncVertical(){
  const v = VERTS.find(x=>x.key===vsel.value);
  document.getElementById("vdesc").textContent = v.description || "";
  const cb = document.getElementById("competitor_box");
  if (v.competitor_input){
    cb.style.display="block";
    document.getElementById("competitor_label").textContent = v.competitor_input.label;
    document.getElementById("competitor_help").textContent = v.competitor_input.help;
  } else cb.style.display="none";
  document.getElementById("src_overture").checked = v.default_sources.includes("overture");
  document.getElementById("src_osm").checked = v.default_sources.includes("osm");
}
vsel.addEventListener("change", syncVertical); syncVertical();

const form=document.getElementById("form"), go=document.getElementById("go");
const demoBtn=document.getElementById("demo"), checkBtn=document.getElementById("check");
const checkout=document.getElementById("checkout");
const statusEl=document.getElementById("status"), summary=document.getElementById("summary");
const logwrap=document.getElementById("logwrap"), legend=document.getElementById("legend");
const dls=document.getElementById("dls"), tablewrap=document.getElementById("tablewrap"), table=document.getElementById("preview");
const GO_LABEL="🔍 Find leads";

function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c])); }

// Read an uploaded CRM .csv into memory (text) so the server can dedupe against it.
let crmText="";
document.getElementById("crm_file").addEventListener("change", e=>{
  const f=e.target.files[0]; const st=document.getElementById("crm_status");
  if(!f){ crmText=""; return; }
  const reader=new FileReader();
  reader.onload=()=>{ crmText=reader.result||"";
    const lines=crmText.split(/\\r?\\n/).filter(x=>x.trim()).length-1;
    st.textContent=`Loaded ${f.name} — about ${Math.max(0,lines)} companies will be skipped if found.`; };
  reader.readAsText(f);
});

function baseBody(){
  const sources=[]; if(document.getElementById("src_overture").checked) sources.push("overture");
  if(document.getElementById("src_osm").checked) sources.push("osm");
  if(document.getElementById("src_socrata").checked) sources.push("socrata");
  if(document.getElementById("src_npi").checked) sources.push("npi");
  if(document.getElementById("src_foursquare").checked) sources.push("foursquare");
  return {
    vertical:vsel.value, market:document.getElementById("market").value,
    sources, enrich:document.getElementById("enrich").checked,
    enrich_cap:+document.getElementById("enrich_cap").value||0,
    limit:+document.getElementById("limit").value||0,
    competitor_urls:document.getElementById("competitor_urls").value,
    crm_csv:crmText,
  };
}

let lastBody=null;  // last run's request body, for the Retry button

async function startRun(body){
  lastBody=body;
  go.disabled=true; demoBtn.disabled=true; go.textContent="Working…";
  logwrap.style.display="block"; statusEl.style.display="block"; statusEl.textContent="Starting…"; checkout.innerHTML="";
  summary.style.display="none"; dls.style.display="none"; legend.style.display="none";
  tablewrap.style.display="none"; table.style.display="none";
  startMeter();
  const r=await fetch("/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await r.json();
  if(j.error){ checkout.innerHTML=`<div class="banner bad">${esc(j.error)}</div>`;
    go.disabled=false; demoBtn.disabled=false; go.textContent=GO_LABEL; stopMeter();
    return Promise.resolve({error:j.error}); }
  return poll(j.job_id);
}

form.addEventListener("submit", e=>{
  e.preventDefault();
  const body=baseBody();
  if(!body.market.trim()){ alert("Type an area to search, or click “Try a sample”."); return; }
  if(!body.sources.length){ alert("Leave at least one data source ticked under “Where the data comes from”."); return; }
  body.demo=false; saveMarket(body.market); startRun(body);
});

demoBtn.addEventListener("click", ()=>{
  const body=baseBody(); body.demo=true; body.market=body.market||"(sample)";
  startRun(body);
});

checkBtn.addEventListener("click", async ()=>{
  checkBtn.disabled=true; checkout.innerHTML="<div class='hint'>Testing each data source…</div>";
  try{
    const j=await (await fetch("/check")).json();
    let h=j.results.map(p=>`<div class="probe"><span class="dot ${p.ok?'ok':'bad'}"></span>`
      +`<b>${p.label}</b> — ${p.detail}</div>`).join("");
    const cls=(j.can_overture||j.can_osm)?(j.can_overture&&j.can_osm?"good":"warn"):"bad";
    h+=`<div class="banner ${cls}">${j.summary}</div>`;
    checkout.innerHTML=h;
  }catch(e){ checkout.innerHTML="<div class='banner bad'>Could not run the check.</div>"; }
  checkBtn.disabled=false;
});

function poll(jid){
 return new Promise(resolve=>{
  const t=setInterval(async ()=>{
    const r=await fetch("/progress/"+jid); const j=await r.json();
    statusEl.textContent=j.log.join("\\n"); statusEl.scrollTop=statusEl.scrollHeight;
    updateMeter(j.log);
    if(j.done){
      clearInterval(t); go.disabled=false; demoBtn.disabled=false; go.textContent=GO_LABEL;
      stopMeter(); loadRecent();
      // Mid-run recovery: error OR a source reported "failed" in the log → retry banner.
      const logText=(j.log||[]).join("\\n");
      const sourceFailed=/failed/i.test(logText);
      if(j.error || sourceFailed){
        const msg=j.error || "A data source failed during this run — results may be incomplete.";
        checkout.innerHTML=`<div class="banner bad" id="retrybanner">${esc(msg)} `
          +`<button type="button" class="ghost" id="retrybtn" style="padding:5px 12px;margin-left:8px">↻ Retry</button></div>`;
        const rb=document.getElementById("retrybtn");
        if(rb) rb.addEventListener("click", ()=>{ if(lastBody) startRun(Object.assign({}, lastBody)); });
      }
      else if(j.notice){ checkout.innerHTML=`<div class="banner warn">${esc(j.notice)}</div>`; }
      if(j.stats){
        summary.style.display="flex";
        s_total.textContent=j.stats.total; s_A.textContent=j.stats.A;
        s_B.textContent=j.stats.B; s_C.textContent=j.stats.C;
      }
      if(j.files && (j.files.csv||j.files.xlsx)){
        dls.style.display="flex"; dls.innerHTML="";
        if(j.files.xlsx) dls.innerHTML+=`<a class="dl" href="/download/xlsx/${jid}">⬇ Download spreadsheet (Excel)</a>`;
        if(j.files.csv) dls.innerHTML+=`<a class="dl alt" href="/download/csv/${jid}">⬇ Download for CRM (.csv)</a>`;
      }
      if(j.leads && j.leads.length){
        legend.style.display="block";
        legend.innerHTML="<b>How to read this:</b> 🟢 <b>Call first</b> = best fit, contact these today · "
          +"🟡 <b>Worth a call</b> = good but verify on the call · 🔴 <b>Lower priority</b> = weak fit or already taken. "
          +"The full list (with phone, website, why it's a lead, and a suggested opener) is in the downloads above.";
        renderTable(j.leads, j.columns);
      }
      resolve({error:j.error, sourceFailed, stats:j.stats});
    }
  }, 700);
 });
}

let curLeads=[], curCols=[];
let visibleCols={};        // key -> bool (shown in preview)
let sortKey=null, sortDir=1; // 1 asc, -1 desc
const PHONE_KEYS=new Set(["phone","telephone","tel"]);
const EMAIL_KEYS=new Set(["email","e-mail","mail"]);

// ── Per-lead tagging (contacted / not-interested), persisted in localStorage. ──
function loadTags(){ try{ return JSON.parse(localStorage.getItem("leadgen_tags")||"{}"); }catch(e){ return {}; } }
function saveTags(t){ try{ localStorage.setItem("leadgen_tags", JSON.stringify(t)); }catch(e){} }
let tags=loadTags();
function leadKey(r){ return (String(r.name||"").trim()+"|"+String(r.phone||"").trim()).toLowerCase(); }

function renderTable(leads, columns){
  curLeads=leads||[]; curCols=columns||[];
  // Default visible columns: first 9 (matches prior "keep readable" behaviour), unless prefs saved.
  let savedVis=null; try{ savedVis=JSON.parse(localStorage.getItem("leadgen_cols")||"null"); }catch(e){}
  visibleCols={};
  curCols.forEach((c,i)=>{ const k=c[1];
    visibleCols[k] = savedVis && (k in savedVis) ? !!savedVis[k] : i<9; });
  sortKey=null; sortDir=1;
  document.getElementById("resultsearch").style.display="block";
  document.getElementById("resulttools").style.display="flex";
  buildColPanel();
  drawRows();
}

function buildColPanel(){
  const p=document.getElementById("colpanel");
  p.innerHTML=curCols.map(c=>
    `<label><input type="checkbox" data-k="${esc(c[1])}" ${visibleCols[c[1]]?"checked":""}>${esc(c[0])}</label>`
  ).join("");
  p.querySelectorAll("input").forEach(cb=>cb.addEventListener("change", ()=>{
    visibleCols[cb.dataset.k]=cb.checked;
    try{ localStorage.setItem("leadgen_cols", JSON.stringify(visibleCols)); }catch(e){}
    drawRows();
  }));
}

function shownCols(){ return curCols.filter(c=>visibleCols[c[1]]); }

function filteredRows(){
  const q=(document.getElementById("r_filter").value||"").toLowerCase().trim();
  const cols=shownCols();
  const match=r=>cols.some(c=>String(r[c[1]]==null?"":r[c[1]]).toLowerCase().includes(q));
  let rows=q?curLeads.filter(match):curLeads.slice();
  if(sortKey!=null){
    rows.sort((a,b)=>{
      let x=a[sortKey], y=b[sortKey];
      const nx=parseFloat(x), ny=parseFloat(y);
      let c;
      if(!isNaN(nx)&&!isNaN(ny)&&String(x).trim()!==""&&String(y).trim()!=="") c=nx-ny;
      else c=String(x==null?"":x).toLowerCase().localeCompare(String(y==null?"":y).toLowerCase());
      return c*sortDir;
    });
  }
  return rows;
}

function cellHTML(r, key){
  const raw=r[key]; const v=String(raw==null?"":raw);
  if(!v) return "";
  if(PHONE_KEYS.has(key)){
    const tel=v.replace(/[^0-9+]/g,"");
    return `<a href="tel:${esc(tel)}">${esc(v)}</a>`
      +`<button type="button" class="cellbtn" data-copy="${esc(v)}">copy</button>`;
  }
  if(EMAIL_KEYS.has(key)){
    return `<a href="mailto:${esc(v)}">${esc(v)}</a>`
      +`<button type="button" class="cellbtn" data-copy="${esc(v)}">copy</button>`;
  }
  return esc(v);
}

function drawRows(){
  const cols=shownCols();
  const all=filteredRows();
  const rows=all.slice(0,500);
  document.getElementById("exportcount").textContent=
    all.length+" row(s) match"+(curLeads.length!==all.length?" of "+curLeads.length:"");
  const arrow=k=> sortKey===k ? `<span class="arrow">${sortDir>0?"▲":"▼"}</span>` : `<span class="arrow">↕</span>`;
  let h="<thead><tr>"+cols.map(c=>`<th data-k="${esc(c[1])}">${esc(c[0])}${arrow(c[1])}</th>`).join("")
    +`<th>Status</th></tr></thead><tbody>`;
  for(const r of rows){
    const tier=r.tier||"C";
    const tg=tags[leadKey(r)]||"";
    const tagClass=tg?` tagged-${esc(tg)}`:"";
    h+=`<tr class="tier${esc(tier)}${tagClass}">`
      +cols.map(c=>`<td>${cellHTML(r,c[1])}</td>`).join("")
      +`<td><span class="tagbtns" data-key="${esc(leadKey(r))}">`
      +`<button type="button" data-tag="contacted" class="${tg==='contacted'?'on-c':''}" title="Mark contacted">✓</button>`
      +`<button type="button" data-tag="not_interested" class="${tg==='not_interested'?'on-n':''}" title="Not interested">✕</button>`
      +`</span></td></tr>`;
  }
  table.innerHTML=h+"</tbody>"; table.style.display="table"; tablewrap.style.display="block";
  // header sort handlers
  table.querySelectorAll("th[data-k]").forEach(th=>th.addEventListener("click", ()=>{
    const k=th.dataset.k;
    if(sortKey===k) sortDir=-sortDir; else { sortKey=k; sortDir=1; }
    drawRows();
  }));
  // copy buttons
  table.querySelectorAll("button[data-copy]").forEach(b=>b.addEventListener("click", ev=>{
    ev.stopPropagation();
    const txt=b.dataset.copy;
    const done=()=>{ const o=b.textContent; b.textContent="✓"; setTimeout(()=>b.textContent=o,900); };
    if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done,done);
    else { const ta=document.createElement("textarea"); ta.value=txt; document.body.appendChild(ta);
           ta.select(); try{document.execCommand("copy");}catch(e){} ta.remove(); done(); }
  }));
  // tag buttons (mark contacted / not-interested; click again to clear)
  table.querySelectorAll(".tagbtns button").forEach(b=>b.addEventListener("click", ()=>{
    const key=b.parentNode.dataset.key, val=b.dataset.tag;
    if(tags[key]===val) delete tags[key]; else tags[key]=val;
    saveTags(tags); drawRows();
  }));
}
document.getElementById("r_filter").addEventListener("input", drawRows);

// Column chooser open/close
document.getElementById("colbtn").addEventListener("click", e=>{
  e.stopPropagation();
  const p=document.getElementById("colpanel");
  p.style.display = p.style.display==="block" ? "none" : "block";
});
document.addEventListener("click", e=>{
  const p=document.getElementById("colpanel");
  if(p && !document.getElementById("colmenu").contains(e.target)) p.style.display="none";
});

// ── Export exactly the filtered + sorted rows, with visible columns, as CSV. ──
function csvCell(v){ v=String(v==null?"":v);
  return /[",\\n\\r]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v; }
document.getElementById("exportbtn").addEventListener("click", ()=>{
  const cols=shownCols();
  const rows=filteredRows();
  const header=cols.map(c=>csvCell(c[0])).concat(["status"]);
  const lines=[header.join(",")];
  for(const r of rows){
    const row=cols.map(c=>csvCell(r[c[1]])).concat([csvCell(tags[leadKey(r)]||"")]);
    lines.push(row.join(","));
  }
  const blob=new Blob(["\\ufeff"+lines.join("\\r\\n")],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url; a.download="leads_filtered.csv"; document.body.appendChild(a); a.click();
  a.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
});

// Recent runs (this session) — re-download without re-running.
async function loadRecent(){
  try{
    const list=await (await fetch("/recent")).json();
    const wrap=document.getElementById("recentwrap"), el=document.getElementById("recentlist");
    if(!list.length){ wrap.style.display="none"; return; }
    el.innerHTML=list.map(r=>{
      const f=r.files||{};
      const links=[f.xlsx?`<a href="/download/xlsx/${r.jid}">⬇ Excel</a>`:"",
                   f.csv?`<a href="/download/csv/${r.jid}">⬇ CSV</a>`:""].filter(Boolean).join(" · ");
      return `<div class="rcard"><b>${esc(r.label)}</b>`
        +`<div class="meta">${esc(r.market)} · ${esc(r.when)}</div>`
        +`${r.stats.total} leads · 🟢${r.stats.A} 🟡${r.stats.B} 🔴${r.stats.C}`
        +`<div style="margin-top:5px">${links}</div></div>`;
    }).join("");
    wrap.style.display="block";
  }catch(e){}
}

// Remember markets the user actually searched, across sessions.
function loadSavedMarkets(){
  try{
    const saved=JSON.parse(localStorage.getItem("leadgen_markets")||"[]");
    const dl=document.getElementById("markets");
    saved.forEach(m=>{ if(![...dl.options].some(o=>o.value===m)){
      const o=document.createElement("option"); o.value=m; dl.appendChild(o); } });
  }catch(e){}
}
function saveMarket(m){
  if(!m||!m.trim()) return;
  try{
    let saved=JSON.parse(localStorage.getItem("leadgen_markets")||"[]");
    saved=[m,...saved.filter(x=>x!==m)].slice(0,8);
    localStorage.setItem("leadgen_markets",JSON.stringify(saved));
  }catch(e){}
}

// ─────────────────────────── Settings panel ────────────────────────────────
// Default sources, default enrich cap, crawler UA — persisted in localStorage.
const SET_KEY="leadgen_settings";
function loadSettings(){ try{ return JSON.parse(localStorage.getItem(SET_KEY)||"null"); }catch(e){ return null; } }
function applySettings(s){
  if(!s) return;
  if(Array.isArray(s.sources)){
    document.querySelectorAll("#set_sources input").forEach(cb=>cb.checked=s.sources.includes(cb.dataset.src));
    // Mirror onto the run form's source checkboxes.
    const map={overture:"src_overture",osm:"src_osm",socrata:"src_socrata",npi:"src_npi",foursquare:"src_foursquare"};
    Object.entries(map).forEach(([src,id])=>{ const el=document.getElementById(id); if(el) el.checked=s.sources.includes(src); });
  }
  if(s.enrich_cap!=null && s.enrich_cap!==""){
    document.getElementById("set_enrich_cap").value=s.enrich_cap;
    document.getElementById("enrich_cap").value=s.enrich_cap;
  }
  if(s.ua!=null) document.getElementById("set_ua").value=s.ua;
}
function readSettingsForm(){
  const sources=[...document.querySelectorAll("#set_sources input")].filter(cb=>cb.checked).map(cb=>cb.dataset.src);
  return { sources, enrich_cap:document.getElementById("set_enrich_cap").value,
           ua:document.getElementById("set_ua").value };
}
document.getElementById("set_save").addEventListener("click", ()=>{
  const s=readSettingsForm();
  try{ localStorage.setItem(SET_KEY, JSON.stringify(s)); }catch(e){}
  applySettings(s);
  const saved=document.getElementById("set_saved");
  saved.style.display="inline"; setTimeout(()=>saved.style.display="none",1500);
});
document.getElementById("set_clear").addEventListener("click", ()=>{
  try{ localStorage.removeItem(SET_KEY); }catch(e){}
  document.querySelectorAll("#set_sources input").forEach(cb=>cb.checked=false);
  document.getElementById("set_enrich_cap").value="";
  document.getElementById("set_ua").value="";
});
// Apply saved settings on load — but a vertical change can still re-set sources via syncVertical.
applySettings(loadSettings());

// ─────────────────────────── Run queue ─────────────────────────────────────
// Queue (vertical, market) combos and run them sequentially through /run + /progress.
let queue=[];          // {vertical, vlabel, market}
let queueRunning=false;
const qlist=document.getElementById("qlist"), queuewrap=document.getElementById("queuewrap");
function renderQueue(){
  document.getElementById("queuecount").textContent = queue.length ? `(${queue.length})` : "";
  queuewrap.style.display = queue.length ? "block" : "none";
  if(queue.length && !queueRunning) queuewrap.open=true;
  qlist.innerHTML=queue.map((q,i)=>{
    const st=q.state||"queued";
    const cls=st==="active"?"active":st==="done"?"done":st==="failed"?"failed":"";
    const label={queued:"queued",active:"running…",done:"done ✓",failed:"failed"}[st]||st;
    return `<li class="qitem ${cls}"><span class="qmeta"><b>${esc(q.vlabel)}</b> · ${esc(q.market)}</span>`
      +`<span class="qstate">${esc(label)}</span>`
      +(queueRunning?"":`<button type="button" class="qrm" data-i="${i}">✕</button>`)+`</li>`;
  }).join("");
  qlist.querySelectorAll("button.qrm").forEach(b=>b.addEventListener("click", ()=>{
    queue.splice(+b.dataset.i,1); renderQueue();
  }));
}
document.getElementById("enqueue").addEventListener("click", ()=>{
  const market=document.getElementById("market").value.trim();
  if(!market){ alert("Type an area before adding to the queue."); return; }
  const v=VERTS.find(x=>x.key===vsel.value);
  queue.push({vertical:vsel.value, vlabel:(v&&v.label)||vsel.value, market, state:"queued"});
  saveMarket(market); renderQueue();
});
document.getElementById("queueclear").addEventListener("click", ()=>{
  if(queueRunning) return; queue=[]; renderQueue();
});
document.getElementById("queuerun").addEventListener("click", runQueue);
async function runQueue(){
  if(queueRunning || !queue.length) return;
  queueRunning=true; renderQueue();
  // Sources / advanced options taken once from the form (baseBody) and reused per combo.
  const tmpl=baseBody(); tmpl.demo=false;
  for(const q of queue){
    if(q.state==="done") continue;
    q.state="active"; renderQueue();
    const body=Object.assign({}, tmpl, {vertical:q.vertical, market:q.market});
    let res;
    try{ res=await startRun(body); }catch(e){ res={error:String(e)}; }
    q.state=(res&&(res.error||res.sourceFailed))?"failed":"done";
    renderQueue();
  }
  queueRunning=false; renderQueue();
}

// ────────────────── Per-source progress / ETA + elapsed timer ───────────────
// Parse streaming log lines like "  Overture: 412 businesses" / "  NPI: 128 providers…"
let meterTimer=null, meterStart=0;
const SOURCE_LINE=/^\\s*([A-Za-z][A-Za-z0-9 ]*?):\\s*([\\d,]+)\\b/;
function startMeter(){
  meterStart=Date.now();
  document.getElementById("runmeter").style.display="flex";
  document.getElementById("runchips").innerHTML="";
  document.getElementById("runtimer").textContent="⏱ 0:00";
  clearInterval(meterTimer);
  meterTimer=setInterval(()=>{
    const s=Math.floor((Date.now()-meterStart)/1000);
    document.getElementById("runtimer").textContent=`⏱ ${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;
  }, 500);
}
function updateMeter(log){
  if(!log) return;
  const tally={};
  for(let line of log){
    line=line.replace(/^\\[\\d{2}:\\d{2}:\\d{2}\\]\\s*/,"");  // drop timestamp prefix
    const m=line.match(SOURCE_LINE);
    if(m){
      const name=m[1].trim(), n=parseInt(m[2].replace(/,/g,""),10);
      if(name && !isNaN(n)) tally[name]=n;   // last value for a source wins
    }
  }
  const chips=Object.entries(tally).map(([k,v])=>`<span class="chip"><b>${esc(k)}</b> ${v}</span>`).join("");
  document.getElementById("runchips").innerHTML=chips;
}
function stopMeter(){ clearInterval(meterTimer); meterTimer=null; }

// ─────────────────────────── First-run tour ────────────────────────────────
const TOUR_KEY="leadgen_tour_done";
const TOUR_STEPS=[
  {sel:"#vertical", title:"1 · Pick what to find",
   body:"Start here — choose the type of business you want to prospect for."},
  {sel:"#market", title:"2 · Set the area",
   body:"Type any city, county, or metro, like “Austin, Texas”."},
  {sel:"#demo", title:"3 · Try a sample",
   body:"No internet? Click this to see exactly what the results look like, instantly."},
];
let tourIdx=0;
function tourSeen(){ try{ return localStorage.getItem(TOUR_KEY)==="1"; }catch(e){ return true; } }
function endTour(){
  try{ localStorage.setItem(TOUR_KEY,"1"); }catch(e){}
  document.getElementById("tour").style.display="none";
  document.querySelectorAll(".tourhi").forEach(el=>el.classList.remove("tourhi"));
}
function showTourStep(){
  document.querySelectorAll(".tourhi").forEach(el=>el.classList.remove("tourhi"));
  const step=TOUR_STEPS[tourIdx];
  const target=document.querySelector(step.sel);
  document.getElementById("tourtitle").textContent=step.title;
  document.getElementById("tourbody").textContent=step.body;
  document.getElementById("tourstep").textContent=`${tourIdx+1} / ${TOUR_STEPS.length}`;
  document.getElementById("tournext").textContent=(tourIdx===TOUR_STEPS.length-1)?"Got it":"Next →";
  const card=document.getElementById("tourcard");
  if(target){
    card.style.transform="none";
    target.classList.add("tourhi");
    if(target.scrollIntoView) target.scrollIntoView({block:"center"});
    const rb=target.getBoundingClientRect();
    let top=rb.bottom+10, left=rb.left;
    // Keep the card on-screen.
    requestAnimationFrame(()=>{
      const cw=card.offsetWidth, ch=card.offsetHeight;
      if(left+cw>window.innerWidth-12) left=Math.max(12, window.innerWidth-cw-12);
      if(top+ch>window.innerHeight-12) top=Math.max(12, rb.top-ch-10);
      card.style.left=left+"px"; card.style.top=top+"px";
    });
  } else {
    card.style.left="50%"; card.style.top="40%"; card.style.transform="translate(-50%,-50%)";
  }
}
document.getElementById("tournext").addEventListener("click", ()=>{
  tourIdx++;
  if(tourIdx>=TOUR_STEPS.length) endTour(); else showTourStep();
});
document.getElementById("tourskip").addEventListener("click", endTour);
function maybeStartTour(){
  if(tourSeen()) return;
  tourIdx=0;
  document.getElementById("tour").style.display="block";
  showTourStep();
}

loadSavedMarkets(); loadRecent(); maybeStartTour();
</script>
</body></html>"""


def main():
    port = free_port()
    print("\n" + "=" * 46)
    print(f"  Lead Engine  →  http://127.0.0.1:{port}")
    print("=" * 46 + "\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
