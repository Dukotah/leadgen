"""
Vertical: web-design leads — the shipped worked example.

Target: local businesses with no website, a social-only presence, or a weak/slow
DIY site — i.e. good prospects for a web designer. This is the reference vertical:
read it alongside docs/ADD_A_VERTICAL.md to build your own.

It shows the full pattern: an enrich_fn that audits each site, a score_fn that
turns those signals into a tier, and an opener_fn that drafts a pitch angle. The
enrich_fn is written to also work offline (demo mode) by reading bundled HTML
from ctx, so `--demo` / the GUI "Try a demo" button need no network.
"""
from __future__ import annotations

from .. import register, Vertical
from ..audit import audit_website, audit_from_html, is_weak_url, DIY_BUILDERS

CONFIG = {"diy_builders": DIY_BUILDERS}


def _enrich(rec: dict, ctx: dict) -> dict:
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return rec  # no real site to audit — scoring handles the gap
    demo_html = (ctx or {}).get("demo_html")
    if demo_html is not None:
        # Offline: score the bundled fixture exactly as a live fetch would.
        html = demo_html(site)
        rec["audit"] = audit_from_html(html, site, reachable=bool(html))
    else:
        rec["audit"] = audit_website(site)
    return rec


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
    if not site:
        return f"No website — pitch a 1-page site ranking for '{rec.get('category','')} {rec.get('city','')}'."
    if "facebook" in site or "instagram" in site:
        return "Social-only — pitch a real site that ranks on Google."
    if site.startswith("http://"):
        return "HTTP only — Chrome flags it 'Not secure'. Quick rebuild + SSL."
    return "Has a site — verify quality before pitching."


COLUMNS = [
    ("Tier", "tier"), ("Score", "score"), ("Business", "name"),
    ("Category", "category"), ("City", "city"), ("Phone", "phone"),
    ("Website", "website"), ("Why a lead", "why"), ("Pitch", "opener"),
    ("Address", "address"), ("Source", "source"), ("Source URL", "source_url"),
]

register(Vertical(
    key="web_design",
    label="Local businesses that need a website",
    description=("Finds local businesses with no website, a social-only page, or "
                 "a weak/outdated site — good prospects for web-design work."),
    overture_categories=[],          # all categories; broad by design
    osm_tags=["craft=plumber", "craft=electrician", "shop=car_repair",
              "shop=hairdresser", "amenity=restaurant", "office=lawyer"],
    keep_chains=False,               # chains don't buy from local web designers
    score_fn=_score,
    enrich_fn=_enrich,
    opener_fn=_opener,
    config=CONFIG,
    columns=COLUMNS,
))
