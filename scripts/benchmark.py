"""
Tiny offline benchmark — times a demo pipeline run end to end (no network).

  python scripts/benchmark.py            # default vertical web_design
  python scripts/benchmark.py seo_audit  # pick a vertical

demo=True uses bundled sample businesses + fixture HTML, so this is fully
offline and dependency-light: it just measures the engine's CPU path.
"""
import os
import sys
import time

# Make the repo root importable whether run from root or scripts/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leadgen import run_pipeline, get_vertical


def main(argv):
    name = argv[1] if len(argv) > 1 else "web_design"
    vertical = get_vertical(name)

    start = time.perf_counter()
    leads = run_pipeline(vertical, market="austin_tx", demo=True,
                         log=lambda *a, **k: None)  # silence pipeline chatter
    elapsed = time.perf_counter() - start

    print(f"vertical={name}  leads={len(leads)}  elapsed={elapsed:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
