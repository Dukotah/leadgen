"""
Vertical: pet-services web leads.

Targets veterinarians, groomers, boarding/daycare, and pet shops. Same buyer
logic as web_design (no site, social-only, or a weak/slow DIY site = a good
web-design prospect), but the pitch is tuned to how pet owners choose: they
search '<service> near me' and want hours, services, and a way to book.

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
    svc = rec.get("category") or "pet service"
    city = rec.get("city") or ""
    if not site:
        return (f"No website — pet owners searching '{svc} {city}' can't find hours "
                f"or book. Pitch a simple site with services + appointment requests.")
    if "facebook" in site or "instagram" in site:
        return (f"Only on social — pitch an owned site that ranks for "
                f"'{svc} {city}' and takes appointment requests.")
    if site.startswith("http://"):
        return "HTTP only — Chrome flags it 'Not secure'. Quick rebuild + SSL."
    return f"Has a site — check for online booking/appointment requests before pitching."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="pet_services",
    label="Pet-service businesses that need a website",
    description=("Finds vets, groomers, boarding/daycare, and pet shops with "
                 "no/weak/slow site — web-design prospects that need to rank for "
                 "'<service> near me' and take bookings."),
    overture_categories=["veterinary", "pet_groomer", "pet_boarding",
                         "pet_store", "animal"],
    osm_tags=["amenity=veterinary", "shop=pet", "shop=pet_grooming"],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    config=CONFIG,
    columns=COLUMNS,
))
