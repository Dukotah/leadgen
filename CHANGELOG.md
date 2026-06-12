# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project aims for
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Six more verticals: `ecommerce_ready`, `booking_gap`, `outdated_site`,
  `social_media_mgmt`, `new_business`, `restaurant_menu_gap` (**14 total**).
- Four more no-key sources via `leadgen/extra_sources.py`: `wikidata`, `ckan`,
  `localfile` (your own CSV/XLSX), `url_csv` (a public CSV URL) — wired into the
  pipeline and CLI.
- Config files: `leadgen.toml` support (`--config`, auto-found) with `load_config`
  / `merge_config`; see `leadgen.example.toml`.
- Extra export formats (`--format`): JSON Lines, JSON, vCard, per-tier CSVs, and a
  Markdown report — `leadgen/exporters.py` (+ CRM header presets).
- `leadgen/cache.py` — optional on-disk TTL cache for HTTP responses.
- GUI: dark mode, sortable/choosable columns, click-to-call / mailto + copy,
  export-the-filtered-view, and mark-contacted/not-interested (localStorage).
- Docs site scaffolding (`mkdocs.yml`, `docs/index.md`), `mypy.ini`, screenshots
  placeholder. `.gitignore` now also blocks `*.json`/`*.vcf`/`*.leads.md` and real
  `leadgen.toml` configs.
- Five more verticals: `restaurants`, `home_services`, `no_ssl`,
  `healthcare_web`, `directory_only`.
- `leadgen/signals.py` — website-signal helpers (email finder, copyright-year,
  e-commerce / booking detection, social-handle extraction, domain-resolves).
- `leadgen/quality.py` — phone normalization, junk-name filtering, haversine /
  geo-proximity, and cross-source dedupe (merge by phone, or same-name + nearby).
- Pipeline now normalizes phone numbers and de-duplicates **across** sources.
- Packaging: `pyproject.toml` (pip/pipx install + ruff/black config), `Dockerfile`,
  `.dockerignore`, `.pre-commit-config.yaml`.
- Project health: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  issue/PR templates, and a CI workflow that runs the test suites on every push/PR.
- Docs: `docs/ROADMAP.md` (100 build-on items), `docs/RESPONSIBLE_USE.md`,
  `docs/COOKBOOK.md`.

## [1.0.0] - 2026-06-11

### Added
- Universal pipeline: collect → dedupe → enrich → suppress → score → export,
  driven by swappable **verticals** (a dataclass + `register()`).
- Verticals: `web_design`, `seo_audit`, `social_only`.
- Six no-key data sources: `overture`, `osm` (broadened to all shops/crafts/
  offices + key amenities), `socrata`, `npi`, `arcgis`, `foursquare` (deep/slow).
- Website auditing (HTTPS / mobile / load / DIY-builder) and optional
  competitor-suppression + CRM de-dupe.
- Three ways to run: Python library, CLI (`python -m leadgen`), and a Flask /
  desktop GUI; plus an offline demo mode.
- CRM-ready CSV + color-tiered XLSX export.
- Cross-platform desktop-app build workflow (Windows / macOS / Linux) and an
  offline test suite.

[Unreleased]: https://github.com/Dukotah/leadgen/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Dukotah/leadgen/releases/tag/v1.0.0
