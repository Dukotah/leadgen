"""
The pipeline: collect → dedupe → enrich → suppress → score → export.
Vertical-agnostic; all use-case specifics come from the Vertical object.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .geo import resolve_market
from .sources import (overture_collect, osm_collect, socrata_collect,
                      npi_collect, foursquare_collect, arcgis_collect)
from .suppression import norm, build_suppression_set
from .export import write_outputs
from .vertical import Vertical


def load_crm_names(path_or_text: str, *, is_text: bool = False) -> set[str]:
    """Normalized company names from an existing CRM export (CSV) so the pipeline
    never hands back a business the user already has.

    Reads the first column that looks like a company/business/name field; falls
    back to the first column. Accepts a file path or raw CSV text (is_text=True).
    """
    import csv
    import io
    if not path_or_text:
        return set()
    if is_text:
        f = io.StringIO(path_or_text)
    else:
        f = open(path_or_text, newline="", encoding="utf-8-sig", errors="replace")
    try:
        reader = csv.reader(f)
        rows = list(reader)
    finally:
        if not is_text:
            f.close()
    if not rows:
        return set()
    header = [h.strip().lower() for h in rows[0]]
    name_keys = ("company name", "company", "business", "business name", "brokerage",
                 "name", "account name", "organization")
    col = next((i for i, h in enumerate(header) if h in name_keys), 0)
    out: set[str] = set()
    for row in rows[1:]:
        if col < len(row):
            k = norm(row[col])
            if k:
                out.add(k)
    return out


def _dedupe(leads: list[dict]) -> list[dict]:
    """Collapse same-name duplicates (across sources) within one market."""
    seen: dict[str, dict] = {}
    for r in leads:
        key = norm(r.get("name", ""))
        if not key:
            continue
        if key in seen:
            # prefer the record that already has a website / more fields
            cur = seen[key]
            if not cur.get("website") and r.get("website"):
                cur["website"] = r["website"]
            if not cur.get("phone") and r.get("phone"):
                cur["phone"] = r["phone"]
        else:
            seen[key] = r
    return list(seen.values())


def run_pipeline(vertical: Vertical, market: str, *,
                 sources=("overture",), limit: int | None = None,
                 enrich: bool = True, enrich_cap: int | None = 150,
                 out_stem: str | None = None, config_override: dict | None = None,
                 exclude_names: set | None = None, demo: bool = False,
                 log=print) -> list[dict]:
    """Run the full pipeline for one vertical in one market.

    sources: any of ("overture", "osm").
    enrich:  run the vertical's enrich_fn (fetches each business's site).
    enrich_cap: only enrich the top-N by collection order (cost control); None = all.
    out_stem: if set, also writes <stem>_crm.csv and <stem>.xlsx.
    config_override: shallow-merged over the vertical's config for THIS run only
                     (e.g. competitor seed URLs typed into the GUI). The shared
                     vertical object is never mutated.
    exclude_names: normalized company names to drop (e.g. the user's existing CRM)
                   — see load_crm_names(). Matches are removed, not just flagged.
    demo: if True, use bundled offline sample data + fixture enrichment (no network).
    Returns the scored, sorted list of lead dicts. Output file paths, when written,
    are attached as run_pipeline.last_outputs = (csv_path, xlsx_path).
    """
    run_pipeline.last_outputs = None
    # Per-run config: copy so concurrent runs / the registry stay clean.
    cfg = dict(vertical.config)
    if config_override:
        cfg.update(config_override)

    # 1. COLLECT
    leads: list[dict] = []
    if demo:
        from .demo import demo_records
        leads = demo_records()
        log(f"DEMO MODE — using {len(leads)} bundled sample businesses (no network).")
    else:
        bbox, label = resolve_market(market)
        log(f"Market: {label}  bbox={tuple(round(x,3) for x in bbox)}")
        if "overture" in sources:
            try:
                leads += overture_collect(bbox, vertical.overture_categories, limit, log)
            except Exception as e:
                log(f"  Overture failed: {e}")
        if "osm" in sources and vertical.osm_tags:
            try:
                leads += osm_collect(bbox, vertical.osm_tags, log)
            except Exception as e:
                log(f"  OSM failed: {e}")
        if "socrata" in sources:
            try:
                leads += socrata_collect(label, limit=limit, log=log,
                                         datasets=cfg.get("socrata_datasets"))
            except Exception as e:
                log(f"  Socrata failed: {e}")
        if "npi" in sources:
            try:
                leads += npi_collect(label, limit=limit, log=log,
                                     taxonomies=cfg.get("npi_taxonomies"))
            except Exception as e:
                log(f"  NPI failed: {e}")
        if "foursquare" in sources:
            try:
                leads += foursquare_collect(bbox, vertical.overture_categories,
                                            limit, log)
            except Exception as e:
                log(f"  Foursquare failed: {e}")
        if "arcgis" in sources:
            try:
                leads += arcgis_collect(label, limit=limit, log=log,
                                        layers=cfg.get("arcgis_layers"))
            except Exception as e:
                log(f"  ArcGIS failed: {e}")
        # Extra no-key sources (lazy import so they're fully optional).
        if {"wikidata", "ckan", "localfile", "url_csv"} & set(sources):
            from .extra_sources import (wikidata_collect, ckan_collect,
                                        localfile_collect, url_csv_collect)
            if "wikidata" in sources:
                try:
                    leads += wikidata_collect(bbox, limit=limit, log=log)
                except Exception as e:
                    log(f"  Wikidata failed: {e}")
            if "ckan" in sources:
                try:
                    leads += ckan_collect(label, limit=limit, log=log)
                except Exception as e:
                    log(f"  CKAN failed: {e}")
            if "localfile" in sources and cfg.get("localfile_path"):
                try:
                    leads += localfile_collect(cfg["localfile_path"], limit=limit, log=log)
                except Exception as e:
                    log(f"  Local file failed: {e}")
            if "url_csv" in sources and cfg.get("url_csv"):
                try:
                    leads += url_csv_collect(cfg["url_csv"], limit=limit, log=log)
                except Exception as e:
                    log(f"  URL CSV failed: {e}")
    # Drop permanently-closed businesses, then normalize phones (helps dialing +
    # cross-source dedupe identity).
    from .quality import cross_source_dedupe, normalize_phone, is_closed
    before = len(leads)
    leads = [r for r in leads if not is_closed(r)]
    if before - len(leads):
        log(f"  dropped {before - len(leads)} closed businesses")
    for r in leads:
        if r.get("phone"):
            r["phone"] = normalize_phone(r["phone"]) or r["phone"]
    log(f"Collected {len(leads)} raw; deduping across sources…")
    leads = cross_source_dedupe(leads)
    log(f"  {len(leads)} after dedupe")

    # 1a. drop businesses already in the user's CRM (never hand back a dupe)
    if exclude_names:
        before = len(leads)
        leads = [r for r in leads if norm(r.get("name", "")) not in exclude_names]
        log(f"  removed {before - len(leads)} already in your CRM ({len(exclude_names)} names)")

    # 1b. chain handling — verticals that don't keep chains drop branded records
    if not vertical.keep_chains:
        before = len(leads)
        leads = [r for r in leads if not (r.get("brand"))]
        log(f"  dropped {before - len(leads)} chain/branded records")

    # 2. SUPPRESSION (competitor clients) — build once, applied during scoring.
    # Skipped in demo mode: it fetches competitor sites, and demo must stay offline.
    suppressed: dict[str, str] = {}
    if vertical.suppression_fn and not demo:
        log("Building competitor-suppression set…")
        suppressed = vertical.suppression_fn(cfg) or {}

    # 3. ENRICH (per-business website visit) — parallel, capped
    if enrich and vertical.enrich_fn and demo:
        # Offline enrichment: feed bundled fixture HTML through the same hooks.
        from .demo import demo_html_for
        ctx = {"config": cfg, "demo_html": demo_html_for}
        log(f"Enriching {len(leads)} sample businesses from bundled pages…")
        for r in leads:
            try:
                vertical.enrich_fn(r, ctx)
            except Exception as e:
                r["enrich_error"] = str(e)
    elif enrich and vertical.enrich_fn:
        targets = leads if enrich_cap is None else leads[:enrich_cap]
        log(f"Enriching {len(targets)} businesses (parallel)…")
        ctx = {"config": cfg}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(vertical.enrich_fn, r, ctx): r for r in targets}
            done = 0
            for f in as_completed(futs):
                try:
                    f.result()
                except Exception as e:
                    futs[f]["enrich_error"] = str(e)
                done += 1
                if done % 25 == 0:
                    log(f"  enriched {done}/{len(targets)}")

    # 4. SCORE (+ apply suppression flag) + opener
    for r in leads:
        key = norm(r.get("name", ""))
        if key in suppressed:
            r["suppressed"] = True
            r["suppressed_by"] = suppressed[key]
        s, tier, reasons = vertical.score(r)
        r["score"], r["tier"], r["why"] = s, tier, reasons
        if vertical.opener_fn:
            r["opener"] = vertical.opener_fn(r)
    leads.sort(key=lambda x: -x.get("score", 0))

    n = {"A": 0, "B": 0, "C": 0}
    for r in leads:
        n[r.get("tier", "C")] = n.get(r.get("tier", "C"), 0) + 1
    log(f"Scored {len(leads)} — A={n['A']} B={n['B']} C={n['C']}")

    # 5. EXPORT
    if out_stem:
        # Slugify only the filename; keep any directory the caller supplied intact.
        import os
        d, base = os.path.split(out_stem)
        stem = os.path.join(d, re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_"))
        run_pipeline.last_outputs = write_outputs(leads, vertical.columns, stem, log)

    return leads
