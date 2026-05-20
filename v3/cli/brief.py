"""
`yuclaw brief` — personalized daily digest.

Pulls each watchlist ticker's latest OOS snapshot and prints a compact
summary, plus the single most material recent event for that ticker.
With an empty watchlist, falls back to the universe-wide top-N absolute-
score movers and shows a hint to add tickers.

Public vocabulary only: STRONG_BUY / BUY / HOLD / WATCH / WEAKENING /
NEGATIVE_EVENT / DOWNSIDE_WATCH / RISK_ALERT. No SELL/SHORT anywhere.

CLI:
    python3 -m v3.cli brief
    python3 -m v3.cli brief --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.profile.store import load_profile
from v3.signal.data_loader import get_macro_regime, load_v2_state
from v3.sources.edgar_poll import DB_DSN

COMPLIANCE_FOOTER = (
    "Research and education only. Not investment advice. YUCLAW is "
    "not a registered investment adviser. Signal labels are research "
    "classifications, not buy/sell recommendations."
)


def _latest_snapshots(tickers: list[str]) -> list[dict[str, Any]]:
    """Most recent OOS snapshot per ticker. Skips tickers with no live row."""
    if not tickers:
        return []
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker)
                       ticker, signal_label, total_score, signal_time
                   FROM signal_snapshots
                   WHERE ticker = ANY(%s) AND is_backfill = false
                   ORDER BY ticker, signal_time DESC""",
                (tickers,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _top_movers(limit: int) -> list[dict[str, Any]]:
    """Top-N OOS snapshots by absolute composite score, latest per ticker."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker)
                       ticker, signal_label, total_score, signal_time
                   FROM signal_snapshots
                   WHERE is_backfill = false
                   ORDER BY ticker, signal_time DESC""",
            )
            rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    rows.sort(key=lambda r: abs(float(r["total_score"])), reverse=True)
    return rows[:limit]


def _top_evidence(ticker: str, as_of: datetime) -> Optional[dict[str, Any]]:
    """One-line summary of the most material recent event (7-day window)."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT event_type, magnitude, direction, available_as_of,
                          raw_excerpt
                   FROM events
                   WHERE ticker = %s
                     AND event_status = 'accepted'
                     AND available_as_of <= %s
                     AND available_as_of > %s - INTERVAL '7 days'
                   ORDER BY magnitude * llm_confidence DESC
                   LIMIT 1""",
                (ticker, as_of, as_of),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def _format_row(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    when = row["signal_time"].strftime("%Y-%m-%d")
    lines.append(f"  {row['ticker']:<6s}  {row['signal_label']:<15s}  "
                 f"score={row['total_score']:+.3f}   as of {when}")
    ev = _top_evidence(row["ticker"], row["signal_time"])
    if ev:
        ev_date = ev["available_as_of"].strftime("%Y-%m-%d")
        direction_word = "↑" if ev.get("direction", 0) > 0 else ("↓" if ev.get("direction", 0) < 0 else "·")
        excerpt = (ev.get("raw_excerpt") or "").replace("\n", " ")[:90]
        lines.append(f"          top evidence: {direction_word} {ev_date}  "
                     f"{ev['event_type']} — {excerpt}")
    return lines


def render(prof: dict[str, Any]) -> str:
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: list[str] = [f"YUCLAW BRIEF — {today_iso}"]

    # Macro regime header (cheap, from v2.3.0 cache)
    try:
        macro = get_macro_regime(load_v2_state())
        out.append(f"Regime: {macro['regime']} ({int(round(macro['confidence']*100))}%)")
    except Exception:
        out.append("Regime: (unavailable — dashboard state missing)")
    out.append("")

    watchlist = prof.get("watchlist") or []
    if watchlist:
        rows = _latest_snapshots(watchlist)
        present = {r["ticker"] for r in rows}
        missing = [t for t in watchlist if t not in present]
        out.append(f"Watchlist ({len(watchlist)} ticker{'s' if len(watchlist) != 1 else ''}):")
        # Preserve user's order for the present ones
        rows_by_ticker = {r["ticker"]: r for r in rows}
        for t in watchlist:
            r = rows_by_ticker.get(t)
            if r is None:
                out.append(f"  {t:<6s}  (no live snapshot yet — run `python3 -m v3.signal.snapshot_writer`)")
                continue
            out.extend(_format_row(r))
    else:
        top_n = (prof.get("display") or {}).get("top_n", 10)
        movers = _top_movers(top_n)
        out.append(
            f"(watchlist empty — showing top {len(movers)} universe movers by |score|. "
            f"Add tickers with `python3 -m v3.cli watch add TICKER`.)"
        )
        out.append("")
        for r in movers:
            out.extend(_format_row(r))

    out.append("")
    out.append(COMPLIANCE_FOOTER)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw brief",
                                description="Personalized daily brief")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    prof = load_profile()
    if args.json:
        watchlist = prof.get("watchlist") or []
        rows = _latest_snapshots(watchlist) if watchlist \
            else _top_movers((prof.get("display") or {}).get("top_n", 10))
        out = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "watchlist_mode": bool(watchlist),
            "rows": rows,
            "compliance_footer": COMPLIANCE_FOOTER,
        }
        print(json.dumps(out, indent=2, default=str))
    else:
        print(render(prof))
    return 0


if __name__ == "__main__":
    sys.exit(main())
