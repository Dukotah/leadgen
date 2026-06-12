"""
Vertical: social-media-management prospects.

Same signal as social_only (the business's only presence is a Facebook/Instagram/
Linktree page) but framed for a different buyer: a social-media MANAGER selling
ongoing posting/engagement rather than a website. For that seller a business that
already lives on social is the BEST lead — they have an account to manage — a
business with no presence at all is a softer "start them on social" lead, and a
business with a real owned website is a weaker fit for pure SMM.

No website audit needed — the signal is the URL itself — so no enrich_fn.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import is_social, BROAD_OSM_TAGS


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    score, why = 0, []
    if is_social(site):
        score += 55; why.append("active on social only — ready-made SMM client"); tier = "A"
    elif not site:
        score += 35; why.append("no online presence — start them on social"); tier = "B"
    elif is_weak_url(site)[0]:
        score += 30; why.append("only a directory listing — social presence to build"); tier = "B"
    else:
        why.append("has a real website — weaker fit for pure social management"); tier = "C"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if is_social(site):
        return ("Already posting on social — pitch managing it: consistent posting, "
                "engagement, and growth so it actually drives customers.")
    if not site:
        return "No presence anywhere — pitch standing up and running their social channels."
    if is_weak_url(site)[0]:
        return "Only a directory listing — pitch building and managing real social profiles."
    return "Has a real website — pure social management is a softer fit here."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="social_media_mgmt",
    label="Businesses to sell social-media management to",
    description=("Finds businesses whose only presence is social (or none) — the "
                 "best prospects for someone selling ongoing social-media management."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    opener_fn=_opener,
    columns=COLUMNS,
))
