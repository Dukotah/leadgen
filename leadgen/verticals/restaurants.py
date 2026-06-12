"""
Vertical: restaurant / food-business web leads.

Same buyer logic as web_design (no site, social-only, or a weak/slow DIY site =
a good prospect for a web designer) but TARGETED to food businesses —
restaurants, cafes, bars, bakeries, delis. Food businesses live or die on
discovery (menus, hours, reservations, online ordering), so a missing or weak
site is an especially easy pitch.

Uses audit_enrich so the same offline/demo HTML path works as web_design.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url, DIY_BUILDERS
from ._common import audit_enrich

CONFIG = {"diy_builders": DIY_BUILDERS}


def _score(rec: dict) -> tuple[int, str, str]:
    score, reasons = 0, []
    site = rec.get("website") or ""
    weak, why = is_weak_url(site)
    audit = rec.get("audit") or {}
    if not site:
        score += 60; reasons.append("NO WEBSITE"); tier = "A"
    elif weak:
        score += 40; reasons.append(f"non-site link ({why})"); tier = "A"
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
                score += 10; reasons.append(f"slow ({audit['load_ms']}ms)"); tier = "B"
            if audit.get("builder") in CONFIG["diy_builders"]:
                score += 12; reasons.append(f"DIY ({audit['builder']})"); tier = "B"
            if not reasons:
                reasons.append("real site, no obvious issues")
    if rec.get("phone"):
        score += 4; reasons.append("phone listed")
    return score, tier, "; ".join(reasons)


def _opener(rec: dict) -> str:
    site = (rec.get("website") or "").lower()
    cat = rec.get("category") or "restaurant"
    city = rec.get("city") or ""
    if not site:
        return (f"No website — diners can't find the menu or hours. Pitch a "
                f"1-page site ranking for '{cat} {city}'.")
    if "facebook" in site or "instagram" in site:
        return "Menu/hours live only on social — pitch a real site they own that ranks on Google."
    if site.startswith("http://"):
        return "HTTP only — Chrome flags it 'Not secure'. Quick rebuild + SSL + online menu."
    return "Has a site — verify the menu/ordering experience before pitching."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="restaurants",
    label="Restaurants & food businesses that need a website",
    description=("Finds restaurants, cafes, bars, and bakeries with no website, "
                 "a social-only page, or a weak/slow site — web-design prospects."),
    overture_categories=["restaurant", "cafe", "food", "bar", "bakery", "coffee"],
    osm_tags=["amenity=restaurant", "amenity=cafe", "amenity=fast_food",
              "amenity=bar", "amenity=pub", "shop=bakery", "shop=deli"],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    config=CONFIG,
    columns=COLUMNS,
))
