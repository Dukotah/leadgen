# Adding a vertical

A **vertical** is one prospecting use case: WHAT businesses to collect and HOW to
score them. The engine (collect → dedupe → enrich → suppress → score → export) is
shared; a vertical just plugs in behavior. There's no subclassing — a vertical is
a single `Vertical` dataclass you `register()`.

Drop a new module in `leadgen/verticals/`, import it from
`leadgen/verticals/__init__.py`, and it shows up automatically in `--list`, the
CLI, and the GUI.

## The `Vertical` fields

```python
Vertical(
    key="web_design",                 # CLI id (lowercase, no spaces)
    label="Local businesses that need a website",   # shown in --list / GUI
    description="One line about who this finds.",

    # --- targeting: which businesses to collect ---
    overture_categories=[],           # substring match on Overture's category; [] = all
    osm_tags=["amenity=restaurant"],  # "key=value" tags for the OSM source
    keep_chains=False,                # drop national chains (brand set) or keep them

    # --- behavior hooks (only score_fn is required) ---
    score_fn=_score,                  # rec -> (score:int, tier:str, reasons:str)
    enrich_fn=_enrich,                # rec, ctx -> rec  (visit the site, add signal)
    opener_fn=_opener,                # rec -> str        (a suggested pitch line)
    suppression_fn=None,              # cfg -> {normalized_name: competitor_label}

    config={},                        # arbitrary blob passed to your hooks
    competitor_input=None,            # GUI: {config_key, label, help} for a textarea
    columns=[("Tier","tier"), ("Business","name"), ...],   # output column order
)
```

Every hook takes and returns plain dicts, so verticals stay simple and unit-testable.

## The one required hook: `score_fn`

```python
def _score(rec: dict) -> tuple[int, str, str]:
    score, why = 0, []
    if not rec.get("website"):
        score += 60; why.append("NO WEBSITE")
    if rec.get("phone"):
        score += 4;  why.append("phone listed")
    tier = "A" if score >= 40 else "B" if score >= 15 else "C"
    return score, tier, "; ".join(why)
```

Return `(score, tier, reasons)`. Tier is just a label you choose — `web_design`
uses A/B/C, and the XLSX exporter color-codes those three. The engine sorts leads
by `score` descending.

## The record shape

Collectors hand your hooks a normalized dict:

```python
{ "name", "category", "website", "phone", "email", "address",
  "city", "state", "zip", "lat", "lon", "brand", "source", "source_url" }
```

Your `enrich_fn` can add any keys it likes; `score_fn` reads whatever it needs;
`columns` decides what lands in the output.

## Optional: enrich each site (`enrich_fn`)

`enrich_fn(rec, ctx)` runs in a thread pool (capped by `--enrich-cap`). Use the
shared helpers in `leadgen/audit.py` and `leadgen/enrich.py`:

```python
from ..audit import audit_website, audit_from_html, is_weak_url
from ..enrich import fetch_pages, estimate_roster, find_decision_maker, find_phrases

def _enrich(rec, ctx):
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return rec
    # Demo/offline support: if ctx provides bundled HTML, score that instead of
    # fetching — lets `--demo` and the GUI "Try a sample" button run with no network.
    demo_html = (ctx or {}).get("demo_html")
    if demo_html is not None:
        rec["audit"] = audit_from_html(demo_html(site), site, reachable=bool(demo_html(site)))
    else:
        rec["audit"] = audit_website(site)
    return rec
```

`audit_website` reports `reachable / https / mobile_viewport / load_ms / builder`
(Wix, Squarespace, …). `estimate_roster` / `find_decision_maker` extract team size
and a likely owner from a site's team page. See `web_design.py` for a complete,
working example.

## Optional: a pitch line (`opener_fn`)

```python
def _opener(rec):
    if not rec.get("website"):
        return "No website — pitch a one-page site that ranks on Google."
    return "Has a site — verify quality before pitching."
```

## Optional: competitor suppression (`suppression_fn`)

If your competitors publish client/testimonial lists, you can drop businesses
already using them. Wire `suppression_fn` to `build_suppression_set` and expose a
`competitor_input` so the GUI shows a paste box:

```python
from ..suppression import build_suppression_set

def _suppress(cfg):
    return build_suppression_set(cfg.get("competitor_urls", {}))
```

Suppressed leads are flagged and sunk in scoring — kept (not deleted) so you can
re-approach when a contract lapses. The engine sets `rec["suppressed"]` /
`rec["suppressed_by"]` before calling your `score_fn`.

## Register it

```python
# bottom of leadgen/verticals/my_vertical.py
from .. import register, Vertical
register(Vertical(key="my_vertical", label="…", score_fn=_score, columns=[...]))
```

```python
# leadgen/verticals/__init__.py
from . import web_design   # noqa: F401
from . import my_vertical  # noqa: F401
```

Then:

```bash
python -m leadgen --list
python -m leadgen --vertical my_vertical --market "Denver, Colorado"
```

## Test it offline

Mirror the existing tests: feed your `score_fn` hand-built records and your
`enrich_fn` HTML fixtures (see `leadgen/tests/`). No network needed, so they run
anywhere — including CI.
