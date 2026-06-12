"""
CLI for the universal lead engine.

    python -m leadgen --list
    python -m leadgen --vertical web_design --market austin_tx --out austin_web
    python -m leadgen --vertical web_design --market "Boulder, Colorado" --sources overture osm
    python -m leadgen --vertical web_design --market phoenix_az --no-enrich --limit 200
"""
from __future__ import annotations

import argparse
import sys

from . import get_vertical, all_verticals, run_pipeline


def main(argv=None) -> int:
    # Make logging robust on Windows consoles / redirected output, where the
    # default code page (cp1252) can't encode the glyphs in our progress lines.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(prog="leadgen", description="Universal lead-gen engine")
    ap.add_argument("--list", action="store_true", help="list available verticals and exit")
    ap.add_argument("--vertical", help="vertical key (see --list)")
    ap.add_argument("--market", help="named market key or a geocodable place name")
    ap.add_argument("--sources", nargs="+", default=None,
                    choices=["overture", "osm", "socrata", "npi", "foursquare",
                             "arcgis", "wikidata", "ckan", "localfile", "url_csv"],
                    help="data sources: overture/osm (maps), socrata/arcgis/ckan "
                         "(open-data), npi (healthcare), wikidata, foursquare "
                         "(deep/slow), localfile/url_csv (your own CSV/XLSX)")
    ap.add_argument("--limit", type=int, help="cap businesses collected")
    ap.add_argument("--enrich-cap", type=int, default=150,
                    help="enrich only the top-N businesses (cost control)")
    ap.add_argument("--no-enrich", action="store_true", help="skip per-site enrichment")
    ap.add_argument("--out", help="output filename stem (writes <stem>_crm.csv + <stem>.xlsx)")
    ap.add_argument("--config", help="path to a leadgen.toml (default: auto-find in cwd)")
    ap.add_argument("--format", nargs="+", default=None,
                    choices=["jsonl", "json", "vcard", "per-tier", "report"],
                    help="extra output formats to write alongside the CSV/XLSX")
    ap.add_argument("--localfile", help="path to your own CSV/XLSX (with --sources localfile)")
    ap.add_argument("--url-csv", help="URL of a public CSV (with --sources url_csv)")
    args = ap.parse_args(argv)

    if args.list:
        for k, v in sorted(all_verticals().items()):
            print(f"  {k:18s} {v.label}")
        return 0

    # Config file: CLI flags win; the file fills the gaps.
    from .config import load_config, find_config
    cfg_path = args.config or find_config()
    file_cfg = load_config(cfg_path) if cfg_path else {}

    vertical_key = args.vertical or file_cfg.get("default_vertical")
    market = args.market or file_cfg.get("default_market")
    if not vertical_key or not market:
        ap.error("--vertical and --market are required (via flags, a leadgen.toml, or --list)")

    sources = tuple(args.sources or file_cfg.get("sources") or ["overture"])
    limit = args.limit if args.limit is not None else file_cfg.get("limit")
    enrich = (not args.no_enrich) if args.no_enrich else file_cfg.get("enrich", True)
    enrich_cap = args.enrich_cap if args.enrich_cap != 150 else file_cfg.get("enrich_cap", 150)

    # Per-vertical config (socrata_datasets / arcgis_layers / npi_taxonomies / ...).
    override = dict(file_cfg.get("config") or {})
    if args.localfile:
        override["localfile_path"] = args.localfile
    if args.url_csv:
        override["url_csv"] = args.url_csv

    try:
        vertical = get_vertical(vertical_key)
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    leads = run_pipeline(
        vertical, market,
        sources=sources, limit=limit,
        enrich=enrich, enrich_cap=enrich_cap,
        out_stem=args.out or f"{vertical_key}_{market}",
        config_override=override or None,
    )

    # Extra output formats, written next to the CSV/XLSX stem.
    if args.format and run_pipeline.last_outputs:
        from . import exporters
        import os
        stem = os.path.splitext(run_pipeline.last_outputs[0])[0]
        if stem.endswith("_crm"):
            stem = stem[:-4]
        cols = vertical.columns
        if "jsonl" in args.format:
            print("  ->", exporters.write_jsonl(leads, cols, stem + ".jsonl"))
        if "json" in args.format:
            print("  ->", exporters.write_json(leads, cols, stem + ".json"))
        if "vcard" in args.format:
            print("  ->", exporters.write_vcard(leads, stem + ".vcf"))
        if "report" in args.format:
            print("  ->", exporters.write_markdown_report(leads, stem))
        if "per-tier" in args.format:
            for t, p in exporters.write_per_tier(leads, cols, stem).items():
                print(f"  -> tier {t}: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
