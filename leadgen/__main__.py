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
    ap.add_argument("--sources", nargs="+", default=["overture"],
                    choices=["overture", "osm", "socrata", "npi", "foursquare", "arcgis"],
                    help="data sources: overture/osm (maps), socrata/arcgis (open-data "
                         "licenses), npi (healthcare), foursquare (deep/slow, no key)")
    ap.add_argument("--limit", type=int, help="cap businesses collected")
    ap.add_argument("--enrich-cap", type=int, default=150,
                    help="enrich only the top-N businesses (cost control)")
    ap.add_argument("--no-enrich", action="store_true", help="skip per-site enrichment")
    ap.add_argument("--out", help="output filename stem (writes <stem>_crm.csv + <stem>.xlsx)")
    args = ap.parse_args(argv)

    if args.list:
        for k, v in sorted(all_verticals().items()):
            print(f"  {k:14s} {v.label}")
        return 0

    if not args.vertical or not args.market:
        ap.error("--vertical and --market are required (or use --list)")

    try:
        vertical = get_vertical(args.vertical)
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2

    run_pipeline(
        vertical, args.market,
        sources=tuple(args.sources), limit=args.limit,
        enrich=not args.no_enrich, enrich_cap=args.enrich_cap,
        out_stem=args.out or f"{args.vertical}_{args.market}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
