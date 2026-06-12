<p align="center">
  <img src="docs/img/banner.svg" alt="leadgen — free, no-key local-business lead generation" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Dukotah/leadgen/releases/latest"><img src="https://img.shields.io/github/v/release/Dukotah/leadgen?color=28a745&label=download%20app&style=flat-square" alt="Download"></a>
  <a href="https://github.com/Dukotah/leadgen/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Dukotah/leadgen/ci.yml?branch=main&label=tests&style=flat-square" alt="Tests"></a>
  <img src="https://img.shields.io/badge/API%20keys-none-28a745?style=flat-square" alt="No API keys">
  <img src="https://img.shields.io/badge/python-3.10%2B-1f4e78?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-1f4e78?style=flat-square" alt="MIT License">
</p>

<p align="center">
  <b>Find scored local-business leads from free public data — no API keys, no accounts, runs on your machine.</b>
</p>

One pipeline — **collect → dedupe → enrich → suppress → score → export** — driven
by swappable **verticals**. A *vertical* describes WHAT you're prospecting for and
HOW to score it; the engine handles everything else. Point it at any geocodable
market on Earth, pull businesses from 10 free no-key data sources, audit their
websites, and get a CRM-ready CSV + a color-tiered spreadsheet.

```text
        ┌── Overture · OpenStreetMap · Foursquare        ┌── score_fn  → A / B / C + reasons
data ───┤  Socrata · NPI · ArcGIS · Wikidata · your CSV  ├── enrich_fn → audit each site
        └── (10 sources, zero API keys)        vertical ─┘── opener_fn → a suggested pitch
                          │                                        │
            collect → dedupe → enrich → suppress → score → export → CSV + XLSX
```

**19 ready-made verticals** (web design, SEO, social-only, restaurants, home
services, healthcare, and more — `python -m leadgen --list`), or add your own in a
single file.

---

## ⬇️ Just want to run it? (no coding)

Download the desktop app for your computer, double-click, done — no Python, no setup:

- **Windows** → `LeadEngine-windows.exe`
- **macOS** → `LeadEngine-macos`
- **Linux** → `LeadEngine-linux`

Grab the latest from the [**Releases**](../../releases) page. It opens a simple
window: pick what to find and where, click **Find leads**, download a spreadsheet.
There's a **“Try a sample”** button that works with no internet so you can see
exactly what you'll get first. (Unsigned binaries trip Windows SmartScreen / macOS
Gatekeeper once — "Run anyway" / right-click → Open. See [`gui/BUILD_EXE.md`](gui/BUILD_EXE.md).)

The rest of this README is for people who want to script it or extend it.

---

## Quick start

```bash
pip install -r requirements.txt

python -m leadgen --list                      # show available verticals
python -m leadgen --vertical web_design --market austin_tx --out austin_web
python -m leadgen --vertical web_design --market "Boulder, Colorado" --sources overture osm
```

A market is either a **saved key** (`austin_tx`, `phoenix_az`, `tampa_fl`,
`sonoma_county_ca`) or **any place name we geocode on the fly** (`"Boulder, Colorado"`).
Output: `<stem>_crm.csv` (flat, import-ready) and `<stem>.xlsx` (Tier A/B/C colored,
with score, reason, and a suggested opener per lead).

### See it work with zero setup

```bash
python -c "from leadgen import get_vertical, run_pipeline; \
run_pipeline(get_vertical('web_design'), market='(demo)', demo=True)"
```

Demo mode runs the full pipeline on five bundled sample businesses **offline** —
no network — so you see real tiered output before your first live scrape:

```text
 Tier  Score  Business               Why it's a lead
 ────  ─────  ─────────────────────  ───────────────────────────────────────────
  A      64   Summit Plumbing Co     NO WEBSITE; phone listed
  A      54   Old Town Auto Repair   site unreachable; phone listed
  B      48   Sunrise Cafe           no HTTPS; not mobile-friendly; DIY (Wix)
  A      44   Bella Hair Studio      social-only (facebook.com); phone listed
  C       4   Evergreen Dental       real site, no obvious issues
```

Each lead also gets a phone, website, address, and a suggested opener in the CSV/XLSX.

### Point-and-click GUI

No command line needed: pick a vertical + market, optionally upload a CRM to
de-dupe, hit Run, watch live progress, download the CSV/XLSX. There's a **“Try a
sample”** button (the offline demo) and a **“Check my connection”** button that
tests each data source in plain English.

```bash
pip install -r gui/requirements.txt
cd gui && ./run.sh            # browser mode  (run.bat on Windows)
# or a native desktop window:
python gui/desktop_app.py
```

It can also be packaged as a single double-click `LeadEngine.exe` (no Python
needed) — see [`gui/BUILD_EXE.md`](gui/BUILD_EXE.md). See [`gui/README.md`](gui/README.md).

---

## Data sources

All free, **no API keys**. Each returns the same normalized record shape, so the
rest of the pipeline is source-agnostic. Pick any combination with `--sources`:

| Source | What it is | Needs | License |
|---|---|---|---|
| **overture** | Meta/Microsoft/Amazon's open Places dataset, by bbox over S3 | `duckdb` | CC-BY 4.0 |
| **osm** | live businesses via Overpass — every named shop/craft/office + key amenities | nothing | ODbL |
| **socrata** | recently-licensed businesses from city/county Socrata open-data portals | nothing | per-portal |
| **npi** | every US healthcare provider (dentists/doctors/clinics/pharmacies) from CMS's registry | nothing | public domain |
| **arcgis** | business-license layers published on ArcGIS (point it at a layer URL) | nothing | per-publisher |
| **foursquare** | ~100M places w/ website+phone+socials via the open source.coop mirror | `duckdb` | Apache-2.0 |

```bash
python -m leadgen --vertical web_design --market "Boulder, Colorado" --sources overture osm socrata npi
```

Notes:
- **osm** is the broadest no-key *live* source — all shops, trades, offices, and
  business-y amenities (restaurants, clinics, hotels, …), not a hardcoded list.
- **npi** has no website field by design, which makes its records prime
  "needs-a-website" leads. Filter specialties with `config["npi_taxonomies"]`
  (e.g. `["Dentist", "Chiropractor"]`).
- **socrata** / **arcgis** are open *government* data: structured but per-
  jurisdiction and patchy. Point them at specific datasets via
  `config["socrata_datasets"]` / `config["arcgis_layers"]` (a `…/FeatureServer/0`
  URL from hub.arcgis.com) for reliable results.
- **foursquare** is the deepest coverage *and the slowest* — the open mirror can't
  be pruned by area, so a query scans the whole dataset (~1–2 min). It's a frozen
  2024-11-19 snapshot. Use it as an opt-in deep pass, not your default. (Foursquare's
  own live S3 bucket is now account-gated; the source.coop mirror is the no-key path.)

---

## Add your own vertical

A vertical is a plain dataclass — no subclassing. Drop one file in
`leadgen/verticals/`, call `register(...)`, and it appears in the CLI and GUI:

```python
from leadgen import register, Vertical

def _score(rec):
    score, why = 0, []
    if not rec.get("website"):
        score += 60; why.append("NO WEBSITE")
    return score, ("A" if score >= 40 else "C"), "; ".join(why)

register(Vertical(
    key="my_vertical",
    label="What I'm prospecting for",
    osm_tags=["shop=bakery", "amenity=cafe"],
    score_fn=_score,
    columns=[("Tier", "tier"), ("Score", "score"), ("Business", "name"),
             ("Phone", "phone"), ("Website", "website"), ("Why", "why")],
))
```

Optional hooks: `enrich_fn` (visit each site for more signal), `opener_fn` (draft
a pitch), `suppression_fn` (drop businesses already served by a competitor). The
full walkthrough — including the optional website-audit and competitor-suppression
helpers — is in **[`docs/ADD_A_VERTICAL.md`](docs/ADD_A_VERTICAL.md)**, and
[`leadgen/verticals/web_design.py`](leadgen/verticals/web_design.py) is the
reference implementation.

---

## Tests

Pure-logic and offline end-to-end tests, no network required:

```bash
python leadgen/tests/test_engine.py
python leadgen/tests/test_features.py
python leadgen/tests/test_heuristics.py
python gui/test_gui.py          # skips cleanly if Flask isn't installed
# or, with pytest:
pytest leadgen/tests -q
```

---

## Use it responsibly

This is a prospecting tool for **your own outreach**. A few ground rules baked
into the design and worth stating plainly:

- **It ships no data.** The repo is a tool; lead files are generated per run and
  are git-ignored. Don't commit scraped contact data to a public repo.
- **Respect the sources.** Overture is CC-BY (credit "Overture Maps Foundation"
  in derived work); OSM is ODbL. The website audit fetches each homepage once with
  a polite, identifiable user-agent — set `LEADGEN_UA` to your own contact string.
- **Mind the law where you operate.** Reselling scraped personal contact data can
  trigger data-broker registration (e.g. California's DELETE Act) and anti-spam
  rules (CAN-SPAM, CASL, GDPR). Generating a call list for your own business is a
  very different thing from selling one — know which you're doing.

Full guidance, per-source licenses, and attribution notes: [`docs/RESPONSIBLE_USE.md`](docs/RESPONSIBLE_USE.md).

---

## More docs

- [`docs/COOKBOOK.md`](docs/COOKBOOK.md) — worked recipes, one per use case
- [`docs/ADD_A_VERTICAL.md`](docs/ADD_A_VERTICAL.md) — build your own vertical
- [`docs/RESPONSIBLE_USE.md`](docs/RESPONSIBLE_USE.md) — licenses, attribution, anti-spam
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — 100 planned improvements
- [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CHANGELOG.md`](CHANGELOG.md)

---

## License

MIT — see [`LICENSE`](LICENSE). Data you collect carries its source's license
(Overture: CC-BY 4.0; OSM: ODbL); attribute accordingly if you publish derived work.
