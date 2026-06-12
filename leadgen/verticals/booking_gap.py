"""
Vertical: online-booking gap.

Target: service businesses (salons, spas, gyms, professional offices) that have a
real website but NO online scheduling — customers still have to call to book. A
direct pitch for someone selling Calendly/Acuity/Square-Appointments setups:
"let people book themselves 24/7 and stop playing phone tag." A business with no
site is a softer (web-design-first) lead; one that already books online is not a fit.

Reuses audit_enrich (offline-aware) then reads the audited HTML through
signals.has_booking.
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
        elif signals.has_booking(html):
            why.append("already books online"); tier = "C"
        else:
            score += 50; why.append("real site, no online scheduling"); tier = "A"
    if rec.get("phone"):
        score += 4; why.append("phone listed")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return "No real site yet — pitch a booking-ready site from scratch."
    audit = rec.get("audit") or {}
    if signals.has_booking(audit.get("html") or ""):
        return "Already takes online bookings — not a fit for a scheduling build."
    return ("Site but no online booking — pitch self-serve scheduling so they "
            "stop losing after-hours appointments to phone tag.")


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="booking_gap",
    label="Service businesses with a site but no online booking",
    description=("Finds service businesses (salons, spas, gyms, offices) with a "
                 "real site but no online scheduling — a sellable booking-setup gap."),
    overture_categories=[],
    osm_tags=[
        "shop=hairdresser", "shop=beauty", "shop=massage", "amenity=spa",
        "leisure=fitness_centre", "leisure=sports_centre", "amenity=clinic",
        "amenity=dentist", "amenity=doctors", "amenity=veterinary",
        "office=lawyer", "office=accountant", "office=estate_agent",
        "office=insurance", "office=financial",
    ],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
