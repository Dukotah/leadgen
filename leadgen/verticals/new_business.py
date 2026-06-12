"""
Vertical: newly-listed / newly-licensed businesses.

Target: businesses that just appeared in a public license/registration feed and
don't have a website yet — the freshest possible web-design / web-presence lead.
Records pulled from license/registry sources (Socrata open-data portals, the NPI
provider registry, ArcGIS permit/license layers) are the strongest signal: a
newly licensed business with no site is someone actively standing up and likely
shopping for one. A no-site record from any other source is still a good lead;
anything that already has a site is a weaker fit.

No website audit needed — the signal is the source + the missing URL — so no
enrich_fn. Targeting is broad, but it shines fed by the license sources.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import BROAD_OSM_TAGS

# Sources that mean "newly licensed / registered" rather than a scraped map POI.
LICENSE_SOURCES = ("socrata", "npi", "arcgis")


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    source = (rec.get("source") or "").lower()
    weak, _ = is_weak_url(site)
    no_site = (not site) or weak
    score, why = 0, []
    if no_site and source in LICENSE_SOURCES:
        score += 60; why.append(f"newly listed ({source}), no site"); tier = "A"
    elif no_site:
        score += 35; why.append("no website yet"); tier = "B"
    else:
        why.append("already has a site"); tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    source = (rec.get("source") or "").lower()
    no_site = (not site) or is_weak_url(site)[0]
    if no_site and source in LICENSE_SOURCES:
        return ("Just licensed/registered and no site yet — reach out first with a "
                "ready-to-launch one-page site for the new business.")
    if no_site:
        return "No website yet — pitch getting them online before a competitor does."
    return "Already has a site — not a fresh-launch lead."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="new_business",
    label="Newly licensed/registered businesses with no website",
    description=("Ranks newly listed businesses (license/registry feeds) that have "
                 "no website yet — the freshest possible web-presence leads."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    opener_fn=_opener,
    columns=COLUMNS,
))
