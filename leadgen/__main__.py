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
    ap.add_argument("--list-markets", action="store_true",
                    help="list the saved named markets and exit")
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
    ap.add_argument("--count", "--dry-run", dest="count", action="store_true",
                    help="collect + dedupe only; print per-source counts and total, "
                         "then exit without enriching/scoring/exporting")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the per-step progress log")
    ap.add_argument("--verbose", action="store_true",
                    help="print all progress detail (default is already verbose)")
    ap.add_argument("--log-file", help="also tee progress lines to this file")
    ap.add_argument("--weight", action="append", default=None, metavar="KEY=VALUE",
                    help="set a tunable weight (repeatable), passed to the vertical "
                         "via config_override['weights']")
    ap.add_argument("--json-summary", action="store_true",
                    help="after the run, print a one-line JSON summary to stdout")
    args = ap.parse_args(argv)

    if args.list:
        for k, v in sorted(all_verticals().items()):
            print(f"  {k:18s} {v.label}")
        return 0

    if args.list_markets:
        from .geo import MARKETS
        for k in sorted(MARKETS):
            s, w, n, e = MARKETS[k]
            print(f"  {k:22s} bbox=({s}, {w}, {n}, {e})")
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

    # --weight KEY=VALUE (repeatable) -> config_override["weights"].
    # Values are coerced to int/float when they look numeric, else kept as str.
    if args.weight:
        weights = dict(override.get("weights") or {})
        for item in args.weight:
            if "=" not in item:
                ap.error(f"--weight expects KEY=VALUE, got {item!r}")
            k, _, v = item.partition("=")
            k = k.strip()
            v = v.strip()
            try:
                weights[k] = int(v)
            except ValueError:
                try:
                    weights[k] = float(v)
                except ValueError:
                    weights[k] = v
        override["weights"] = weights

    try:
        vertical = get_vertical(vertical_key)
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    from .logsetup import make_logger
    log = make_logger(quiet=args.quiet, verbose=args.verbose, log_file=args.log_file)

    # --count / --dry-run: collect + dedupe only. We disable enrichment and pass
    # no out_stem so nothing is written; run_pipeline still scores, but the cost
    # we care about (per-site enrichment + export) is skipped. We then report a
    # per-source breakdown computed from the returned leads' 'source' field.
    if args.count:
        leads = run_pipeline(
            vertical, market,
            sources=sources, limit=limit,
            enrich=False, enrich_cap=enrich_cap,
            out_stem=None,
            config_override=override or None,
            log=log,
        )
        by_source: dict[str, int] = {}
        for r in leads:
            src = r.get("source") or "unknown"
            by_source[src] = by_source.get(src, 0) + 1
        print("Per-source counts:")
        for src in sorted(by_source):
            print(f"  {src:12s} {by_source[src]}")
        print(f"  {'TOTAL':12s} {len(leads)}")
        if args.json_summary:
            import json
            print(json.dumps({
                "vertical": vertical_key, "market": market,
                "sources": list(sources), "total": len(leads),
                "by_source": by_source,
            }, separators=(",", ":")))
        return 0

    leads = run_pipeline(
        vertical, market,
        sources=sources, limit=limit,
        enrich=enrich, enrich_cap=enrich_cap,
        out_stem=args.out or f"{vertical_key}_{market}",
        config_override=override or None,
        log=log,
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

    if args.json_summary:
        import json
        tiers = {"A": 0, "B": 0, "C": 0}
        for r in leads:
            t = r.get("tier", "C")
            tiers[t] = tiers.get(t, 0) + 1
        outs = run_pipeline.last_outputs or ()
        files = {
            "csv": outs[0] if len(outs) > 0 else None,
            "xlsx": outs[1] if len(outs) > 1 else None,
        }
        print(json.dumps({
            "vertical": vertical_key, "market": market,
            "sources": list(sources), "total": len(leads),
            "tiers": {"A": tiers.get("A", 0), "B": tiers.get("B", 0),
                      "C": tiers.get("C", 0)},
            "files": files,
        }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
