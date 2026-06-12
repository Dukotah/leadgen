"""
Vertical: social-only businesses.

Target: local businesses whose entire web presence is a Facebook / Instagram /
Linktree page (or nothing at all) — i.e. they don't own a real website. A strong,
easy-to-explain pitch for web designers and social-media managers: "you're renting
your presence on someone else's platform; let's get you a site you own that ranks
on Google."

No website audit needed — the signal is the URL itself — so this vertical has no
enrich_fn and runs fast over large markets.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import is_social, BROAD_OSM_TAGS


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    score, why = 0, []
    if is_social(site):
        score += 55; why.append("social-only presence (no owned site)"); tier = "A"
    elif not site:
        score += 35; why.append("no web presence at all"); tier = "B"
    elif is_weak_url(site)[0]:
        score += 30; why.append("listing/directory link only"); tier = "B"
    else:
        why.append("already has a real website"); tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if is_social(site):
        return ("Running everything off social — pitch a site they own that ranks "
                "on Google and survives an algorithm change.")
    if not site:
        return "No web presence at all — the easiest possible win to pitch."
    if is_weak_url(site)[0]:
        return "Only a directory listing — pitch a real owned website."
    return "Already has a real site — not a fit for this list."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="social_only",
    label="Businesses with only a social page (no real website)",
    description=("Finds local businesses whose only web presence is Facebook/"
                 "Instagram/Linktree — or nothing — so they need a site they own."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    opener_fn=_opener,
    columns=COLUMNS,
))
