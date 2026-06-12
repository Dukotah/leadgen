"""
Vertical: e-commerce-ready retail.

Target: retail shops that already have a real website but NO online store — a
brochure site with no cart/checkout. A clean pitch for someone selling Shopify /
WooCommerce builds: "you've got the products and the traffic; let's let people
buy online." A shop with no site at all is a softer (web-design-first) lead, and
a shop that already sells online is not a fit.

Reuses audit_enrich so the same hook works offline (demo) and live, then reads
the audited HTML through signals.has_ecommerce.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url
from ._common import audit_enrich
from .. import signals


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
        elif signals.has_ecommerce(html):
            why.append("already sells online"); tier = "C"
        else:
            score += 50; why.append("real site, no online store"); tier = "A"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return "No real site yet — pitch a store-ready site from scratch."
    audit = rec.get("audit") or {}
    if signals.has_ecommerce(audit.get("html") or ""):
        return "Already sells online — not a fit for an e-commerce build."
    return ("Brochure site, no cart — pitch adding online ordering so customers "
            "can buy without calling.")


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="ecommerce_ready",
    label="Retail shops with a site but no online store",
    description=("Finds retail shops that have a real website but no cart/checkout "
                 "— good prospects for a Shopify/WooCommerce online-store build."),
    overture_categories=[],
    osm_tags=[
        "shop=clothes", "shop=gift", "shop=shoes", "shop=jewelry",
        "shop=furniture", "shop=books", "shop=boutique", "shop=art",
        "shop=florist", "shop=toys", "shop=bakery", "shop=cosmetics",
        "shop=sports", "shop=bicycle", "shop=music",
    ],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
