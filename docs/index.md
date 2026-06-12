# leadgen docs

**leadgen** is a universal, key-free local-business lead engine. One pipeline —
**collect → dedupe → enrich → suppress → score → export** — driven by swappable
**verticals**. No API keys, no accounts; it runs on your machine and exports a
CRM-ready CSV plus a color-tiered XLSX.

The full project overview, quick start, and data-source table live in the
repository **[README](https://github.com/)** (`README.md` at the repo root). Start
there if you're new.

## Pages

- **[Cookbook](COOKBOOK.md)** — worked recipes, one real CLI command per use case.
- **[Add a vertical](ADD_A_VERTICAL.md)** — build your own vertical (a plain
  dataclass: what to prospect for and how to score it).
- **[Responsible use](RESPONSIBLE_USE.md)** — per-source licenses, attribution,
  and anti-spam guidance.
- **[Roadmap](ROADMAP.md)** — planned build-on improvements.
- **[Screenshots](SCREENSHOTS.md)** — where to add GUI screenshots/GIFs.

## Run it in one line

```bash
python -m leadgen --list                                   # show verticals
python -m leadgen --vertical web_design --market austin_tx --out austin_web
```

Or see the full pipeline run offline on bundled samples, no network:

```bash
python -c "from leadgen import get_vertical, run_pipeline; \
run_pipeline(get_vertical('web_design'), market='(demo)', demo=True)"
```
