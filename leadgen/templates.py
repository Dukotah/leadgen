"""
Outreach opener templates — pure, dependency-free {token} rendering.

A template is a plain string with {tokens} that get filled from a lead record,
e.g. "Hi {name} — I help {city} {category} businesses ...". Missing tokens
render as the empty string (never a KeyError), so any record shape is safe.

Tokens are just record keys: {name}, {city}, {category}, {website}, {phone},
{email}, {address}, {state}, {zip}, {tier}, {score}, {why}, ... — anything in
the record can be referenced.
"""
from __future__ import annotations

import string

# A few ready-to-use named openers. Customize per vertical by passing your own
# dict to render_all(); these are sensible defaults for local-business outreach.
DEFAULT_OPENERS: dict[str, str] = {
    "cold_email": (
        "Hi {name},\n\n"
        "I came across your {category} business in {city} and took a quick look "
        "at {website}. I help local {category} owners get more calls from Google "
        "with a fast, modern site. Worth a 10-minute chat this week?\n\n"
        "Best,\nDuke"
    ),
    "cold_call": (
        "Hi, is this {name}? I work with {category} businesses around {city} on "
        "their web presence — I noticed a couple of quick wins on your site and "
        "wanted to see if it's worth 10 minutes to walk you through them."
    ),
    "sms": (
        "Hi {name}! Saw your {category} listing in {city}. I build fast sites that "
        "rank on Google — open to a quick look? Reply YES and I'll send examples."
    ),
}


class _BlankDict(dict):
    """A dict that returns "" for any missing key, so str.format_map never raises."""

    def __missing__(self, key):  # noqa: D401 - simple mapping hook
        return ""


def render_opener(template: str, rec: dict) -> str:
    """Fill {tokens} in `template` from `rec`; missing tokens -> "" (never KeyError).

    None values render as "" rather than the literal "None". Malformed braces in
    the template are returned untouched rather than raising.
    """
    mapping = _BlankDict()
    if rec:
        for k, v in rec.items():
            mapping[k] = "" if v is None else v
    try:
        return string.Formatter().vformat(template, (), mapping)
    except (ValueError, IndexError, KeyError):
        # Malformed format spec / positional field — return template as-is.
        return template


def render_all(rec: dict, templates: dict | None = None) -> dict:
    """Render every named template against `rec`; return {name: rendered}."""
    templates = DEFAULT_OPENERS if templates is None else templates
    return {name: render_opener(tmpl, rec) for name, tmpl in templates.items()}
