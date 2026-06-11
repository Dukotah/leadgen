"""
Competitor suppression — find businesses that are ALREADY a competitor's client,
so you don't waste an outreach on them. Optional: any vertical whose competitors
publish their client lists can wire this up via suppression_fn.

How it works: competitors love to brag. Most B2B service firms publish testimonial
pages, "clients we serve", and client-logo walls. We fetch those pages and extract
the named clients, then the pipeline sinks any lead whose normalized name matches.

build_suppression_set(seeds) -> {normalized_name: "competitor_label", ...}
"""
from __future__ import annotations

import re
from html import unescape

from .audit import fetch


def norm(name: str) -> str:
    """Normalized match key — lowercase alphanumerics only. Strips the legal-suffix
    noise ('LLC', 'Inc', 'Realty', 'Group') that differs between a testimonial and
    a listing for the same firm."""
    n = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    n = re.sub(r"\b(llc|inc|incorporated|co|company|group|team|realty|realtors|"
               r"real estate|properties|brokerage|the)\b", " ", n)
    return re.sub(r"\s+", "", n)


# Patterns that tend to wrap a client/testimonial name on B2B service sites.
_NAME_PATTERNS = [
    # quoted testimonial author lines:  "— Jane Doe, Acme Realty"
    re.compile(r"[—–-]\s*[A-Z][\w.&'\- ]{2,40},\s*([A-Z][\w.&'\- ]{2,50})"),
    # logo/image alt text:  alt="Acme Realty"
    re.compile(r'alt="([A-Z][\w.&\'\- ]{2,50})"'),
    # explicit attribution:  <cite>Acme Realty</cite>, class="client-name">Acme...
    re.compile(r'(?:<cite[^>]*>|client[-_ ]?name[^>]*>)\s*([A-Z][\w.&\'\- ]{2,50})'),
]

# Words that, if they dominate an extracted phrase, mean it's not a client name.
_JUNK = ("testimonial", "review", "client", "logo", "icon", "image", "photo",
         "read more", "learn more", "see all", "google", "facebook", "verified")


def _candidates_from_html(html: str) -> set[str]:
    found: set[str] = set()
    text = unescape(html or "")
    for pat in _NAME_PATTERNS:
        for m in pat.findall(text):
            name = m.strip(" .,-")
            low = name.lower()
            if len(name) < 3 or any(j in low for j in _JUNK):
                continue
            found.add(name)
    return found


def scrape_competitor_clients(url: str) -> set[str]:
    """Fetch one competitor page and return the raw client names found on it."""
    r = fetch(url, timeout=12)
    if not r or r.status_code >= 400:
        return set()
    return _candidates_from_html(r.text)


def build_suppression_set(seeds: dict[str, str], log=print) -> dict[str, str]:
    """seeds = {competitor_label: testimonial_or_clients_url, ...}

    Returns {normalized_client_name: competitor_label}. Anyone in here is already
    served by a competitor — the scorer sinks them (kept, not deleted, so you can
    re-approach when a contract lapses)."""
    suppressed: dict[str, str] = {}
    for label, url in (seeds or {}).items():
        names = scrape_competitor_clients(url)
        for raw in names:
            key = norm(raw)
            if key:
                suppressed.setdefault(key, label)
        log(f"  suppression: {label} → {len(names)} client names scraped")
    log(f"  suppression set: {len(suppressed)} unique competitor clients")
    return suppressed
