# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project aims for
[Semantic Versioning](https://semver.org/).

## [Unreleased]

_Nothing yet — see the [roadmap](docs/ROADMAP.md)._

## [1.0.0] - 2026-06-11

The first release. A universal, **key-free** local-business lead engine.

### Engine
- Pipeline: collect → dedupe → enrich → suppress → score → export, driven by
  swappable **verticals** (a dataclass + `register()`).
- Phone normalization, closed-business filtering, and **cross-source dedupe**
  (merge by phone, or same-name + nearby). Optional helpers: address parsing,
  chain detection, field-confidence, do-not-contact lists, cross-run dedupe.
- Website auditing (HTTPS / mobile / load / DIY-builder), website signals (email
  finder, copyright-year, e-commerce / booking detection, social handles), and a
  0–100 scoring helper with reason tags.
- Reliability + history: retry/backoff, per-host rate limiting, parallel collect,
  an optional TTL HTTP cache, and a SQLite run store.

### 19 verticals
`web_design`, `seo_audit`, `social_only`, `restaurants`, `home_services`,
`no_ssl`, `healthcare_web`, `directory_only`, `ecommerce_ready`, `booking_gap`,
`outdated_site`, `social_media_mgmt`, `new_business`, `restaurant_menu_gap`,
`auto_services`, `fitness_wellness`, `pet_services`, `beauty`,
`professional_services` — plus a scaffolder (`scripts/new_vertical.py`).

### 10 no-key data sources
`overture`, `osm` (all shops/crafts/offices + key amenities), `socrata`, `npi`
(healthcare), `arcgis`, `foursquare` (deep/slow mirror), `wikidata`, `ckan`,
`localfile` (your own CSV/XLSX), `url_csv` (a public CSV URL).

### Ways to run
- Python library, CLI (`python -m leadgen`, with `--count`, `--list-markets`,
  `--format`, `--config`, `--weight`, `--json-summary`, quiet/verbose/log-file),
  a Flask / desktop GUI, and an offline demo.
- GUI: live search, sortable/choosable columns, recent runs, run queue, dark
  mode, settings, first-run tour, click-to-call / copy, mark-contacted,
  export-the-filtered-view.

### Output & config
- CRM-ready CSV + color-tiered XLSX, plus JSON/JSONL, vCard, per-tier splits, a
  Markdown report, TSV, CRM-header presets, de-duplicated master-CSV append, and
  outreach opener templates.
- `leadgen.toml` config files (see `leadgen.example.toml`).

### Packaging & project health
- `pyproject.toml` (pip/pipx + ruff/black), `Dockerfile`, pre-commit, mypy,
  cross-platform build workflow, and CI running the suites on every push/PR.
- Docs: README, COOKBOOK, ADD_A_VERTICAL, RESPONSIBLE_USE, ROADMAP (100 items),
  TESTING; CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, issue/PR templates.
- ~245 offline tests across 21 suites (incl. recorded-response source tests) + a
  GUI end-to-end test. The repo ships **no scraped data** (enforced by
  `.gitignore`).

[Unreleased]: https://github.com/Dukotah/leadgen/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Dukotah/leadgen/releases/tag/v1.0.0
