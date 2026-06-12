"""
Vertical: SEO / performance leads.

A different buyer from web_design: these businesses ALREADY have a real website —
it's just slow, insecure (no HTTPS), not mobile-friendly, or stuck on a DIY
builder. Good prospects for someone selling SEO, performance, or site-modernization
work (not a from-scratch rebuild). A business with no site at all is NOT this
buyer's lead, so it scores low here.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import is_weak_url, DIY_BUILDERS
from ._common import audit_enrich, BROAD_OSM_TAGS


def _score(rec: dict) -> tuple[int, str, str]:
    site = rec.get("website") or ""
    weak, _ = is_weak_url(site)
    if not site or weak:
        return 0, "C", "no real site to optimize (a web-design lead, not SEO)"

    audit = rec.get("audit") or {}
    if not audit:
        return 5, "C", "site not audited yet"
    if not audit.get("reachable"):
        return 60, "A", "site down / unreachable — urgent fix"

    score, why = 0, []
    if not audit.get("https"):
        score += 20; why.append("no HTTPS")
    if not audit.get("mobile_viewport"):
        score += 18; why.append("not mobile-friendly")
    load = audit.get("load_ms") or 0
    if load > 4000:
        score += 16; why.append(f"very slow ({load}ms)")
    elif load > 2500:
        score += 8; why.append(f"slow ({load}ms)")
    if audit.get("builder") in DIY_BUILDERS:
        score += 8; why.append(f"DIY builder ({audit['builder']})")

    if score >= 30:
        tier = "A"
    elif score >= 12:
        tier = "B"
    else:
        tier = "C"
        if not why:
            why.append("fast, secure, mobile — little to improve")
    return score, tier, "; ".join(why)


def _opener(rec: dict) -> str:
    audit = rec.get("audit") or {}
    if not (rec.get("website")) or is_weak_url(rec.get("website") or "")[0]:
        return "No real site — this is a web-design pitch, not SEO."
    if not audit.get("reachable"):
        return "Their site is down — lead with 'your website isn't loading'."
    if not audit.get("https"):
        return "No HTTPS — Google ranks them down and Chrome flags 'Not secure'."
    if not audit.get("mobile_viewport"):
        return "Not mobile-friendly — most local searches are on phones."
    if (audit.get("load_ms") or 0) > 2500:
        return "Slow site — pitch a speed/Core-Web-Vitals tune-up."
    return "Solid site — limited SEO upside; deprioritize."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="seo_audit",
    label="Businesses with a weak/slow site (SEO & performance)",
    description=("Finds businesses that already have a site but it's slow, "
                 "insecure, not mobile-friendly, or on a DIY builder — SEO/perf work."),
    overture_categories=[],
    osm_tags=BROAD_OSM_TAGS,
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    columns=COLUMNS,
))
