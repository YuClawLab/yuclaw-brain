"""
Verified Research Ledger writer.

Once per day, this script:
  1. Pulls today's OOS signal_snapshots (is_backfill=false).
  2. Computes a content_hash per snapshot (using the same canonical
     function the writer used, in v3/proof/_hash.py).
  3. Wraps them in one daily block + daily_root, appends one JSON line
     to ~/yuclaw-trust/verified_research_ledger.jsonl.
  4. git-add / commit / push so the hashes land in the public repo
     before anyone can quietly mutate signal_snapshots.

Idempotent: if a block for today is already present, this exits cleanly
without re-appending or re-committing. The cron entry can re-fire
without making noise.

CLI:
    python3 -m v3.proof.ledger
    python3 -m v3.proof.ledger --date 2026-05-20   # backfill / dev mode
    python3 -m v3.proof.ledger --dry-run           # show, do not write
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.proof._hash import content_hash, daily_root
from v3.sources.edgar_poll import DB_DSN

LEDGER_REPO_DIR = Path(os.environ.get("YUCLAW_LEDGER_REPO",
                                      str(Path.home() / "yuclaw-trust")))
LEDGER_FILE = LEDGER_REPO_DIR / "verified_research_ledger.jsonl"

# Component column → component id mapping (matches signal_snapshots schema).
COMPONENT_COLS = {
    "c1": "c1_price_momentum",
    "c2": "c2_volume_confirm",
    "c3": "c3_sector_velocity",
    "c4": "c4_macro_regime",
    "c5": "c5_oil_rates_fx",
    "c6": "c6_event_impact",
    "c7": "c7_peer_correlation",
    "c8": "c8_cascade_effect",
    "c9": "c9_model_trust",
}


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


def _block_exists_for(date_str: str) -> bool:
    """Check the ledger jsonl for an existing entry on `date_str`."""
    if not LEDGER_FILE.exists():
        return False
    for line in LEDGER_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("date") == date_str:
            return True
    return False


def _fetch_snapshots_for(conn, date_str: str) -> list[dict[str, Any]]:
    """All OOS snapshots whose signal_time falls on `date_str` (UTC)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM signal_snapshots
               WHERE is_backfill = false
                 AND (signal_time AT TIME ZONE 'UTC')::date = %s
               ORDER BY ticker""",
            (date_str,),
        )
        return [dict(r) for r in cur.fetchall()]


def _entry_from_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    components = {cid: float(row[col]) if row[col] is not None else 0.0
                  for cid, col in COMPONENT_COLS.items()}
    ch = content_hash(row["snapshot_id"], float(row["total_score"]), components)
    return {
        "ticker": row["ticker"],
        "snapshot_id": row["snapshot_id"],
        "signal_label": row["signal_label"],
        "content_hash": ch,
    }


def build_block(conn, date_str: str) -> Optional[dict[str, Any]]:
    """Return the day's block as a dict, or None if nothing to record."""
    snaps = _fetch_snapshots_for(conn, date_str)
    if not snaps:
        return None
    entries = [_entry_from_snapshot(s) for s in snaps]
    root = daily_root([e["content_hash"] for e in entries])
    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_count": len(entries),
        "entries": entries,
        "daily_root": root,
    }


def append_block(block: dict[str, Any]) -> None:
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_FILE.open("a") as f:
        f.write(json.dumps(block, separators=(",", ":")) + "\n")


def commit_and_push(block: dict[str, Any]) -> tuple[bool, str]:
    """Commit + push the ledger repo. Returns (success, message)."""
    if not (LEDGER_REPO_DIR / ".git").exists():
        return False, f"{LEDGER_REPO_DIR} is not a git repo — skip push"

    add = _git(["add", str(LEDGER_FILE.relative_to(LEDGER_REPO_DIR))], LEDGER_REPO_DIR)
    if add.returncode != 0:
        return False, f"git add failed: {add.stderr.strip()[:200]}"

    msg = f"ledger: {block['date']} — {block['snapshot_count']} signals, root {block['daily_root'][:12]}"
    commit = _git(["commit", "-m", msg], LEDGER_REPO_DIR)
    if commit.returncode != 0:
        # "nothing to commit" is benign; surface otherwise.
        if "nothing to commit" in (commit.stdout + commit.stderr).lower():
            return True, "nothing to commit (already in tree)"
        return False, f"git commit failed: {commit.stderr.strip()[:200]}"

    push = _git(["push", "origin", "main"], LEDGER_REPO_DIR)
    if push.returncode != 0:
        return False, f"git push failed: {push.stderr.strip()[:200]}"
    return True, msg


def append_daily_block(date_str: Optional[str] = None, dry_run: bool = False) -> dict[str, Any]:
    """Public entry point — runs steps 1..4 and reports a single stats dict."""
    date_str = date_str or _today_iso()
    stats: dict[str, Any] = {"date": date_str, "appended": False, "pushed": False, "reason": None}

    if _block_exists_for(date_str) and not dry_run:
        stats["reason"] = "block already present (idempotent skip)"
        return stats

    with psycopg2.connect(DB_DSN) as conn:
        block = build_block(conn, date_str)
    if block is None:
        stats["reason"] = "no OOS snapshots for that date"
        return stats

    stats["snapshot_count"] = block["snapshot_count"]
    stats["daily_root"] = block["daily_root"]

    if dry_run:
        stats["reason"] = "dry-run — block built but not appended"
        stats["block_preview"] = {**block, "entries": block["entries"][:3]}
        return stats

    append_block(block)
    stats["appended"] = True
    ok, msg = commit_and_push(block)
    stats["pushed"] = ok
    stats["reason"] = msg
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Verified Research Ledger writer")
    p.add_argument("--date", help="YYYY-MM-DD (default: today UTC)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    stats = append_daily_block(date_str=args.date, dry_run=args.dry_run)
    print(f"[ledger] {stats}", flush=True)
    return 0 if stats.get("pushed") or args.dry_run or "already present" in (stats.get("reason") or "") else 1


if __name__ == "__main__":
    sys.exit(main())
