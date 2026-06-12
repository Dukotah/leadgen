# leadgen roadmap

100 build-on items, all within the project's hard constraints:
**no API keys · no ToS-violating scraping · no paid services · never commit scraped
data · runnable locally by developers (CLI/lib) and non-technical users (GUI/exe).**

Tags: `(quick)` = small/self-contained · `(v1.1)` = proposed for the next release
milestone (see the bottom). Numbers are stable IDs, not priority order.

---

## A. Data sources (more key-free reach)

1. `(quick)` **Local file source** — load a user's own CSV/XLSX of businesses and run it through scoring (BYO data, reuses the column mapper).
2. **Generic URL/CSV source** — point at any public CSV of businesses and map columns heuristically (huge flexibility, zero new infra).
3. **CKAN connector** — data.gov + city CKAN portals for business datasets (parallels the Socrata source).
4. **Wikidata SPARQL source** — notable/branded local businesses with websites (sparse but free).
5. `(v1.1)` **Source registry** — refactor `sources.py` into a pluggable `Source` dataclass + registry (mirror the verticals pattern) so new sources are one file.
6. **ArcGIS Hub auto-search** — best-effort discovery of license layers by city, layered on top of the reliable config-driven URLs.
7. **Foursquare H3 partition pruning** — precompute which mirror partitions cover a bbox to cut the ~1–2 min full scan down to seconds.
8. **Overture confidence filtering** — use Overture's `confidence`/`update_time` to drop low-quality or stale rows.
9. **Nominatim category fallback** — structured category lookup for tiny markets where Overpass returns little.
10. `(quick)` **Per-source result attribution in output** — keep a `sources` list when a lead is merged across providers.

## B. New verticals (more prospecting use cases)

11. `(v1.1)` **`restaurants`** — category-filtered web_design (demonstrates category targeting).
12. **`home_services`** — plumbers/electricians/HVAC/roofers (high-value web-design niche).
13. **`healthcare_web`** — NPI-sourced providers needing a website (pairs with the `npi` source).
14. `(quick)` **`no_ssl`** — businesses on `http://` only (security/SSL pitch).
15. **`directory_only`** — businesses whose only link is a Yelp/YP directory page.
16. **`new_business`** — recently-licensed businesses (socrata/npi/arcgis), scored by recency.
17. **`ecommerce_ready`** — retail shops with no online store (Shopify/web upsell).
18. **`social_media_mgmt`** — weak/inactive social presence (for SMM sellers).
19. **`outdated_site`** — stale copyright year / old framework (neglect signal).
20. **`booking_gap`** — service businesses with no online scheduling (Calendly/Square gap).
21. `(quick)` **`restaurant_menu_gap`** — restaurants with no menu/online-ordering link.
22. **Vertical scaffolder** — `python -m leadgen new-vertical <name>` writes a starter vertical file.

## C. Enrichment & scoring

23. `(v1.1)` **Email finder helper** — homepage + `/contact` email scrape as a reusable enrich helper (was in the original tool).
24. **Email deliverability** — MX-record DNS check on found emails (no key) to cut bounces.
25. **Copyright-year read** — extract footer `© YYYY` → "stale since" signal.
26. **Booking/scheduling detection** — Calendly/Square/Acuity presence (gap = opportunity).
27. **E-commerce/cart detection** — Shopify/Woo/cart keywords.
28. **Contact-method detection** — form vs. `mailto:` vs. none.
29. **Fuller builder/CMS fingerprints** — more platforms + versions in `audit.py`.
30. **Social-handle extraction** — pull FB/IG/LinkedIn from a site for outreach context.
31. **Lightweight performance signals** — TTFB, total bytes, request count from the single fetch.
32. **Robust mobile check** — viewport + responsive-CSS hints, not just the meta tag.
33. **Score normalization** — calibrate every vertical to a documented 0–100 rubric.
34. `(quick)` **"Why" reasons as structured tags** — keep machine-readable reason codes alongside the prose.

## D. Data quality, dedupe & accuracy

35. `(v1.1)` **Cross-source dedupe** — merge by name + phone + geo proximity, not just name.
36. `(quick)` **Phone normalization** — E.164 for dedupe + dialing.
37. **Address parsing/normalization** — split/standardize addresses (no-key parser).
38. **Geo-dedupe** — merge records within N meters with similar names.
39. **Closed-business filtering** — honor `date_closed` (Overture/FSQ) and `disused:`/`abandoned:` (OSM).
40. **Better chain detection** — brand lists + name patterns beyond the `brand` field.
41. `(quick)` **Junk-name filtering** — drop placeholder/profane/empty names.
42. **Field-confidence flags** — mark which fields are verified vs. guessed.
43. **Do-not-contact list** — import a suppression CSV beyond CRM dedupe.
44. **Cross-run dedupe** — don't re-surface leads from a prior run (optional master ledger).

## E. CLI & developer experience

45. `(v1.1)` **Config file** — `leadgen.toml` for markets, sources, verticals, weights.
46. **Run journaling / `--resume`** — continue an interrupted large run.
47. **Response cache (TTL)** — avoid re-fetching during development.
48. `(quick)` **`--count` / `--dry-run`** — estimate result size before a full run.
49. `(quick)` **`--format ndjson|json`** — machine-readable output beside CSV/XLSX.
50. **`--quiet` / `--verbose` / `--log-file`** — structured logging levels.
51. `(quick)` **`leadgen markets`** — list saved markets; `--add-market` helper.
52. **Scriptable summary** — exit codes + a JSON run summary to stdout.
53. **Library examples** — a documented notebook/script for the `run_pipeline` API.
54. **Tunable weights** — `--weight no_website=80` to override scoring per run.

## F. GUI & non-technical UX

55. `(v1.1)` **Server-side saved markets** — persist favorites (not just localStorage).
56. **Run queue** — line up several market/vertical combos to run in sequence.
57. **Progress ETA + per-source bars** — clearer "how long left".
58. **In-app map preview** — Leaflet + OSM tiles (no key) to see results geographically.
59. `(quick)` **Column chooser + sort** in the results table.
60. `(quick)` **Click-to-call / mailto + copy buttons** per lead.
61. **Mark contacted / not-interested** with local persistence.
62. `(quick)` **Export the filtered view** — download exactly what's on screen.
63. `(quick)` **Dark mode.**
64. **First-run guided tour.**
65. **Settings panel** — default sources, enrich cap, crawler UA contact string.
66. **Mid-run source-failure recovery** — clear message + "retry this source" button.

## G. Output & integrations

67. `(quick)` **Per-tier exports** — separate A/B/C files.
68. **CRM-ready headers** — column presets for HubSpot/Pipedrive/Mailchimp imports.
69. **Markdown/HTML run report** — summary + top leads, shareable.
70. `(quick)` **vCard export** for contacts.
71. **Editable opener templates** — per-vertical, with mail-merge tokens.
72. **Completion hook** — run a user script/command when a run finishes.
73. **Append to a master CSV** — dedup-aware growing list.
74. **Google-Sheets-friendly TSV** — paste-ready file (no API/account).

## H. Packaging & distribution

75. `(v1.1)` **Cut `v1.0.0`** — tag → cross-platform binaries on a Release (build workflow already exists).
76. **PyPI / pipx publish** — `pip install leadgen` for the lib + CLI.
77. **Auto-generated changelog** from commits at release time.
78. **winget / scoop / Homebrew manifests** for one-line installs.
79. **Docker image** for the GUI/server.
80. **Desktop auto-update check** — points at GitHub Releases; SmartScreen/Gatekeeper guidance doc.

## I. Performance & reliability

81. `(v1.1)` **Parallel multi-source collection** — run the chosen sources concurrently.
82. **Adaptive per-host rate limiting** for enrichment fetches.
83. **Overpass bbox tiling** — split large areas into tiles + merge to avoid timeouts.
84. **Unified retry/backoff** policy shared by all sources.
85. **Streaming for huge markets** — don't hold the whole result set in RAM.
86. **Optional SQLite run store** — browse history across restarts.
87. `(quick)` **Surface per-source counts** in the UI/summary ("Overture 412, OSM 88…").
88. **Perf benchmarks** + a regression guard.

## J. Project health (testing, CI, docs, community)

89. `(v1.1)` **CI on PRs** — run all test suites (pytest) on push/PR.
90. **Recorded-response source tests** — mock network for each provider.
91. `(quick)` **Lint/format** — ruff + black + a pre-commit hook.
92. **Coverage reporting.**
93. **Type hints throughout** + mypy in CI.
94. `(quick)` **`CONTRIBUTING.md`** + issue/PR templates.
95. `(quick)` **`SECURITY.md` + `CODE_OF_CONDUCT.md`.**
96. **`CHANGELOG.md`** (kept per release).
97. **Docs site** (mkdocs) generated from the markdown docs.
98. **Cookbook / recipe gallery** — one worked example per use case.
99. `(quick)` **README screenshots / GIF** of the GUI.
100. **Expanded legal & ethics doc** — per-source licenses + attribution + anti-spam (CAN-SPAM/CASL/GDPR) pointers.

---

## Proposed v1.1 milestone (a shippable next version)

A focused, coherent slice — reach, quality, and polish — rather than all 100 at once:

- **Ship it:** #75 cut v1.0.0 first (so there's a baseline release), then target v1.1.
- **Reach:** #11 `restaurants` vertical, #5 source registry, #23 email finder.
- **Quality:** #35 cross-source dedupe, #36 phone normalization, #39 closed-business filtering.
- **Speed:** #81 parallel source collection.
- **Dev UX:** #45 config file, #48 `--count`.
- **GUI:** #55 saved markets, #59 column chooser/sort, #62 export filtered view.
- **Health:** #89 CI on PRs, #91 lint/format, #94 CONTRIBUTING.

That bundle is large but cohesive, keeps every constraint, and gives a clear
"v1.1" story: *more sources made pluggable, cleaner deduped data, faster runs, and
a friendlier UI.* Everything else stays queued here for v1.2+.
