# Cookbook — recipes by use case

One worked example per use case. Each recipe is a real CLI command, what it does,
and which **sources** + **vertical** it leans on. Everything here uses flags that
actually exist:

```text
--list            list available verticals and exit
--vertical KEY    which vertical to run (see --list)
--market M        a saved key (austin_tx, phoenix_az, tampa_fl, sonoma_county_ca)
                  or any geocodable place name ("Boulder, Colorado")
--sources ...     one or more of: overture osm socrata npi foursquare arcgis
--limit N         cap businesses collected
--enrich-cap N    enrich only the top-N businesses (default 150; cost control)
--no-enrich       skip per-site enrichment entirely
--out STEM        output stem → writes <stem>_crm.csv and <stem>.xlsx
```

There is **no** `--enrich`, `--taxonomy`, `--dataset`, or `--exclude` flag.
Enrichment is **on by default** (turn it *off* with `--no-enrich`). Source-specific
targeting (NPI specialties, Socrata datasets, ArcGIS layers) is set in the
**vertical's `config`**, not on the command line — see the recipes that need it.

Output is always `<stem>_crm.csv` (flat, import-ready) + `<stem>.xlsx` (Tier
A/B/C colored, with score, reason, and a suggested opener per lead).

---

## 1. Local businesses with no website in a city

The flagship use case: find shops/trades/offices that have no site, a social-only
page, or a weak/slow DIY site — prime web-design prospects.

```bash
python -m leadgen --vertical web_design --market "Boulder, Colorado" \
  --sources overture osm --out boulder_web
```

- **Vertical:** `web_design` (audits each site, tiers A/B/C, drafts a pitch).
- **Sources:** `overture` (bulk national listings) + `osm` (live, broad coverage
  of every named shop/craft/office and key amenities). Together they give you the
  widest net of real local businesses.
- `overture` needs `duckdb` (`pip install duckdb`); `osm` needs nothing.

---

## 2. Healthcare providers needing a site

Dentists, clinics, chiropractors, PT, optometry — pulled from CMS's NPI registry,
which carries **no website field by design**, so every record is a "needs a site"
candidate.

```bash
python -m leadgen --vertical web_design --market austin_tx \
  --sources npi --out austin_healthcare
```

- **Source:** `npi` (the NPPES registry; no key, needs a US **city + state**, so
  use a market that resolves to one).
- **Narrowing to specialties:** filter taxonomies via the vertical's config, e.g.
  `config["npi_taxonomies"] = ["Dentist", "Chiropractor"]`. Set this in your
  vertical file (or pass it through `run_pipeline(..., config_override=...)` from
  the library API) — there's no CLI flag for it.
- Because NPI records have no website, expect most to land in **Tier A** ("NO
  WEBSITE"); `--no-enrich` is reasonable here since there's usually no site to
  audit.

---

## 3. New / just-licensed businesses

Brand-new businesses that don't have a website yet — they show up in city/county
**business-license** open data before they show up on a map.

```bash
python -m leadgen --vertical web_design --market "Chicago, Illinois" \
  --sources socrata --out chicago_new
```

- **Source:** `socrata` (recently-licensed businesses from Socrata open-data
  portals; no key). Coverage is per-jurisdiction and patchy, so pick a market with
  a strong portal — **Chicago** and **Los Angeles** are good bets.
- With no explicit dataset configured, `socrata` searches the Discovery API for
  the market's locality and reads the best-matching license/registration datasets.
  For reliable results, point it at a dataset you trust (next recipe).

---

## 4. Pull from a specific open-data portal you found

When you've found an exact dataset or layer, skip the fuzzy search and read it
directly. This is config-driven (set on the vertical), not a CLI flag.

**Socrata** — give it the portal domain + dataset id:

```python
config["socrata_datasets"] = [
    {"domain": "data.cityofchicago.org", "id": "r5kz-chrr"},
]
```

**ArcGIS** — give it a public layer query URL ending in `.../FeatureServer/0`
(find one at hub.arcgis.com → a dataset's *View API Resources* → the service URL):

```python
config["arcgis_layers"] = [
    "https://services.arcgis.com/EXAMPLE/arcgis/rest/services/Business_Licenses/FeatureServer/0",
]
```

Then run with the matching source:

```bash
python -m leadgen --vertical web_design --market "Chicago, Illinois" \
  --sources socrata --out chicago_portal

python -m leadgen --vertical web_design --market "Los Angeles, California" \
  --sources arcgis --out la_portal
```

- **Sources:** `socrata` and/or `arcgis`, both no-key open-government data.
- When you pass explicit datasets/layers, the source reads them directly instead
  of guessing — the reliable path for a portal you already know.

---

## 5. A deep one-off pass with Foursquare

Foursquare's open mirror (~100M places, with website/phone/social fields) is the
**deepest** coverage — and the **slowest**. The mirror can't be pruned by area, so
each query scans the whole dataset (~1–2 min). Use it as an opt-in deep pass, not
a default.

```bash
python -m leadgen --vertical web_design --market "Sonoma County, California" \
  --sources foursquare --limit 500 --out sonoma_deep
```

- **Source:** `foursquare` (no key; needs `duckdb`). It's a frozen **2024-11-19**
  snapshot — treat it as a point-in-time deep sweep.
- Use `--limit` to keep the result set sane, and don't loop this in a script — one
  deliberate pass at a time.

---

## 6. Skip businesses already in your CRM

Don't re-surface leads you already have. CRM de-dupe happens through the
**library API** (`exclude_names`) or the **GUI's CRM upload box** — there is no
CLI flag for it.

**GUI:** on the run screen, upload your existing CRM export (CSV); matching company
names are removed from the results before you ever see them.

**Library / script:**

```python
from leadgen import get_vertical, run_pipeline
from leadgen.pipeline import load_crm_names

known = load_crm_names("my_existing_crm.csv")   # normalized company names
run_pipeline(
    get_vertical("web_design"),
    market="austin_tx",
    sources=("overture", "osm"),
    exclude_names=known,         # matches are removed, not just flagged
    out_stem="austin_new_only",
)
```

- `load_crm_names` reads the first company/business/name-looking column (falls back
  to the first column); it also accepts raw CSV text with `is_text=True`.
- Enrichment (`enrich=`, `enrich_cap=`) and everything else work the same as the
  CLI — the CLI is just a thin wrapper over `run_pipeline`.

---

## 7. Run the offline demo

See real tiered output before your first live scrape — runs the full pipeline on
five bundled sample businesses **offline**, no network:

```bash
python -c "from leadgen import get_vertical, run_pipeline; \
run_pipeline(get_vertical('web_design'), market='(demo)', demo=True)"
```

- No sources hit the network; enrichment scores bundled HTML fixtures instead of
  fetching. (The GUI's **"Try a sample"** button does the same thing.)

---

## 8. Add your own vertical

The recipes above all ride on `web_design`, but a vertical is just a single
dataclass you `register()` — drop one file in `leadgen/verticals/` and it shows up
in `--list`, the CLI, and the GUI automatically.

```bash
python -m leadgen --list                              # confirm yours appears
python -m leadgen --vertical my_vertical --market "Denver, Colorado"
```

- Full walkthrough — `score_fn`, the optional `enrich_fn` / `opener_fn` /
  `suppression_fn`, the record shape, and offline testing — is in
  **[`docs/ADD_A_VERTICAL.md`](ADD_A_VERTICAL.md)**.
- The reference implementation is
  [`leadgen/verticals/web_design.py`](../leadgen/verticals/web_design.py).

---

## Mix-and-match cheatsheet

```bash
# Widest live net, fast (skip the per-site audit)
python -m leadgen --vertical web_design --market phoenix_az \
  --sources overture osm --no-enrich --limit 300 --out phoenix_fast

# Combine maps + government data in one run
python -m leadgen --vertical web_design --market "Boulder, Colorado" \
  --sources overture osm socrata npi --out boulder_all

# Cap the audit cost on a big market
python -m leadgen --vertical web_design --market tampa_fl \
  --sources osm --enrich-cap 50 --out tampa_top50
```

Before you contact anyone you find here, read
**[`docs/RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md)** — source attribution and
anti-spam basics.
