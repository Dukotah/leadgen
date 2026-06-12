# Contributing to leadgen

Thanks for helping out. leadgen is a key-free, local-business lead engine built
around one pipeline (**collect → dedupe → enrich → suppress → score → export**)
and swappable **verticals**. Most contributions are a single new file — a vertical
or (eventually) a source — plus a test. This guide covers setup, conventions, and
the few hard rules that keep the project honest.

---

## Setup

```bash
pip install -r requirements.txt        # the engine + CLI
pip install -r gui/requirements.txt    # only if you touch the GUI / desktop app
```

That's it — no API keys, no accounts. Confirm it works offline:

```bash
python -c "from leadgen import get_vertical, run_pipeline; \
run_pipeline(get_vertical('web_design'), market='(demo)', demo=True)"
```

Demo mode runs the full pipeline on five bundled sample businesses with no
network, so you get real tiered output before touching a live source.

---

## Tests

Tests are pure-logic and offline end-to-end — no network required. Run them
directly or under pytest:

```bash
python leadgen/tests/test_engine.py
python leadgen/tests/test_features.py
python leadgen/tests/test_heuristics.py
python leadgen/tests/test_verticals.py
python leadgen/tests/test_sources.py
python gui/test_gui.py          # skips cleanly if Flask isn't installed
# or, all at once:
pytest leadgen/tests -q
```

Test functions are named `test_*` so pytest collects them automatically. CI runs
`pytest leadgen/tests -q` and `python gui/test_gui.py` on every push and PR — keep
both green.

---

## Adding a vertical

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

Optional hooks: `enrich_fn`, `opener_fn`, `suppression_fn`. The full walkthrough —
including the website-audit and competitor-suppression helpers — is in
[`docs/ADD_A_VERTICAL.md`](docs/ADD_A_VERTICAL.md), and
[`leadgen/verticals/web_design.py`](leadgen/verticals/web_design.py) is the
reference implementation. Add a small test in `leadgen/tests/` that exercises your
`score_fn` against a couple of representative records.

Adding a data source follows the same spirit (one normalized record shape so the
rest of the pipeline stays source-agnostic); look at the existing sources before
proposing a new one.

---

## Coding conventions

- **Python, standard library first.** Match the surrounding style — short
  functions, plain dataclasses, descriptive names.
- **Keep records normalized.** Every source emits the same record shape; verticals
  read from it. Don't leak source-specific fields downstream.
- **Fail soft on the network.** A flaky source should degrade gracefully, not crash
  a run.
- **Be polite to sources.** The website audit fetches each homepage once with an
  identifiable user-agent (`LEADGEN_UA`). Don't add aggressive crawling.

---

## The hard rules

These are baked into the project's identity. PRs that break them won't be merged:

- **Never commit data.** The repo is a tool; lead files are generated per run and
  are git-ignored. Do not commit scraped contact data, sample dumps, or fixtures
  built from real businesses.
- **Stay key-free.** No source may require an API key, account, or paid service.
  If a source goes account-gated, find the no-key path or drop it.
- **No ToS-violating scraping.** We pull from open datasets and APIs (Overture,
  OSM/Overpass, Socrata, NPI, ArcGIS, the Foursquare open mirror) and fetch a
  business's own homepage once. We do not scrape ToS-protected sites.
- **Respect source licenses.** Overture is CC-BY (attribute "Overture Maps
  Foundation"); OSM is ODbL. Attribute derived work accordingly.

---

## Pull request expectations

- **Tests pass** — `pytest leadgen/tests -q` and `python gui/test_gui.py` both
  green. Add tests for new logic.
- **No new required dependencies without discussion.** Part of the appeal is that
  the engine installs with a short `requirements.txt`. Optional, lazily-imported
  deps for a single source (the way `duckdb` is optional today) are fine to
  propose; new always-on deps need a conversation first — open an issue.
- **Stay within the hard rules above.**
- **Update docs** when you change behavior — README and `docs/` should stay
  accurate. Add a line to `CHANGELOG.md` under **Unreleased**.

Open an issue first for anything large (new source, new dependency, pipeline
change) so we can agree on the shape before you build it. Small, focused PRs are
easiest to review.
