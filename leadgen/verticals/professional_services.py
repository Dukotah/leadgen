"""
Vertical: professional-services web leads.

Targets lawyers, accountants, insurance agencies, real-estate offices, and
financial advisors. Same buyer logic as web_design (no site, social-only, or a
weak/slow DIY site = a good web-design prospect), but the pitch is tuned to how
these firms win clients: a credible, trustworthy site is table stakes for a
high-value service people research before they call.

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
    firm = rec.get("category") or "firm"
    city = rec.get("city") or ""
    if not site:
        return (f"No website — for a high-trust service that's a red flag to "
                f"prospects. Pitch a credible site for '{firm} {city}' with bio, "
                f"services, and a contact form.")
    if "facebook" in site or "instagram" in site:
        return (f"Only on social — looks unprofessional for a {firm}. Pitch an owned, "
                f"credible site that ranks for '{firm} {city}'.")
    if site.startswith("http://"):
        return "HTTP only — Chrome flags it 'Not secure'. For a trust business that's a deal-breaker; rebuild + SSL."
    return f"Has a site — check it looks credible and current before pitching."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="professional_services",
    label="Professional-service firms that need a website",
    description=("Finds lawyers, accountants, insurance agents, real-estate "
                 "offices, and financial advisors with no/weak/slow site — "
                 "web-design prospects where a credible site is table stakes."),
    overture_categories=["lawyer", "attorney", "accountant", "insurance",
                         "real_estate", "financial"],
    osm_tags=["office=lawyer", "office=accountant", "office=insurance",
              "office=estate_agent", "office=financial"],
    keep_chains=False,
    score_fn=_score,
    enrich_fn=audit_enrich,
    opener_fn=_opener,
    config=CONFIG,
    columns=COLUMNS,
))
