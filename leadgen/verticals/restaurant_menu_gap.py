"""
Vertical: restaurants with no online menu / ordering.

Target: restaurants and cafes whose site shows no menu and no online-ordering
link (no DoorDash / Uber Eats / Grubhub / Toast). A clear pitch for someone
selling menu pages and online-ordering integrations: "people can't see your menu
or order online — that's lost revenue every night." A restaurant that already
links a menu/ordering is not a fit; one with no site is a softer web-design lead.

Reuses audit_enrich (offline-aware) then scans the audited HTML for menu/ordering
markers.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import audit_enrich

# Markers that mean "menu or online ordering is present" on the page.
MENU_MARKERS = (
    "menu", "order online", "doordash", "ubereats", "uber eats",
    "toast", "grubhub",
)


def _has_menu(html: str) -> bool:
    if not html:
        return False
    low = html.lower()
    return any(m in low for m in MENU_MARKERS)


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    weak, _ = is_weak_url(site)
    score, why = 0, []
    if not site or weak:
        score += 30; why.append("no real site yet (web-design first)"); tier = "B"
    else:
        audit = rec.get("audit") or {}
        html = audit.get("html") or ""
        if not audit.get("reachable", True):
            score += 30; why.append("site unreachable"); tier = "B"
        elif _has_menu(html):
            why.append("menu/online ordering present"); tier = "C"
        else:
            score += 50; why.append("no online menu/ordering"); tier = "A"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return "No real site yet — pitch a menu-and-ordering site from scratch."
    audit = rec.get("audit") or {}
    if _has_menu(audit.get("html") or ""):
        return "Menu/ordering already online — not a fit for this list."
    return ("Site but no menu or online ordering — pitch adding both so diners can "
            "see the menu and order without calling.")


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="restaurant_menu_gap",
    label="Restaurants with no online menu or ordering",
    description=("Finds restaurants whose site shows no menu and no online-ordering "
                 "link — prospects for menu pages and ordering integrations."),
    overture_categories=[],
    osm_tags=["amenity=restaurant", "amenity=cafe", "amenity=fast_food"],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
