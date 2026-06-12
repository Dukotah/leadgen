"""
Extra output formats — JSON/JSONL, vCard, per-tier CSV splits, a Markdown
summary report, and CRM-preset CSVs (HubSpot/Pipedrive/Mailchimp header maps).

Pure functions: each takes the scored leads and writes a file, returning the
path written. Stdlib + leadgen.export only; robust to missing dict keys.
"""
from __future__ import annotations

import csv
import json
import subprocess

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


# ── TSV (Google-Sheets paste-friendly) ────────────────────────────────────────

def _tsv_cell(value) -> str:
    """Stringify a value for a TSV cell: drop tabs/newlines so columns stay aligned."""
    s = "" if value is None else str(value)
    return s.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def write_tsv(leads: list[dict], columns: list[tuple[str, str]], path: str) -> str:
    """Tab-separated values — paste straight into Google Sheets / Excel.

    No CSV quoting is used (none is needed): every cell has its tabs and newlines
    stripped to spaces so the row/column structure is preserved on paste.
    """
    keys = [k for _, k in columns]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(_tsv_cell(h) for h, _ in columns))
        f.write("\n")
        for r in leads:
            f.write("\t".join(_tsv_cell(r.get(k, "")) for k in keys))
            f.write("\n")
    return path


# ── Master CSV with de-duplicated append ──────────────────────────────────────

def _default_key(rec: dict):
    """Default dedupe key: (name, phone), normalized to lowercase/stripped."""
    name = (rec.get("name") or "").strip().lower()
    phone = (rec.get("phone") or "").strip().lower()
    return (name, phone)


def append_to_master(leads: list[dict], columns: list[tuple[str, str]],
                     master_path: str, key_fn=None) -> int:
    """Append `leads` to a running master CSV, skipping rows already present.

    Dedupe is by `key_fn(rec)` (or name+phone by default), computed both over the
    rows already in the file and over the incoming leads. Creates the file with a
    header row if it does not yet exist. Returns the count of NEW rows appended.
    """
    import os

    key_fn = key_fn or _default_key
    header = [h for h, _ in columns]
    keys = [k for _, k in columns]

    seen: set = set()
    exists = os.path.exists(master_path)
    if exists:
        with open(master_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            # Map the file's header back to record keys via the column headers.
            head_to_key = {h: k for (h, k) in columns}
            for row in reader:
                rec = {head_to_key.get(h, h): v for h, v in row.items()}
                seen.add(key_fn(rec))

    added = 0
    with open(master_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        for r in leads:
            k = key_fn(r)
            if k in seen:
                continue
            seen.add(k)
            w.writerow([r.get(col, "") for col in keys])
            added += 1
    return added


# ── Completion hook ───────────────────────────────────────────────────────────

def run_completion_hook(command: str, summary: dict) -> int:
    """Run a user-provided shell command on completion, piping `summary` as JSON
    on stdin. Returns the command's exit code; never raises (returns -1 on any
    failure to launch the command).

    SECURITY: this runs an ARBITRARY user-supplied command via the shell, by
    design — it is the user's own post-run hook (e.g. a Slack/webhook notifier).
    Only configure it with commands you trust.
    """
    if not command:
        return -1
    try:
        payload = json.dumps(summary, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        payload = "{}"
    try:
        proc = subprocess.run(
            command, shell=True, input=payload,
            text=True, encoding="utf-8",
        )
        return proc.returncode
    except Exception:
        return -1
