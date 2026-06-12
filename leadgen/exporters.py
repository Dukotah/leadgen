"""
Extra output formats — JSON/JSONL, vCard, per-tier CSV splits, a Markdown
summary report, and CRM-preset CSVs (HubSpot/Pipedrive/Mailchimp header maps).

Pure functions: each takes the scored leads and writes a file, returning the
path written. Stdlib + leadgen.export only; robust to missing dict keys.
"""
from __future__ import annotations

import json

from leadgen.export import write_csv


# ── JSON / JSON Lines ─────────────────────────────────────────────────────────

def write_jsonl(leads: list[dict], columns: list[tuple[str, str]], path: str) -> str:
    """One JSON object per line, projected to the column keys."""
    keys = [k for _, k in columns]
    with open(path, "w", encoding="utf-8") as f:
        for r in leads:
            obj = {k: r.get(k) for k in keys}
            f.write(json.dumps(obj, ensure_ascii=False))
            f.write("\n")
    return path


def write_json(leads: list[dict], columns: list[tuple[str, str]], path: str) -> str:
    """A JSON array of objects, projected to the column keys."""
    keys = [k for _, k in columns]
    rows = [{k: r.get(k) for k in keys} for r in leads]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path


# ── vCard ─────────────────────────────────────────────────────────────────────

def write_vcard(leads: list[dict], path: str) -> str:
    """A .vcf with FN/TEL/EMAIL/URL/ADR per lead; empty fields are skipped."""
    with open(path, "w", encoding="utf-8") as f:
        for r in leads:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
            phone = (r.get("phone") or "").strip()
            if phone:
                lines.append(f"TEL:{phone}")
            email = (r.get("email") or "").strip()
            if email:
                lines.append(f"EMAIL:{email}")
            website = (r.get("website") or "").strip()
            if website:
                lines.append(f"URL:{website}")
            address = (r.get("address") or "").strip()
            if address:
                # ADR has 7 semicolon-separated components; put the whole
                # address in the street field.
                lines.append(f"ADR:;;{address};;;;")
            lines.append("END:VCARD")
            f.write("\n".join(lines))
            f.write("\n")
    return path


# ── Per-tier CSV splits ───────────────────────────────────────────────────────

def write_per_tier(leads: list[dict], columns: list[tuple[str, str]], stem: str) -> dict:
    """Write <stem>_A.csv/_B.csv/_C.csv via export.write_csv; return {tier: path}."""
    out: dict[str, str] = {}
    for tier in ("A", "B", "C"):
        rows = [r for r in leads if r.get("tier") == tier]
        path = f"{stem}_{tier}.csv"
        write_csv(rows, columns, path)
        out[tier] = path
    return out


# ── Markdown summary report ───────────────────────────────────────────────────

def _md_cell(value) -> str:
    s = "" if value is None else str(value)
    return s.replace("|", "\\|").replace("\n", " ").strip()


def _score_key(r: dict):
    s = r.get("score")
    try:
        return float(s)
    except (TypeError, ValueError):
        return float("-inf")


def write_markdown_report(leads: list[dict], stem: str, title: str = "Leads") -> str:
    """A <stem>.leads.md summary: counts per tier + a table of the top 25 leads.
    The `.leads.md` suffix keeps generated reports out of git (see .gitignore)."""
    path = f"{stem}.leads.md"
    counts: dict[str, int] = {}
    for r in leads:
        t = r.get("tier") or "—"
        counts[t] = counts.get(t, 0) + 1

    lines = [f"# {title}", "", f"Total leads: {len(leads)}", "", "## Counts per tier", ""]
    for tier in ("A", "B", "C"):
        lines.append(f"- Tier {tier}: {counts.get(tier, 0)}")
    other = sorted(k for k in counts if k not in ("A", "B", "C"))
    for k in other:
        lines.append(f"- {k}: {counts[k]}")

    lines += ["", "## Top 25 leads", ""]
    headers = ["name", "tier", "score", "city", "phone", "website", "why"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    top = sorted(leads, key=_score_key, reverse=True)[:25]
    for r in top:
        row = [_md_cell(r.get(h)) for h in headers]
        lines.append("| " + " | ".join(row) + " |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    return path


# ── CRM-preset CSVs ───────────────────────────────────────────────────────────

# Common fields we know how to export, in a stable order.
_CRM_FIELDS = ("name", "phone", "email", "website", "address", "city", "state", "zip")

CRM_HEADER_PRESETS: dict[str, dict[str, str]] = {
    "hubspot": {
        "name": "Company Name",
        "phone": "Phone Number",
        "email": "Email",
        "website": "Website URL",
        "address": "Street Address",
        "city": "City",
        "state": "State/Region",
        "zip": "Postal Code",
    },
    "pipedrive": {
        "name": "Organization",
        "phone": "Phone",
        "email": "Email",
        "website": "Website",
        "address": "Address",
        "city": "City",
        "state": "State",
        "zip": "ZIP",
    },
    "mailchimp": {
        "name": "Company",
        "phone": "Phone",
        "email": "Email Address",
        "website": "Website",
        "address": "Address",
        "city": "City",
        "state": "State",
        "zip": "Zip",
    },
}


def write_crm_csv(leads: list[dict], path: str, preset: str) -> str:
    """Write a CSV with a CRM preset's renamed headers for common fields."""
    rename = CRM_HEADER_PRESETS[preset]
    fields = [k for k in _CRM_FIELDS if k in rename]
    columns = [(rename[k], k) for k in fields]
    return write_csv(leads, columns, path)
