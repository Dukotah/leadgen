"""
Vertical: directory-only businesses.

Targets businesses whose ONLY web presence is a third-party directory listing —
a Yelp, YellowPages, MapQuest, or similar link — rather than an owned site.
They're paying (in attention, often money) to rent a page on someone else's
platform that competes with every other business on the same listing. Strong
pitch: "you own nothing; let's get you a real site that ranks on its own."

Social-only businesses (Facebook/Instagram/etc.) are routed to tier B with a
pointer to the social_only vertical, which is the better-fit list for them. No
enrich_fn — the signal is the URL itself, so this runs fast over large markets.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import is_social, BROAD_OSM_TAGS


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    score, why = 0, []
    if is_social(site):
        # A social page is "weak" too, but it's the social_only vertical's lead.
        score += 25; why.append("social only, see social_only vertical"); tier = "B"
    elif not site:
        score += 30; why.append("no web presence at all"); tier = "B"
    elif is_weak_url(site)[0]:
        score += 50; why.append(f"directory listing only ({is_weak_url(site)[1]})"); tier = "A"
    else:
        why.append("already has a real website"); tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if is_social(site):
        return "Social-only — better fit for the social_only list; pitch an owned site."
    if not site:
        return "No web presence at all — pitch a one-page site that ranks on Google."
    if is_weak_url(site)[0]:
        return ("Only a directory listing they don't own — pitch a real site that "
                "ranks on its own instead of renting a page on someone else's.")
    return "Already has a real site — not a fit for this list."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="directory_only",
    label="Businesses whose only presence is a directory listing",
    description=("Finds businesses whose only web link is a directory/listing "
                 "(Yelp/YellowPages/etc.) they don't own — pitch a real owned site."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    opener_fn=_opener,
    columns=COLUMNS,
))
