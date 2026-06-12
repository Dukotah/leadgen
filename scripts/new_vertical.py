"""
Scaffold a new leadgen vertical.

    python scripts/new_vertical.py <key>

Writes leadgen/verticals/<key>.py from a template — a "needs a website" style
scorer (no site => A, weak/social => A, real site => C, with a phone bonus), the
standard web_design-shaped COLUMNS, and a register(Vertical(...)) call. It will
NOT overwrite an existing file. After it runs, add the import to
leadgen/verticals/__init__.py so the engine registers the new vertical.
"""
from __future__ import annotations

import os
import re
import sys

VERTICALS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "leadgen", "verticals",
)

TEMPLATE = '''\
"""
Vertical: {key} web leads (scaffolded).

Same buyer logic as web_design (no site, social-only, or a weak/slow DIY site =
a good web-design prospect). Tune osm_tags / overture_categories and the opener
below for the {key} niche, then add the import to verticals/__init__.py.

Uses audit_enrich so the same offline/demo HTML path works as web_design.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url, DIY_BUILDERS
from ._common import audit_enrich

CONFIG = {{"diy_builders": DIY_BUILDERS}}


def _score(rec: dict) -> tuple[int, str, str]:
    score, reasons = 0, []
    site = rec.get("website") or ""
    weak, why = is_weak_url(site)
    audit = rec.get("audit") or {{}}
    if not site:
        score += 60; reasons.append("NO WEBSITE"); tier = "A"
    elif weak:
        score += 40; reasons.append(f"non-site link ({{why}})"); tier = "A"
    else:
        tier = "C"
        if not audit.get("reachable"):
            score += 50; reasons.append("site unreachable"); tier = "A"
        else:
            if not audit.get("https"):
                score += 18; reasons.append("no HTTPS"); tier = "B"
            if not audit.get("mobile_viewport"):
                score += 14; reasons.append("not mobile-friendly"); tier = "B"
            if (audit.get("load_ms") or 0) > 4000:
                score += 10; reasons.append(f"slow ({{audit['load_ms']}}ms)"); tier = "B"
            if audit.get("builder") in CONFIG["diy_builders"]:
                score += 12; reasons.append(f"DIY ({{audit['builder']}})"); tier = "B"
            if not reasons:
                reasons.append("real site, no obvious issues")
    if rec.get("phone"):
        score += 4; reasons.append("phone listed")
    return score, tier, "; ".join(reasons)


def _opener(rec: dict) -> str:
    site = (rec.get("website") or "").lower()
    cat = rec.get("category") or "business"
    city = rec.get("city") or ""
    if not site:
        return f"No website — pitch a 1-page site ranking for '{{cat}} {{city}}'."
    if "facebook" in site or "instagram" in site:
        return "Social-only — pitch a real site that ranks on Google."
    if site.startswith("http://"):
        return "HTTP only — Chrome flags it 'Not secure'. Quick rebuild + SSL."
    return "Has a site — verify quality before pitching."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="{key}",
    label="{label}",
    description="Scaffolded vertical for {key} — businesses with no/weak/slow site.",
    overture_categories=[],          # TODO: tune for the {key} niche
    osm_tags=["shop"],               # TODO: tune for the {key} niche
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    config=CONFIG,
    columns=COLUMNS,
))
'''

_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python scripts/new_vertical.py <key>", file=sys.stderr)
        return 2
    key = argv[0].strip()
    if not _KEY_RE.match(key):
        print(f"error: invalid key '{key}' — use lowercase letters, digits, "
              f"and underscores only (must start with a letter or underscore).",
              file=sys.stderr)
        return 2

    path = os.path.join(VERTICALS_DIR, f"{key}.py")
    if os.path.exists(path):
        print(f"error: {path} already exists — refusing to overwrite.",
              file=sys.stderr)
        return 1

    label = key.replace("_", " ").title() + " that need a website"
    with open(path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(key=key, label=label))

    print(f"Created {path}")
    print()
    print("Next: add the import to leadgen/verticals/__init__.py so it registers:")
    print(f"    from . import {key}  # noqa: F401  (registers \"{key}\")")
    print()
    print("Then tune osm_tags / overture_categories / opener for the niche.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
