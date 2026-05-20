"""
`yuclaw replay TICKER --date YYYY-MM-DD` — recompute a signal as if it were
that date, using only data that was available at the time.

Reuses the rendering path from `yuclaw why` so the output format is
identical and the two commands stay in lockstep. Adds a header explaining
that this is a replay and (when applicable) a look-ahead-bias warning
about the LLM training cutoff.

CLI:
    python3 -m v3.cli replay AMD --date 2026-04-15
    python3 -m v3.cli replay AMD --date 2026-04-15 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.cli.why import (
    COMPONENT_COLS,
    COMPONENT_NAMES,
    _fetch_top_events,
    render_text,
)
from v3.replay.engine import replay
from v3.signal.base import COMPONENT_WEIGHTS
from v3.sources.edgar_poll import DB_DSN


def _result_to_snapshot_row(result: dict[str, Any]) -> dict[str, Any]:
    """Adapt compose_at()'s nested result into the flat snapshot shape that
    `render_text` (from why.py) expects. Same column names as
    signal_snapshots so the renderer doesn't know it's looking at an
    in-memory value instead of a DB row.
    """
    comps = result["components"]
    row: dict[str, Any] = {
        "ticker": result["ticker"],
        "signal_label": result["label"],
        "total_score": result["total_score"],
        "signal_time": datetime.fromisoformat(result["as_of"]),
    }
    for cid, col in COMPONENT_COLS.items():
        row[col] = comps[cid]["score"]
    return row


def _evidence_event_ids(result: dict[str, Any]) -> list[str]:
    """Collect the full event_id set that fed C6 + C8 in this replay."""
    ids: list[str] = []
    for cid in ("c6", "c8"):
        details = (result["components"].get(cid) or {}).get("details") or {}
        inputs = details.get("inputs") or {}
        ids.extend(inputs.get("event_ids") or [])
    seen = set()
    return [x for x in ids if not (x in seen or seen.add(x))]


def _replay_header(ticker: str, as_of: datetime, meta: dict[str, Any]) -> str:
    lines = [
        f"TIME MACHINE REPLAY: {ticker} as of {as_of.strftime('%Y-%m-%d')}",
        "(signal computed using only data available before this timestamp)",
    ]
    if meta.get("in_llm_training_window"):
        lines.append("")
        lines.append("⚠ " + meta["note"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw replay",
                                description="Recompute a signal as of a past date")
    p.add_argument("ticker", help="ticker (e.g. NVDA, AMD)")
    p.add_argument("--date", required=True,
                   help="point-in-time date YYYY-MM-DD (interpreted as 23:59:59 UTC)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    try:
        d = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"invalid --date: {args.date}", file=sys.stderr)
        return 2
    as_of = d.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)

    result = replay(args.ticker.upper(), as_of)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(_replay_header(args.ticker.upper(), as_of, result["replay_metadata"]))

    snap_row = _result_to_snapshot_row(result)
    event_ids = _evidence_event_ids(result)
    events = _fetch_top_events(args.ticker.upper(), event_ids, as_of)

    print(render_text(snap_row, events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
