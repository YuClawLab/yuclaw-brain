"""
Verify a YUCLAW signal against the Verified Research Ledger.

For (ticker, date), look up the ledger entry, recompute the content_hash
from the current signal_snapshots row, and compare. Three outcomes:
  - VERIFIED: ledger entry exists, hash matches → signal unaltered.
  - INTEGRITY FAILURE: entry exists, hash differs → signal was edited
    after publication. (Or the canonical hash function changed.)
  - NOT FOUND: no entry for that (ticker, date) → either YUCLAW didn't
    publish a signal that day, or the ledger run hasn't fired yet.

Verifies record integrity and timing — not investment merit.

CLI is wired in v3/cli/verify.py; this file is the engine.
"""
from __future__ import annotations

import json
import subprocess
from datetime import date as _date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.proof._hash import content_hash
from v3.proof.ledger import COMPONENT_COLS, LEDGER_FILE, LEDGER_REPO_DIR
from v3.sources.edgar_poll import DB_DSN


def _read_ledger_entry(ticker: str, date_str: str) -> tuple[Optional[dict[str, Any]],
                                                             Optional[dict[str, Any]]]:
    """Returns (block_for_date, entry_for_ticker) or (None, None)."""
    if not LEDGER_FILE.exists():
        return None, None
    for line in LEDGER_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            block = json.loads(line)
        except json.JSONDecodeError:
            continue
        if block.get("date") != date_str:
            continue
        for entry in block.get("entries", []):
            if entry.get("ticker") == ticker.upper():
                return block, entry
        return block, None
    return None, None


def _fetch_snapshot_row(ticker: str, date_str: str) -> Optional[dict[str, Any]]:
    with psycopg2.connect(DB_DSN) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM signal_snapshots
               WHERE ticker = %s
                 AND is_backfill = false
                 AND (signal_time AT TIME ZONE 'UTC')::date = %s
               ORDER BY signal_time DESC LIMIT 1""",
            (ticker.upper(), date_str),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _git_commit_meta(commit_hash: Optional[str]) -> Optional[dict[str, str]]:
    """Get the timestamp + short hash of the git commit that introduced today's
    block. Best-effort — if the repo isn't accessible we just return None."""
    if not (LEDGER_REPO_DIR / ".git").exists() or not LEDGER_FILE.exists():
        return None
    rel = str(LEDGER_FILE.relative_to(LEDGER_REPO_DIR))
    log = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%h|%ci", "--", rel],
        cwd=str(LEDGER_REPO_DIR), capture_output=True, text=True, check=False,
    )
    if log.returncode != 0 or "|" not in log.stdout:
        return None
    short, when = log.stdout.split("|", 1)
    return {"commit": short.strip(), "committed_at": when.strip()}


def verify(ticker: str, date_str: str) -> dict[str, Any]:
    """Main entry. Returns a dict; the CLI formats it."""
    out: dict[str, Any] = {
        "ticker": ticker.upper(),
        "date": date_str,
        "status": "UNKNOWN",
        "note": "Verifies record integrity and timing — not investment merit.",
    }
    try:
        _date.fromisoformat(date_str)
    except ValueError:
        out["status"] = "INVALID_DATE"
        out["detail"] = f"date must be YYYY-MM-DD: {date_str!r}"
        return out

    block, entry = _read_ledger_entry(ticker, date_str)
    if block is None:
        out["status"] = "NOT_FOUND"
        out["detail"] = f"no ledger entry for {ticker.upper()} on {date_str} — the ledger run may not have fired yet"
        return out
    if entry is None:
        out["status"] = "NOT_FOUND"
        out["detail"] = f"ledger block exists for {date_str} but {ticker.upper()} is not in its entries"
        return out

    snap = _fetch_snapshot_row(ticker, date_str)
    if snap is None:
        out["status"] = "INTEGRITY_FAILURE"
        out["detail"] = (f"ledger says {ticker.upper()} had a snapshot on {date_str} "
                         f"but the database has no matching row — record removed?")
        return out

    components = {cid: float(snap[col]) if snap[col] is not None else 0.0
                  for cid, col in COMPONENT_COLS.items()}
    recomputed = content_hash(snap["snapshot_id"], float(snap["total_score"]), components)
    out["ledger_hash"] = entry["content_hash"]
    out["recomputed_hash"] = recomputed
    out["ledger_label"] = entry["signal_label"]
    out["current_label"] = snap["signal_label"]

    if recomputed != entry["content_hash"]:
        out["status"] = "INTEGRITY_FAILURE"
        out["detail"] = ("recomputed content_hash differs from the ledger record — "
                         "the snapshot was edited after publication")
        return out

    meta = _git_commit_meta(entry["content_hash"])
    out["status"] = "VERIFIED"
    out["commit"] = meta
    return out
