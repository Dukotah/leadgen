"""
Vertical: outdated / stale website.

Target: businesses whose site carries an old footer copyright year (e.g. "© 2019")
— a strong proxy for a site nobody has touched in years. A clean modernization /
redesign pitch: "your site still says 2019; let's refresh it." A site with a
recent year is low priority; a business with no site is a softer web-design lead.

Reuses audit_enrich (offline-aware) then reads the audited HTML through
signals.copyright_year. CURRENT_YEAR is fixed so scoring is deterministic in tests.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import audit_enrich, BROAD_OSM_TAGS
from .. import signals

CURRENT_YEAR = 2026
STALE_BEFORE = CURRENT_YEAR - 3   # year <= this counts as stale


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    weak, _ = is_weak_url(site)
    score, why = 0, []
    if not site or weak:
        score += 30; why.append("no real site yet (web-design first)"); tier = "B"
    else:
        audit = rec.get("audit") or {}
        if not audit.get("reachable", True):
            score += 30; why.append("site unreachable"); tier = "B"
        else:
            year = signals.copyright_year(audit.get("html") or "")
            if year is not None and year <= STALE_BEFORE:
                score += 50; why.append(f"stale since {year}"); tier = "A"
            else:
                if year is not None:
                    why.append(f"recent copyright ({year})")
                else:
                    why.append("no stale copyright found")
                tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return "No real site yet — pitch a modern site from scratch."
    audit = rec.get("audit") or {}
    year = signals.copyright_year(audit.get("html") or "")
    if year is not None and year <= STALE_BEFORE:
        return (f"Footer still says {year} — pitch a refresh; an outdated-looking "
                "site costs them trust and search ranking.")
    return "Site looks current — limited modernization upside; deprioritize."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="outdated_site",
    label="Businesses with a stale, outdated website",
    description=("Finds businesses whose site shows an old copyright year — a "
                 "proxy for a neglected site that's ripe for a redesign/refresh."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
