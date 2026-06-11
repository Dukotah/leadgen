"""
Demo mode — a fully offline sample run so a new user sees exactly what the tool
produces before their first real scrape. No network required.

demo_records() returns realistic raw business records (the same shape collectors
produce). The pipeline's demo path enriches them from the bundled HTML below
instead of fetching live sites, so scoring / tiering / openers all populate and
every tier (A/B/C) shows up in the output.
"""
from __future__ import annotations

# Bundled "website" HTML, keyed by the demo record's website URL. A record whose
# URL maps to "" (or isn't here) is treated as unreachable by the audit.
_WIX_CAFE = """
<html><head><title>Sunrise Cafe</title></head>
<body><h1>Sunrise Cafe</h1>
<p>Fresh coffee &amp; pastries in Tampa.</p>
<!-- built on wix.com --><script src="https://static.wix.com/app.js"></script>
</body></html>
"""

_CLEAN_DENTAL = """
<html><head><title>Evergreen Dental</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><h1>Evergreen Dental</h1>
<p>Modern family dentistry in Boulder. Book online.</p></body></html>
"""

# (raw record, bundled HTML). Mix of gaps so the output shows every tier.
_DEMO = [
    (dict(name="Summit Plumbing Co", category="plumber", website="",
          phone="303-555-0144", email="", address="14 Pearl St",
          city="Boulder", state="CO", zip="80302", brand="",
          lat=40.02, lon=-105.27, source="demo", source_url=""), ""),
    (dict(name="Bella Hair Studio", category="hairdresser",
          website="https://facebook.com/bellahairatx", phone="512-555-0102",
          email="", address="2200 Guadalupe St", city="Austin", state="TX",
          zip="78705", brand="", lat=30.29, lon=-97.74, source="demo",
          source_url=""), ""),
    (dict(name="Old Town Auto Repair", category="car_repair",
          website="http://oldtownauto.example", phone="602-555-0101", email="",
          address="9 Roosevelt St", city="Phoenix", state="AZ", zip="85003",
          brand="", lat=33.46, lon=-112.07, source="demo", source_url=""), ""),
    (dict(name="Sunrise Cafe", category="restaurant",
          website="http://sunrisecafe.example", phone="813-555-0103", email="",
          address="700 Channelside Dr", city="Tampa", state="FL", zip="33602",
          brand="", lat=27.94, lon=-82.45, source="demo", source_url=""), _WIX_CAFE),
    (dict(name="Evergreen Dental", category="dentist",
          website="https://evergreendental.example", phone="303-555-0104",
          email="hello@evergreendental.example", address="55 Walnut St",
          city="Boulder", state="CO", zip="80302", brand="", lat=40.01,
          lon=-105.28, source="demo", source_url=""), _CLEAN_DENTAL),
]


def demo_records() -> list[dict]:
    """Raw lead dicts for the demo (deep-copied so callers can mutate freely)."""
    return [dict(rec) for rec, _ in _DEMO]


def demo_html_for(website: str) -> str:
    """The fixture HTML to use when 'enriching' a demo record's website offline.
    Returns '' for sites meant to look unreachable."""
    for rec, html in _DEMO:
        if rec["website"] == website:
            return html
    return ""
