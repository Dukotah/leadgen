# Lead Engine — GUI

A point-and-click front end over the [`leadgen`](../leadgen) engine. Pick a
**vertical** (what to prospect for), a **market** (where), optionally paste
competitor pages to skip their clients or upload a CRM to de-dupe, hit **Run**,
watch live progress, and download a CRM-ready CSV + a color-tiered XLSX.

## Run it

**Browser mode (simplest):**
```bash
cd gui
./run.sh            # macOS/Linux  (run.bat on Windows)
# then open the URL it prints, e.g. http://127.0.0.1:5000
```

**Native desktop window:**
```bash
pip install -r gui/requirements.txt
python gui/desktop_app.py
```

## What each control does
- **Vertical** — which prospecting use case to run (ships with `web_design`; add
  your own — see [`docs/ADD_A_VERTICAL.md`](../docs/ADD_A_VERTICAL.md)). The
  description and any competitor box update to match the selected vertical.
- **Market** — a saved key (e.g. `austin_tx`) or any place name we geocode on the
  fly (e.g. `"Boulder, Colorado"`).
- **Data sources** — *Overture* (bulk national dataset, needs `duckdb`) and/or
  *OpenStreetMap* (live, no extra deps).
- **Skip competitors' clients** *(only shown if the vertical defines it)* — paste
  each rival's testimonial / "clients we serve" URL. We scrape them and drop any
  business already using a competitor.
- **Skip people already in your CRM** — upload a `.csv`; matches on company name
  are removed so you never get a duplicate.
- **Enrich** — visit each business's site to audit it (HTTPS, mobile, speed, DIY
  builder). Richer data, slower. **Enrich cap** limits how many sites are visited;
  **Collect limit** caps how many businesses are pulled.

Output files are written to `gui/_output/` and offered as downloads. The app
bundles no lead data — everything is generated fresh per run.

## Network note
The collectors call out to Overture (AWS S3), Overpass (OSM), and DuckDuckGo.
Some locked-down/cloud IPs block these (you'll see `HTTP 403` or S3 errors in the
log). If that happens, run from a normal network connection — or click
**“Try a sample”** to see the full flow offline.
