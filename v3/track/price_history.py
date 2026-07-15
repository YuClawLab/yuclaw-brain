"""
Populate the internal `price_history` table from yfinance.

Strictly internal — Yahoo terms forbid redistribution of raw OHLCV, so
this data is never exported in public output. Only derived metrics
(returns, hit-rates) reach users.

CLI:
    python3 -m v3.track.price_history --start 2026-02-01 --end 2026-05-20
    python3 -m v3.track.price_history ... --ticker AAPL
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import psycopg2

from v3.sources.edgar_poll import DB_DSN

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "universe.json"

# Tickers we want extra: SPY for benchmark, and a couple of macro ETFs.
ALWAYS_INCLUDE = {"SPY"}


def _all_tickers() -> list[str]:
    # Coverage, not eligibility: price history spans the scoring tier AND the
    # evidence-only tier (Canada Resources). Scoring stays gated separately in
    # v3/universe_tiers.scoring_universe().
    from v3.universe_tiers import coverage_universe
    return sorted(coverage_universe() | ALWAYS_INCLUDE)


def _fetch_one(ticker: str, start: date, end: date) -> list[tuple[str, date, float, int]]:
    """Pull daily closes via yfinance. Returns list of (ticker, date, close, volume).

    yfinance.download with multiple tickers gives a MultiIndex frame; we keep
    things simple by calling per-ticker (also gives clearer error reporting).
    """
    import yfinance as yf
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end.toordinal() - start.toordinal() and (end.toordinal() + 1)) and
            date.fromordinal(end.toordinal() + 1).isoformat(),
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if df is None or df.empty:
        return []
    # yfinance returns a multi-level column header when multiple tickers are
    # requested; flatten to the top level for our single-ticker call.
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.droplevel(axis=1, level=1)
    out: list[tuple[str, date, float, int]] = []
    for ts, row in df.iterrows():
        try:
            close = float(row["Close"])
            vol = int(row["Volume"]) if not (row["Volume"] != row["Volume"]) else 0  # NaN check
        except (KeyError, TypeError, ValueError):
            continue
        if close != close:  # NaN
            continue
        out.append((ticker, ts.date(), close, vol))
    return out


def populate(tickers: Iterable[str], start: date, end: date) -> dict:
    conn = psycopg2.connect(DB_DSN)
    stats = {"tickers": 0, "rows_inserted": 0, "rows_skipped": 0, "errors": 0}
    try:
        for t in tickers:
            try:
                rows = _fetch_one(t, start, end)
            except Exception as e:
                stats["errors"] += 1
                print(f"[price_history] {t}: yfinance ERROR {type(e).__name__}: {str(e)[:120]}",
                      file=sys.stderr, flush=True)
                continue
            if not rows:
                print(f"[price_history] {t}: 0 rows in window {start}..{end}", flush=True)
                continue
            with conn.cursor() as cur:
                for r in rows:
                    cur.execute(
                        """INSERT INTO price_history (ticker, trade_date, close, volume, source)
                           VALUES (%s, %s, %s, %s, 'yfinance')
                           ON CONFLICT (ticker, trade_date) DO UPDATE
                             SET close = EXCLUDED.close, volume = EXCLUDED.volume,
                                 source = EXCLUDED.source, fetched_at = now()""",
                        r,
                    )
            conn.commit()
            stats["tickers"] += 1
            stats["rows_inserted"] += len(rows)
            print(f"[price_history] {t}: {len(rows)} rows", flush=True)
    finally:
        conn.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Populate price_history from yfinance (internal use)")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--ticker", help="single ticker (default: universe + SPY)")
    args = p.parse_args(argv)

    try:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        print(f"invalid date", file=sys.stderr)
        return 2

    tickers = [args.ticker.upper()] if args.ticker else _all_tickers()
    print(f"[price_history] {len(tickers)} ticker(s), {start} → {end}", flush=True)
    stats = populate(tickers, start, end)
    print(f"[price_history] DONE: {stats}", flush=True)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
