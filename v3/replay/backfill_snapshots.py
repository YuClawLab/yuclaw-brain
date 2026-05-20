"""
Generate a series of in-sample replay snapshots — Wednesdays from
2026-02-18 through 2026-05-13 (inclusive), one row per (ticker, date).

This is the data foundation for the in-sample BACKTEST RESULTS panel.
We pick Wednesdays because they sit in the middle of the trading week
and are unlikely to be holidays; alternative cadences (daily, weekly
Friday) are easy swaps via constants.

Each call delegates to v3.replay.engine.replay() — same path the live
`yuclaw replay` CLI uses — so leak-audit guarantees apply equally here.

CLI:
    python3 -m v3.replay.backfill_snapshots
    python3 -m v3.replay.backfill_snapshots --ticker AAPL    # single
    python3 -m v3.replay.backfill_snapshots --weekday FRI    # different cadence
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Iterable

from v3.replay.engine import replay

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "universe.json"

DEFAULT_START = date(2026, 2, 18)
DEFAULT_END = date(2026, 5, 13)
WEEKDAY_MAP = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4}


def _load_universe() -> list[str]:
    u = json.loads(UNIVERSE_PATH.read_text())
    return sorted(set(u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"]))


def _weekly_dates(start: date, end: date, weekday: int) -> list[date]:
    """Every `weekday` in [start, end] inclusive."""
    out: list[date] = []
    d = start
    # Walk forward to first matching weekday
    while d <= end and d.weekday() != weekday:
        d += timedelta(days=1)
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def run(tickers: Iterable[str], dates: list[date]) -> dict:
    stats = {"calls": 0, "ok": 0, "errors": 0, "by_label": {}}
    total = sum(1 for _ in tickers)
    # tickers may have been a generator; rebuild a list
    tickers = list(tickers) if not isinstance(tickers, list) else tickers
    total = len(tickers) * len(dates)
    print(f"[backfill_snapshots] {len(tickers)} tickers × {len(dates)} dates = {total} replays",
          flush=True)
    t0 = time.time()
    for i, d in enumerate(dates, 1):
        as_of = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        ok_on_date = 0
        for t in tickers:
            stats["calls"] += 1
            try:
                r = replay(t, as_of)
                stats["ok"] += 1
                ok_on_date += 1
                label = r["label"]
                stats["by_label"][label] = stats["by_label"].get(label, 0) + 1
            except Exception as e:
                stats["errors"] += 1
                print(f"[backfill_snapshots] {t} @ {d}: ERROR {type(e).__name__}: {str(e)[:120]}",
                      file=sys.stderr, flush=True)
        elapsed = time.time() - t0
        rate = stats["calls"] / max(elapsed, 1e-3)
        print(f"[backfill_snapshots] date {i}/{len(dates)} {d}: {ok_on_date}/{len(tickers)} ok  "
              f"(cumulative {stats['ok']}/{stats['calls']}, {rate:.1f} replays/s)",
              flush=True)
    print(f"[backfill_snapshots] DONE: {stats}", flush=True)
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="In-sample weekly replay backfill")
    p.add_argument("--start", help="YYYY-MM-DD (default 2026-02-18)")
    p.add_argument("--end", help="YYYY-MM-DD (default 2026-05-13)")
    p.add_argument("--ticker", help="single ticker (default: universe)")
    p.add_argument("--weekday", choices=sorted(WEEKDAY_MAP), default="WED")
    args = p.parse_args(argv)

    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else DEFAULT_START
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else DEFAULT_END
    dates = _weekly_dates(start, end, WEEKDAY_MAP[args.weekday])
    if not dates:
        print(f"no {args.weekday} dates in {start}..{end}", file=sys.stderr)
        return 2

    tickers = [args.ticker.upper()] if args.ticker else _load_universe()
    stats = run(tickers, dates)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
