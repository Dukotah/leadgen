"""
Reusable website-signal helpers — pure functions over an HTML string (and an
optional base URL), each independently testable OFFLINE with no network.

These extract conversion/outreach signals a vertical's enrich_fn can attach to a
lead without any third-party API or new dependency (stdlib re/socket/urllib only):
  - find_emails():       plausible contact emails, junk filtered, best-first
  - copyright_year():    the footer "© 2019" year (a "stale site" proxy)
  - has_ecommerce():     a store/cart is present (Shopify, Woo, "add to cart", …)
  - has_booking():       online scheduling is present (Calendly, "book now", …)
  - detect_socials():    the social profiles linked from the page
  - domain_resolves():   a no-dependency deliverability proxy (DNS A-record only)
  - page_weight_bytes(): byte size of the HTML (a crude page-weight proxy)
  - is_mobile_friendly():viewport meta + responsive hints (more robust than meta)

Every function tolerates empty/None input and never raises.
"""
from __future__ import annotations

import re
import socket
from urllib.parse import urlparse

# ── Emails ────────────────────────────────────────────────────────────────────

# A deliberately conservative address shape: a real local-part and a real TLD.
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
)

# mailto: links are the highest-confidence source — pull them first.
_MAILTO_RE = re.compile(r'mailto:([^"\'?>\s]+)', re.IGNORECASE)

# Local-parts / domains that mean "not a human contact address".
_EMAIL_JUNK_LOCAL = (
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "bounce", "notifications", "notification",
)
_EMAIL_JUNK_DOMAINS = (
    "sentry.io", "example.com", "example.org", "example.net", "domain.com",
    "email.com", "yourdomain.com", "wixpress.com", "sentry-next.wixpress.com",
    "wix.com", "godaddy.com", "squarespace.com", "wordpress.com", "schema.org",
    "w3.org", "googleapis.com", "gstatic.com", "cloudflare.com", "jquery.com",
    "2x.png", "sentry.wixpress.com",
)
# Image-name false positives: foo@2x.png, sprite@3x.jpg, etc.
_IMAGE_TAIL_RE = re.compile(r"@\d+x", re.IGNORECASE)
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico")
# Preference order for "best" contact address.
_EMAIL_PREFER = ("info", "hello", "contact", "sales", "office", "admin", "team")


def _is_junk_email(email: str) -> bool:
    """True if `email` looks like a system/placeholder/image string, not a
    human-reachable contact address."""
    e = email.lower().strip().strip(".")
    if "@" not in e:
        return True
    local, _, domain = e.partition("@")
    if not local or not domain or "." not in domain:
        return True
    if _IMAGE_TAIL_RE.search(e):
        return True
    if e.endswith(_IMAGE_EXT) or domain.endswith(_IMAGE_EXT):
        return True
    if any(local == j or local.startswith(j) for j in _EMAIL_JUNK_LOCAL):
        return True
    if any(domain == d or domain.endswith("." + d) for d in _EMAIL_JUNK_DOMAINS):
        return True
    # A "domain" that is actually a filename fragment (e.g. icon@2x or u003e).
    if domain.startswith("2x") or domain.startswith("3x"):
        return True
    return False


def _email_rank(email: str) -> tuple[int, int, str]:
    """Sort key: preferred local-parts first, then shorter, then alphabetical."""
    local = email.lower().partition("@")[0]
    try:
        pref = _EMAIL_PREFER.index(local)
    except ValueError:
        pref = len(_EMAIL_PREFER)
    return (pref, len(email), email.lower())


def find_emails(html: str) -> list[str]:
    """Extract plausible contact emails from `html`, junk filtered.

    mailto: links are trusted first, then any address-shaped text in the page.
    Filters noreply/sentry/example/wixpress addresses and image-name false
    positives (logo@2x.png). Returns a de-duplicated list, best-first:
    info@/hello@/contact@ are preferred over random personal addresses.
    """
    if not html:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for raw in _MAILTO_RE.findall(html) + _EMAIL_RE.findall(html):
        email = raw.strip().strip(".").rstrip(">").strip()
        # mailto can carry a "Name <addr>" or trailing params — re-extract.
        m = _EMAIL_RE.search(email)
        if not m:
            continue
        email = m.group(0)
        key = email.lower()
        if key in seen:
            continue
        if _is_junk_email(email):
            continue
        seen.add(key)
        found.append(email)
    return sorted(found, key=_email_rank)


# ── Copyright year ────────────────────────────────────────────────────────────

_YEAR_RE = re.compile(
    r"(?:©|&copy;|&#169;|\(c\)|copyright)\s*"
    r"(?:[^\d<>]{0,40}?)?"          # optional "all rights reserved", company, etc.
    r"((?:19|20)\d{2})"             # a four-digit year
    r"(?:\s*[–—\-]\s*((?:19|20)\d{2}))?",  # optional "2019-2024" range
    re.IGNORECASE,
)


def copyright_year(html: str) -> int | None:
    """Parse a footer copyright year from `html` ("© 2019", "Copyright 2019",
    "© 2019-2024 Acme"). Returns the most recent plausible year (1990..2100)
    across all matches, or None if no copyright year is present.

    A "© 2019" on an otherwise-modern-looking page is a strong staleness signal.
    """
    if not html:
        return None
    best: int | None = None
    for m in _YEAR_RE.finditer(html):
        for grp in m.groups():
            if not grp:
                continue
            yr = int(grp)
            if 1990 <= yr <= 2100 and (best is None or yr > best):
                best = yr
    return best


# ── E-commerce / cart ─────────────────────────────────────────────────────────

_ECOMMERCE_MARKERS = (
    "cdn.shopify.com", "shopify", "woocommerce", "wc-cart", "wp-content/plugins/woocommerce",
    "add to cart", "add-to-cart", "addtocart", "bigcommerce", "snipcart",
    "ecwid", "squarespace-commerce", "/cart", "shopping cart", "checkout",
    "view cart", "your cart", "data-product-id", "magento", "/products/",
    "buy now", "squareup.com/market", "gumroad",
)


def has_ecommerce(html: str) -> bool:
    """True if `html` shows a real online store / cart (Shopify, WooCommerce,
    BigCommerce, Snipcart, Ecwid, a checkout/cart page, "add to cart", …).

    Distinguishes a transactional site from a brochure site — useful both as a
    qualifier and to avoid pitching e-commerce to a shop that already has it.
    """
    if not html:
        return False
    low = html.lower()
    return any(marker in low for marker in _ECOMMERCE_MARKERS)


# ── Online booking / scheduling ───────────────────────────────────────────────

_BOOKING_MARKERS = (
    "calendly.com", "calendly", "acuityscheduling.com", "acuity scheduling",
    "squareup.com/appointments", "square appointments", "schedulicity",
    "setmore", "simplybook", "book now", "book online", "book an appointment",
    "book a table", "schedule an appointment", "schedule online",
    "request an appointment", "opentable.com", "opentable", "resy.com", "resy",
    "tock", "vagaro", "mindbodyonline", "mindbody", "housecallpro",
    "appointmentplus", "youcanbook.me", "tidycal", "cal.com",
)


def has_booking(html: str) -> bool:
    """True if `html` exposes online scheduling/booking (Calendly, Acuity,
    Square Appointments, OpenTable, Resy, "book now", "schedule an appointment",
    …). Absence on a service business is a common, sellable gap.
    """
    if not html:
        return False
    low = html.lower()
    return any(marker in low for marker in _BOOKING_MARKERS)


# ── Social profiles ───────────────────────────────────────────────────────────

# Per-network: (canonical key, host regex, capture of the handle/path tail).
# Hosts are matched on a URL inside an href or plain text.
_SOCIAL_PATTERNS: dict[str, re.Pattern] = {
    "facebook": re.compile(
        r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.com)/([^\s\"'<>?#]+)",
        re.IGNORECASE),
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/([^\s\"'<>?#]+)", re.IGNORECASE),
    "linkedin": re.compile(
        r"https?://(?:www\.)?linkedin\.com/((?:company|in|pub)/[^\s\"'<>?#]+|[^\s\"'<>?#]+)",
        re.IGNORECASE),
    "twitter": re.compile(
        r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([^\s\"'<>?#]+)", re.IGNORECASE),
    "tiktok": re.compile(
        r"https?://(?:www\.)?tiktok\.com/(@?[^\s\"'<>?#]+)", re.IGNORECASE),
    "youtube": re.compile(
        r"https?://(?:www\.|m\.)?youtube\.com/([^\s\"'<>?#]+)", re.IGNORECASE),
}

# Path fragments that are sharers/widgets/login pages, not a business profile.
_SOCIAL_NON_PROFILE = (
    "sharer", "share.php", "share?", "intent/", "intent?", "/tr?", "plugins/",
    "/login", "/signup", "/home", "/embed", "/widgets", "dialog/", "/oauth",
)


def _clean_social(network: str, tail: str) -> str | None:
    """Normalize a captured social path tail to a handle/profile, or None if it
    is a sharer/login/widget rather than a real profile."""
    tail = (tail or "").strip().strip("/")
    if not tail:
        return None
    low = tail.lower()
    if any(bad in low for bad in _SOCIAL_NON_PROFILE):
        return None
    first = low.split("/")[0]
    # network-specific obvious non-handles
    if network == "facebook" and first in ("sharer.php", "dialog", "tr", "plugins"):
        return None
    if network == "twitter" and first in ("intent", "share", "home", "hashtag"):
        return None
    if network == "youtube" and first in ("watch", "embed", "results"):
        return None
    return tail


def detect_socials(html: str) -> dict:
    """Return the social profiles linked from `html` as a dict with a fixed set
    of keys — {facebook, instagram, linkedin, twitter, tiktok, youtube} — whose
    value is the first plausible handle/URL tail found, or None.

    Sharer/login/widget links (facebook.com/sharer.php, twitter.com/intent/…)
    are skipped so we report the business's own presence, not share buttons.
    """
    out: dict[str, str | None] = {
        "facebook": None, "instagram": None, "linkedin": None,
        "twitter": None, "tiktok": None, "youtube": None,
    }
    if not html:
        return out
    for network, pat in _SOCIAL_PATTERNS.items():
        for m in pat.finditer(html):
            handle = _clean_social(network, m.group(1))
            if handle:
                out[network] = handle
                break
    return out


# ── Domain resolution (deliverability proxy) ──────────────────────────────────

def domain_resolves(url_or_domain: str) -> bool:
    """A no-dependency deliverability proxy: True if the domain has a DNS
    A-record (socket.gethostbyname succeeds), else False. Never raises.

    NOTE: this is NOT an MX check — a domain can resolve yet accept no mail, or
    accept mail on a different host. A true MX-record lookup would require the
    optional `dnspython` package (out of scope here, no new dependencies). Use
    this only as a cheap "does this domain exist / is the website live" signal.
    """
    if not url_or_domain:
        return False
    raw = url_or_domain.strip()
    try:
        if "://" in raw:
            host = urlparse(raw).hostname or ""
        elif "/" in raw or raw.startswith("www."):
            host = urlparse("http://" + raw).hostname or ""
        else:
            host = raw
        host = (host or "").strip().strip(".").lower()
        if not host or "." not in host:
            # bare hostnames like "localhost" are allowed through
            if host != "localhost":
                return False
        socket.gethostbyname(host)
        return True
    except Exception:
        return False


# ── Page weight (performance proxy) ───────────────────────────────────────────

def page_weight_bytes(html: str) -> int:
    """Byte size of `html` (UTF-8 encoded) — a crude page-weight proxy.

    A heavy homepage HTML payload (lots of inline scripts/styles/markup) is a
    weak signal of a bloated, slow-to-render site. Returns 0 for empty/None.
    This counts only the HTML document itself, not its linked assets.
    """
    if not html:
        return 0
    return len(html.encode("utf-8", "replace"))


# ── Mobile-friendliness (responsive heuristic) ────────────────────────────────

# A viewport meta tag that opts into responsive scaling.
_VIEWPORT_RE = re.compile(
    r'<meta[^>]+name=["\']?viewport["\']?[^>]*>', re.IGNORECASE)

# Responsive hints beyond the bare meta tag: CSS media queries, fluid widths,
# or a class from a known responsive/mobile-first framework.
_RESPONSIVE_HINTS = re.compile(
    r"@media\b"                                   # CSS media query
    r"|max-width\s*:"                             # fluid breakpoint in CSS
    r"|min-width\s*:"
    r"|\bcol-(?:xs|sm|md|lg|xl)\b"                # Bootstrap grid
    r"|\b(?:container|row)-fluid\b"               # Bootstrap fluid
    r"|\bflex-wrap\b"                             # flexbox responsive
    r"|\bgrid-cols-\d"                            # Tailwind grid
    r"|\b(?:sm|md|lg|xl):[a-z]"                   # Tailwind responsive prefixes
    r'|srcset='                                   # responsive images
    r"|\bw-full\b|\bw-100\b"                       # full-width utility classes
    r"|media=[\"']?(?:screen[^\"'>]*and|\([^\"'>]*width)",  # <link media> query
    re.IGNORECASE)


def is_mobile_friendly(html: str) -> bool:
    """True if `html` is plausibly mobile-responsive: a viewport meta tag is
    present AND there are responsive hints (a CSS media query / max-width /
    min-width rule, responsive images, or a known responsive-framework class
    such as Bootstrap's col-md-* or Tailwind's md:/lg: prefixes).

    Stricter than the bare viewport meta alone (which audit.mobile_viewport
    already reports): a page can declare a viewport yet still ship a fixed-width
    desktop layout. Returns False for empty/None and never raises.
    """
    if not html:
        return False
    if not _VIEWPORT_RE.search(html):
        return False
    return bool(_RESPONSIVE_HINTS.search(html))
