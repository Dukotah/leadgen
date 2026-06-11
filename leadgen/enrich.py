"""
Generic enrichment helpers verticals call from their enrich_fn.

These add depth to a raw lead by visiting the business's own website:
  - fetch_pages():         homepage + a few candidate sub-pages that resolve
  - estimate_roster():     distinct team/staff count (a size proxy), de-duplicated
  - find_decision_maker(): a likely owner/manager name + title
  - find_phrases():        which of a phrase list appear (hiring signals, etc.)

Nothing here is vertical-specific; the vertical supplies the paths/markers/titles.
The estimators are written to resist the two common traps: roster links counted
twice (image + name) and the same roster echoed in nav/footer across pages.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from .audit import fetch, hostname


def fetch_pages(base_url: str, paths: list[str], cap: int = 4) -> dict[str, str]:
    """Return {url: html} for the homepage plus up to `cap` candidate sub-pages
    that actually resolve. Stops early once cap pages succeed."""
    out: dict[str, str] = {}
    if not base_url:
        return out
    home = fetch(base_url)
    if home is not None and home.status_code < 400:
        out[base_url] = home.text
    base = base_url if base_url.startswith("http") else "http://" + base_url
    for p in paths:
        if len(out) >= cap + 1:
            break
        r = fetch(urljoin(base, p))
        if r is not None and r.status_code < 400 and len(r.text) > 500:
            out[urljoin(base, p)] = r.text
    return out


# Agent-profile link patterns: /agent/slug, /agents/slug, /team/slug, /our-team/slug
_AGENT_HREF = re.compile(r'href="[^"]*/(?:agent|agents|team|our-team|associates?)/'
                         r'([a-z0-9][a-z0-9\-_]{1,60})/?["#?]', re.IGNORECASE)
# License numbers are a near-unique per-agent fingerprint.
_LICENSE = re.compile(r'(?:dre|calbre|lic|license|bre)\s*#?\s*(\d{6,8})', re.IGNORECASE)


def estimate_roster(pages: dict[str, str], extra_card_patterns: list[str] | None = None,
                    cap: int = 1000) -> int:
    """Best estimate of how many people a business lists (team size), de-duplicated.

    Strategy — take the strongest of three DISTINCT-count signals (not raw
    counts), so duplicate links (image + name → same slug) don't inflate it:
      1. distinct staff/team profile slugs   (e.g. /team/jane-smith/)
      2. distinct license numbers            (e.g. a professional license #…)
      3. distinct names inside team-card containers (fallback)
    Returns 0 when nothing is found (caller treats 0 as "unknown", not "zero").
    """
    slugs: set[str] = set()
    licenses: set[str] = set()
    for html in pages.values():
        for m in _AGENT_HREF.findall(html):
            slugs.add(m.lower())
        for m in _LICENSE.findall(html):
            licenses.add(m)

    best = max(len(slugs), len(licenses))

    # Fallback: count agent-card-like containers if links/licenses were sparse.
    if best < 2 and extra_card_patterns:
        for html in pages.values():
            h = html.lower()
            for pat in extra_card_patterns:
                best = max(best, len(re.findall(pat, h)))

    return min(best, cap)


def find_phrases(pages: dict[str, str], phrases: list[str]) -> list[str]:
    """Return the subset of `phrases` (lowercased match) present across pages."""
    blob = "\n".join(pages.values()).lower()
    return [p for p in phrases if p.lower() in blob]


# Title list is injected; we match a Name adjacent to one of those titles.
# NAME excludes '.' and digits so it can't bleed across a sentence boundary
# ("…Petaluma. Susan Park" → only "Susan Park" matches).
_NAME_RE = r"[A-Z][a-zA-Z'’\-]+(?:\s+[A-Z][a-zA-Z'’\-]+){1,2}"


def find_decision_maker(pages: dict[str, str], titles: list[str]) -> tuple[str, str]:
    """Find a 'Name, Title' / 'Title: Name' / 'Name — Title' decision-maker.
    More-senior titles win (the titles list is treated as a seniority order).
    Returns (name, title) or ('', '')."""
    ordered = list(dict.fromkeys(titles))  # preserve caller's seniority order
    # match longest titles first so 'broker/owner' isn't shadowed by 'broker'
    title_alt = "|".join(re.escape(t) for t in sorted(ordered, key=len, reverse=True))
    SEP = r"\s*[,–—\-:|]\s*"
    pat_name_title = re.compile(rf"({_NAME_RE}){SEP}({title_alt})\b", re.IGNORECASE)
    pat_title_name = re.compile(rf"\b({title_alt}){SEP}({_NAME_RE})", re.IGNORECASE)

    best = ("", "")
    best_rank = 10**9
    for html in pages.values():
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        for is_name_first, pat in ((True, pat_name_title), (False, pat_title_name)):
            for m in pat.finditer(text):
                raw_name = m.group(1) if is_name_first else m.group(2)
                title = (m.group(2) if is_name_first else m.group(1)).strip(" .,-—–")
                name = _clean_name(raw_name)
                if not name:
                    continue
                rank = next((i for i, t in enumerate(ordered)
                             if t.lower() == title.lower()), len(ordered))
                if rank < best_rank:
                    best, best_rank = (name, title), rank
    return best


_NON_NAME_WORDS = {"our", "the", "meet", "team", "about", "contact", "broker",
                   "owner", "agent", "agents", "realtor", "realtors", "transaction",
                   "coordinator", "join", "careers", "home", "welcome", "us"}


def _clean_name(raw: str) -> str:
    """Trim a captured phrase to a plausible trailing personal name, dropping
    leading stop-words ('Team Greg Hall' → 'Greg Hall'). Returns '' if implausible."""
    parts = [p for p in raw.split() if p]
    # strip leading stop-words / lowercase leftovers
    while parts and parts[0].lower() in _NON_NAME_WORDS:
        parts.pop(0)
    # keep the last 3 tokens at most
    if len(parts) > 3:
        parts = parts[-3:]
    if not (2 <= len(parts) <= 3):
        return ""
    if any(p.lower() in _NON_NAME_WORDS for p in parts):
        return ""
    if not all(p[:1].isupper() for p in parts):
        return ""
    return " ".join(parts)


def primary_domain(url: str) -> str:
    return hostname(url)


# Back-compat: keep the old name as a thin wrapper (some callers/tests use it).
def count_matches(pages: dict[str, str], patterns: list[str], cap: int = 500) -> int:
    best = 0
    for html in pages.values():
        h = html.lower()
        for pat in patterns:
            best = max(best, len(re.findall(pat, h)))
    return min(best, cap)
