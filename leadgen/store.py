"""
Run store — persist each pipeline run (its meta + the leads it produced) to a
local SQLite file so the GUI/CLI can list past runs and re-open results.

Stdlib only (sqlite3 + json). Leads are stored as a JSON blob; meta is stored as
JSON too, with a few columns lifted out (vertical/market/total/when) for cheap
listing. A fresh connection is opened per call so concurrent callers never share
a connection (SQLite's own file locking handles serialization), and the
timestamp is injectable so tests don't depend on real wall-clock time.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    when_ts   TEXT NOT NULL,
    vertical  TEXT,
    market    TEXT,
    total     INTEGER NOT NULL DEFAULT 0,
    meta      TEXT NOT NULL,
    leads     TEXT NOT NULL
);
"""


def _default_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """SQLite-backed store of pipeline runs.

    db_path: path to the SQLite file (created on first use). Use ":memory:" only
             within a single connection — not useful here since each call opens a
             fresh connection; pass a real file path.
    now:     zero-arg callable returning the timestamp string for a run. Injected
             so tests are deterministic; defaults to UTC ISO-8601 now().
    """

    def __init__(self, db_path, *, now=_default_now):
        self.db_path = str(db_path)
        self._now = now
        con = self._connect()
        try:
            con.executescript(_SCHEMA)
            con.commit()
        finally:
            con.close()

    def _connect(self) -> sqlite3.Connection:
        # Fresh connection per call — never share across threads/calls. Callers
        # MUST close it (we close explicitly rather than rely on `with`, since
        # sqlite3's context manager commits but never closes the handle — on
        # Windows a lingering handle keeps the db file locked).
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def save_run(self, meta: dict, leads: list) -> int:
        """Persist one run; returns its new run_id.

        meta may carry "vertical"/"market" (lifted into columns for listing);
        "total" defaults to len(leads). A "when" key in meta, if present, wins
        over the injected clock so callers can record an explicit timestamp.
        """
        meta = dict(meta or {})
        leads = list(leads or [])
        when = meta.get("when") or self._now()
        total = meta.get("total", len(leads))
        con = self._connect()
        try:
            cur = con.execute(
                "INSERT INTO runs (when_ts, vertical, market, total, meta, leads) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (when, meta.get("vertical"), meta.get("market"), int(total),
                 json.dumps(meta), json.dumps(leads)),
            )
            con.commit()
            return int(cur.lastrowid)
        finally:
            con.close()

    def list_runs(self) -> list:
        """Lightweight listing (newest first): id, when, vertical, market, total."""
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT id, when_ts, vertical, market, total "
                "FROM runs ORDER BY id DESC"
            ).fetchall()
        finally:
            con.close()
        return [{"id": r["id"], "when": r["when_ts"], "vertical": r["vertical"],
                 "market": r["market"], "total": r["total"]} for r in rows]

    def get_run(self, run_id: int) -> dict | None:
        """Full run: {meta, leads}. None if the id doesn't exist."""
        con = self._connect()
        try:
            row = con.execute(
                "SELECT meta, leads FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return None
        return {"meta": json.loads(row["meta"]), "leads": json.loads(row["leads"])}
