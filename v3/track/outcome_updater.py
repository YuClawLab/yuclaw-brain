"""
Compute forward outcomes for every snapshot in signal_snapshots.

For each (snapshot, horizon ∈ {1, 5, 20} trading days):
  price_at_signal  =  close on signal_date (or nearest prior trading day)
  price_at_signal+N =  close on the Nth trading day strictly after signal_date
  return_Nd        =  (price+N - price_at_signal) / price_at_signal
  spy_return_Nd    =  same calc over SPY
  excess_return_Nd =  return - spy_return
  hit_Nd           =  directional outcome (NULL for non-directional labels)

Idempotent: re-runs UPDATE the matured columns; NULLs remain NULL until the
+N-day close exists in price_history. Safe to cron daily.

CLI:
    python3 -m v3.track.outcome_updater
    python3 -m v3.track.outcome_updater --dry-run   # report counts only
    python3 -m v3.track.outcome_updater --ticker AAPL
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.sources.edgar_poll import DB_DSN

HORIZONS = (1, 5, 20)  # trading days forward
SPY_TICKER = "SPY"

# Public signal vocabulary mapped to a directional sign.
# +1 → expect price up    (hit if return > 0)
# -1 → expect price down  (hit if return < 0)
#  0 → non-directional    (hit_Nd = NULL)
LABEL_DIRECTION: dict[str, int] = {
    "STRONG_BUY":     +1,
    "BUY":            +1,
    "HOLD":            0,
    "WATCH":           0,  # WATCH is "we don't have conviction yet" — not directional
    "WEAKENING":      -1,
    "NEGATIVE_EVENT": -1,
    "DOWNSIDE_WATCH": -1,
}


def _load_price_history(conn) -> tuple[dict[str, list[tuple[date, float]]], dict[date, float]]:
    """Pull all price_history into memory once. Returns:
        ticker → ordered [(trade_date, close), ...]  (oldest first)
        spy_by_date → trade_date → close   (for fast SPY lookups)
    """
    by_ticker: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with conn.cursor() as cur:
        cur.execute("SELECT ticker, trade_date, close FROM price_history ORDER BY ticker, trade_date")
        for t, d, c in cur.fetchall():
            by_ticker[t].append((d, float(c)))
    spy_by_date = {d: c for (d, c) in by_ticker.get(SPY_TICKER, [])}
    return dict(by_ticker), spy_by_date


def _close_on_or_before(rows: list[tuple[date, float]], target: date) -> Optional[tuple[date, float]]:
    """Latest (trade_date, close) with trade_date <= target. None if none exist."""
    out: Optional[tuple[date, float]] = None
    for d, c in rows:
        if d <= target:
            out = (d, c)
        else:
            break
    return out


def _close_n_trading_days_after(rows: list[tuple[date, float]], target: date, n: int) -> Optional[tuple[date, float]]:
    """The Nth trading-day close strictly after target (date matches rows in price_history,
    which is itself trading-day-only). None if not yet matured."""
    # First trading row with date > target
    idx_first_after = None
    for i, (d, _) in enumerate(rows):
        if d > target:
            idx_first_after = i
            break
    if idx_first_after is None:
        return None
    target_idx = idx_first_after + (n - 1)
    if target_idx >= len(rows):
        return None
    return rows[target_idx]


def _hit(label: str, return_pct: float) -> Optional[bool]:
    """Directional hit; None for non-directional labels."""
    direction = LABEL_DIRECTION.get(label, 0)
    if direction == 0:
        return None
    if direction > 0:
        return return_pct > 0
    return return_pct < 0


def update_one(
    snap: dict[str, Any],
    ticker_rows: dict[str, list[tuple[date, float]]],
    spy_rows: list[tuple[date, float]],
) -> Optional[dict[str, Any]]:
    """Compute outcome row for one snapshot. Returns dict or None if no price."""
    ticker = snap["ticker"]
    sig_date: date = snap["signal_date"]
    label = snap["signal_label"]

    rows = ticker_rows.get(ticker, [])
    base = _close_on_or_before(rows, sig_date)
    if base is None:
        return None
    _, p0 = base
    spy_base = _close_on_or_before(spy_rows, sig_date)

    out: dict[str, Any] = {
        "snapshot_id": snap["snapshot_id"],
        "ticker": ticker,
        "signal_date": sig_date,
        "signal_label": label,
        "total_score": snap["total_score"],
        "is_backfill": snap["is_backfill"],
        "price_at_signal": p0,
    }

    for n in HORIZONS:
        fwd = _close_n_trading_days_after(rows, sig_date, n)
        spy_fwd = _close_n_trading_days_after(spy_rows, sig_date, n) if spy_base else None
        if fwd is None:
            out[f"return_{n}d"] = None
            out[f"spy_return_{n}d"] = None
            out[f"excess_return_{n}d"] = None
            out[f"hit_{n}d"] = None
            continue
        ret = (fwd[1] - p0) / p0
        out[f"return_{n}d"] = ret
        if spy_base and spy_fwd:
            spy_ret = (spy_fwd[1] - spy_base[1]) / spy_base[1]
            out[f"spy_return_{n}d"] = spy_ret
            out[f"excess_return_{n}d"] = ret - spy_ret
        else:
            out[f"spy_return_{n}d"] = None
            out[f"excess_return_{n}d"] = None
        out[f"hit_{n}d"] = _hit(label, ret)

    return out


def upsert(conn, row: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO track_record (
                snapshot_id, ticker, signal_date, signal_label, total_score, is_backfill,
                price_at_signal,
                return_1d,  return_5d,  return_20d,
                spy_return_1d,  spy_return_5d,  spy_return_20d,
                excess_return_1d, excess_return_5d, excess_return_20d,
                hit_1d, hit_5d, hit_20d
            ) VALUES (
                %(snapshot_id)s, %(ticker)s, %(signal_date)s, %(signal_label)s,
                %(total_score)s, %(is_backfill)s,
                %(price_at_signal)s,
                %(return_1d)s, %(return_5d)s, %(return_20d)s,
                %(spy_return_1d)s, %(spy_return_5d)s, %(spy_return_20d)s,
                %(excess_return_1d)s, %(excess_return_5d)s, %(excess_return_20d)s,
                %(hit_1d)s, %(hit_5d)s, %(hit_20d)s
            )
            ON CONFLICT (snapshot_id) DO UPDATE SET
                price_at_signal   = EXCLUDED.price_at_signal,
                return_1d         = EXCLUDED.return_1d,
                return_5d         = EXCLUDED.return_5d,
                return_20d        = EXCLUDED.return_20d,
                spy_return_1d     = EXCLUDED.spy_return_1d,
                spy_return_5d     = EXCLUDED.spy_return_5d,
                spy_return_20d    = EXCLUDED.spy_return_20d,
                excess_return_1d  = EXCLUDED.excess_return_1d,
                excess_return_5d  = EXCLUDED.excess_return_5d,
                excess_return_20d = EXCLUDED.excess_return_20d,
                hit_1d            = EXCLUDED.hit_1d,
                hit_5d            = EXCLUDED.hit_5d,
                hit_20d           = EXCLUDED.hit_20d,
                computed_at       = now()
            """,
            row,
        )


def run(ticker_filter: Optional[str], dry_run: bool) -> dict:
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    stats = {
        "snapshots": 0, "wrote": 0, "no_price": 0,
        "matured_1d": 0, "matured_5d": 0, "matured_20d": 0,
    }
    try:
        ticker_rows, _ = _load_price_history(conn)
        spy_rows = ticker_rows.get(SPY_TICKER, [])

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            params: list[Any] = []
            sql = """
                SELECT snapshot_id, ticker,
                       signal_time::date AS signal_date,
                       signal_label, total_score, is_backfill
                FROM signal_snapshots
            """
            if ticker_filter:
                sql += " WHERE ticker = %s"
                params.append(ticker_filter.upper())
            sql += " ORDER BY signal_time"
            cur.execute(sql, params)
            snaps = list(cur.fetchall())

        for snap in snaps:
            stats["snapshots"] += 1
            row = update_one(snap, ticker_rows, spy_rows)
            if row is None:
                stats["no_price"] += 1
                continue
            for n in HORIZONS:
                if row[f"return_{n}d"] is not None:
                    stats[f"matured_{n}d"] += 1
            if not dry_run:
                upsert(conn, row)
                stats["wrote"] += 1

        if not dry_run:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Forward outcome computation")
    p.add_argument("--ticker", help="single ticker (default: all)")
    p.add_argument("--dry-run", action="store_true", help="compute, do not write")
    args = p.parse_args(argv)

    stats = run(args.ticker, args.dry_run)
    print(f"[outcome_updater] {stats}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
