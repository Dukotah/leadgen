"""
Scoring helpers any vertical can share — pure, stdlib-only, network-free.

A vertical's score_fn turns raw signals into a (score, tier, reasons) triple
(see verticals/web_design.py). These helpers keep that consistent across
verticals so the dashboard compares apples to apples:

  - normalize_score():  scale a raw point total to a 0..100 score (clamped)
  - tier_from_score():  bucket a 0..100 score into "A"/"B"/"C" by thresholds
  - reason_tags():      turn a "; "-joined reason string into machine-readable
                        tag codes (for filtering/analytics)
  - ScoreBuilder:       accumulate (points, reason, code) and emit a tidy
                        (score100, tier, reasons_str, tags) result

Nothing here touches the network or any third-party package.
"""
from __future__ import annotations

import re

# ── normalize_score ───────────────────────────────────────────────────────────

def normalize_score(raw: int, max_raw: int) -> int:
    """Scale `raw` points (out of `max_raw`) to an integer 0..100, clamped.

    A negative raw clamps to 0; a raw above max_raw clamps to 100. If max_raw
    is 0 or negative the scale is undefined, so return 0. Never raises.
    """
    try:
        raw = int(raw)
        max_raw = int(max_raw)
    except (TypeError, ValueError):
        return 0
    if max_raw <= 0:
        return 0
    if raw <= 0:
        return 0
    if raw >= max_raw:
        return 100
    return round(raw * 100 / max_raw)


# ── tier_from_score ───────────────────────────────────────────────────────────

def tier_from_score(score100: int, a: int = 60, b: int = 30) -> str:
    """Bucket a 0..100 score into "A" (>= a), "B" (>= b), else "C".

    Defaults: A at 60+, B at 30+, C below. Pass a/b to retune per vertical.
    Never raises; non-numeric input falls to "C".
    """
    try:
        s = int(score100)
    except (TypeError, ValueError):
        return "C"
    if s >= a:
        return "A"
    if s >= b:
        return "B"
    return "C"


# ── reason_tags ───────────────────────────────────────────────────────────────

# Known reason phrases → stable tag codes. Matched as a case-insensitive
# substring so parameterized reasons ("slow (5200ms)", "DIY (Wix)") still map.
_TAG_MAP: tuple[tuple[str, str], ...] = (
    ("no website", "no_website"),
    ("non-site link", "social_only"),
    ("social-only", "social_only"),
    ("site unreachable", "unreachable"),
    ("unreachable", "unreachable"),
    ("no https", "no_https"),
    ("http only", "no_https"),
    ("not mobile-friendly", "not_mobile_friendly"),
    ("no mobile viewport", "not_mobile_friendly"),
    ("not mobile", "not_mobile_friendly"),
    ("slow", "slow_load"),
    ("diy", "diy_builder"),
    ("stale", "stale_site"),
    ("outdated", "stale_site"),
    ("no booking", "no_booking"),
    ("no email", "no_email"),
    ("phone listed", "phone_listed"),
    ("real site, no obvious issues", "no_issues"),
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Strip parenthetical detail so "slow (5200ms)" slugs to "slow", not "slow_5200ms".
_PAREN_RE = re.compile(r"\([^)]*\)")


def _slug(reason: str) -> str:
    """Fallback tag code for an unmapped reason: lower, drop parentheticals,
    collapse non-alphanumerics to single underscores, trim."""
    r = _PAREN_RE.sub(" ", reason.lower())
    return _SLUG_RE.sub("_", r).strip("_")


def reason_tags(reasons: str) -> list[str]:
    """Turn a "; "-joined reason string into short machine-readable tag codes.

    Each reason is mapped via a small known-phrase table (so "no HTTPS" ->
    "no_https", "slow (5200ms)" -> "slow_load", "NO WEBSITE" -> "no_website");
    anything unmapped falls back to a slug of the reason. De-duplicated,
    order-preserving. Empty/None input -> []. Never raises.
    """
    if not reasons:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in str(reasons).split(";"):
        reason = part.strip()
        if not reason:
            continue
        low = reason.lower()
        code = None
        for phrase, tag in _TAG_MAP:
            if phrase in low:
                code = tag
                break
        if code is None:
            code = _slug(reason)
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


# ── ScoreBuilder ──────────────────────────────────────────────────────────────

class ScoreBuilder:
    """Accumulate scoring signals, then emit a tidy normalized result.

    Lets a vertical's score_fn stay readable:

        sb = ScoreBuilder()
        if not site:
            sb.add(60, "NO WEBSITE", "no_website")
        if not audit.get("https"):
            sb.add(18, "no HTTPS")            # code inferred from the reason
        score100, tier, reasons, tags = sb.result(max_raw=100)

    add() records points + a human reason (and an optional explicit tag code).
    result(max_raw) normalizes the raw total to 0..100, derives a tier, and
    returns the joined reason string plus machine-readable tags. Pure; the
    builder holds no global state and never touches the network.
    """

    __slots__ = ("_raw", "_reasons", "_codes")

    def __init__(self) -> None:
        self._raw: int = 0
        self._reasons: list[str] = []
        self._codes: list[str | None] = []

    def add(self, points: int, reason: str, code: str | None = None) -> "ScoreBuilder":
        """Record `points` toward the raw total and a human-readable `reason`.

        `code` is an optional explicit tag; if omitted it is inferred from the
        reason at result() time via reason_tags(). Returns self so calls chain.
        A blank reason is allowed (points still count) but produces no tag.
        """
        try:
            self._raw += int(points)
        except (TypeError, ValueError):
            pass
        reason = (reason or "").strip()
        if reason:
            self._reasons.append(reason)
            self._codes.append(code.strip() if isinstance(code, str) and code.strip() else None)
        return self

    @property
    def raw(self) -> int:
        """The accumulated raw point total so far."""
        return self._raw

    def reasons_str(self) -> str:
        """The reasons joined the same way verticals join them ("; ")."""
        return "; ".join(self._reasons)

    def tags(self) -> list[str]:
        """Machine-readable tag codes: explicit codes win, otherwise inferred
        from each reason. De-duplicated, order-preserving."""
        out: list[str] = []
        seen: set[str] = set()
        for reason, code in zip(self._reasons, self._codes):
            tag = code or (reason_tags(reason)[:1] or [None])[0]
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
        return out

    def result(self, max_raw: int) -> tuple[int, str, str, list[str]]:
        """Finalize: (score100, tier, reasons_str, tags).

        Normalizes the raw total against `max_raw` (clamped 0..100), derives a
        tier via tier_from_score, and emits the joined reasons + tags.
        """
        score100 = normalize_score(self._raw, max_raw)
        tier = tier_from_score(score100)
        return score100, tier, self.reasons_str(), self.tags()
