"""
`yuclaw watch` — manage the personal watchlist.

CLI:
    python3 -m v3.cli watch add NVDA
    python3 -m v3.cli watch remove NVDA
    python3 -m v3.cli watch list
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.profile.store import ProfileError, add_watch, load_profile, remove_watch
from v3.sources.edgar_poll import DB_DSN


def _latest_signal(ticker: str) -> Optional[dict[str, Any]]:
    """Most recent OOS snapshot for `ticker`. Returns None if no snapshot."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT signal_label, total_score, signal_time
                   FROM signal_snapshots
                   WHERE ticker = %s AND is_backfill = false
                   ORDER BY signal_time DESC
                   LIMIT 1""",
                (ticker,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _add(ticker: str) -> int:
    try:
        t = add_watch(ticker)
    except ProfileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"OK  added {t}")
    return 0


def _remove(ticker: str) -> int:
    try:
        t = remove_watch(ticker)
    except ProfileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"OK  removed {t}")
    return 0


COMPLIANCE_FOOTER = (
    "Research and education only. Not investment advice. "
    "Signal labels are research classifications, not buy/sell recommendations. "
    "YUCLAW is not a registered investment adviser."
)


def _list() -> int:
    prof = load_profile()
    wl = prof.get("watchlist") or []
    if not wl:
        print("(watchlist empty — `python3 -m v3.cli watch add TICKER` to add)")
        return 0
    print(f"watchlist ({len(wl)}):")
    for t in wl:
        row = _latest_signal(t)
        if row is None:
            print(f"  {t:<6s}  (no live snapshot yet)")
        else:
            label = row["signal_label"]
            score = row["total_score"]
            when = row["signal_time"].strftime("%Y-%m-%d")
            print(f"  {t:<6s}  {label:<15s}  score={score:+.3f}   as of {when}")
    print()
    print(COMPLIANCE_FOOTER)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw watch",
                                description="Manage personal watchlist")
    sub = p.add_subparsers(dest="cmd")
    add_p = sub.add_parser("add")
    add_p.add_argument("ticker")
    rm_p = sub.add_parser("remove")
    rm_p.add_argument("ticker")
    sub.add_parser("list")
    args = p.parse_args(argv)

    if args.cmd == "add":
        return _add(args.ticker)
    if args.cmd == "remove":
        return _remove(args.ticker)
    if args.cmd in (None, "list"):
        return _list()
    return 2


if __name__ == "__main__":
    sys.exit(main())
