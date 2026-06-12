"""
Vertical: healthcare providers that need a website.

Targets healthcare providers — dentists, doctors, clinics, pharmacies,
physiotherapists, chiropractors — who have no real website. Pairs with the NPI
data source, where most records carry a provider name and specialty but no site
at all, so the strongest signal is simply "no owned web presence".

No enrich_fn: NPI records rarely include a site, and the scoring only needs the
URL itself, so this runs fast over large provider lists. A provider with a real
site is already covered and scores low.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import is_social


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    score, why = 0, []
    if not site:
        score += 60; why.append("NO WEBSITE"); tier = "A"
    elif is_social(site):
        score += 45; why.append("social-only presence (no owned site)"); tier = "A"
    elif is_weak_url(site)[0]:
        score += 40; why.append("listing/directory link only"); tier = "A"
    else:
        why.append("already has a real website"); tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    specialty = rec.get("category") or "practice"
    city = rec.get("city") or ""
    if not site:
        return (f"No website — patients search by specialty. Pitch a site that "
                f"ranks for '{specialty} {city}'.")
    if is_social(site):
        return (f"Only on social — pitch an owned site that ranks for "
                f"'{specialty} {city}' and books patients.")
    if is_weak_url(site)[0]:
        return f"Only a directory listing — pitch a real site for '{specialty} {city}'."
    return "Already has a real site — not a fit for this list."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="healthcare_web",
    label="Healthcare providers that need a website",
    description=("Finds dentists, doctors, clinics, and pharmacies with no real "
                 "website — pairs with the NPI source where most have no site."),
    overture_categories=["dentist", "doctor", "clinic", "pharmacy",
                         "physician", "chiropract", "physiotherap", "health"],
    osm_tags=["amenity=dentist", "amenity=doctors", "amenity=clinic",
              "amenity=pharmacy", "healthcare=physiotherapist",
              "healthcare=chiropractor"],
    keep_chains=False,
    score_fn=_score,
    opener_fn=_opener,
    columns=COLUMNS,
))
