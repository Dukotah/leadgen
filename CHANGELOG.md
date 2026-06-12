# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project aims for
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Five more verticals: `restaurants`, `home_services`, `no_ssl`,
  `healthcare_web`, `directory_only` (eight total).
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
