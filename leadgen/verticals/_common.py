"""
Shared hooks reused across verticals, so each vertical file stays about its
*scoring*, not its plumbing.
"""
from __future__ import annotations

from ..audit import audit_website, audit_from_html, is_weak_url

# Social platforms that count as "no real website of your own".
SOCIAL_HOSTS = ("facebook.com", "fb.com", "instagram.com", "linktr.ee",
                "linktree.com", "tiktok.com", "twitter.com", "x.com",
                "nextdoor.com", "youtube.com")

# Broad OSM coverage for "any local business" verticals. Key-only entries
# ("shop", "craft", "office") match ANY value of that key (every shop/trade/office
# with a name); the amenity/tourism/leisure entries add the business-y POIs that
# don't live under those keys. Far wider reach than a short hardcoded list.
BROAD_OSM_TAGS = [
    "shop", "craft", "office",
    "amenity=restaurant", "amenity=cafe", "amenity=bar", "amenity=pub",
    "amenity=fast_food", "amenity=fuel", "amenity=pharmacy", "amenity=clinic",
    "amenity=dentist", "amenity=doctors", "amenity=veterinary", "amenity=bank",
    "amenity=car_wash", "amenity=car_rental", "amenity=driving_school",
    "tourism=hotel", "tourism=guest_house", "tourism=motel",
    "leisure=fitness_centre",
]


def audit_enrich(rec: dict, ctx: dict) -> dict:
    """Audit a business's website (HTTPS / mobile / speed / DIY builder).

    Demo-aware: if ctx provides bundled HTML (offline demo / GUI "Try a sample"),
    score that instead of fetching, so the same hook works with no network.
    """
    site = rec.get("website") or ""
    if not site or is_weak_url(site)[0]:
        return rec  # nothing real to audit — the scorer handles the gap
    demo_html = (ctx or {}).get("demo_html")
    if demo_html is not None:
        html = demo_html(site)
        rec["audit"] = audit_from_html(html, site, reachable=bool(html))
    else:
        rec["audit"] = audit_website(site)
    return rec


def is_social(url: str) -> bool:
    """True if the URL is a social-media page rather than an owned website."""
    from ..audit import hostname
    host = hostname(url)
    return any(host == d or host.endswith("." + d) for d in SOCIAL_HOSTS)
