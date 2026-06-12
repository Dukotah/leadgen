"""
Vertical: no-HTTPS / SSL leads.

A focused security pitch: target businesses that DO have a real, reachable
website but serve it over plain http:// only. Chrome and Safari now mark these
"Not secure", which spooks customers and hurts ranking — an easy, concrete,
one-line sale ("add SSL so browsers stop flagging your site").

Businesses with no site, a social-only page, or a weak/directory link are NOT
this buyer (there's no real site to secure) and score low. An already-https site
is already fixed, so it scores low too. Uses audit_enrich for the reachable/https
signals (demo-aware, same as web_design).
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import audit_enrich, BROAD_OSM_TAGS


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    weak, _ = is_weak_url(site)
    if not site or weak:
        return 0, "C", "no real site to secure (not an SSL lead)"

    audit = rec.get("audit") or {}
    if not audit:
        return 5, "C", "site not audited yet"
    if not audit.get("reachable"):
        return 5, "C", "site unreachable — verify before pitching SSL"
    if not audit.get("https"):
        score = 45
        if rec.get("phone"):
            score += 4
        return score, "A", "no HTTPS — Chrome flags 'Not secure'"
    return 0, "C", "already on HTTPS — already secure"


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return "No real site to secure — not an SSL pitch."
    audit = rec.get("audit") or {}
    if not audit.get("https"):
        return ("Their site is http:// only — Chrome shows visitors 'Not secure'. "
                "Pitch a quick SSL install.")
    return "Already on HTTPS — nothing to sell here."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="no_ssl",
    label="Businesses on http:// only (need SSL)",
    description=("Finds businesses whose real site is served over plain http:// "
                 "with no HTTPS — flagged 'Not secure' by Chrome. Easy SSL pitch."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
