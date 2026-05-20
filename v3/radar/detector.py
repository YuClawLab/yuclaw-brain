"""
Detect material changes in OOS signal snapshots.

For each ticker, compare its two most-recent `is_backfill=false` snapshots:
  - Label flip (any old_label → new_label different): always a change.
  - |Δ total_score| >= profile.alert_threshold: change.

Tickers with only one OOS snapshot yet (history not yet deep enough)
are silently skipped. This is the expected state on Day 0.

Each change event carries a one-line `top_evidence` — the highest
magnitude × confidence event for that ticker in the past 7 days
prior to the *new* snapshot's signal_time. Cascade children are
allowed (they're real evidence).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.profile.store import load_profile
from v3.sources.edgar_poll import DB_DSN


@dataclass
class ChangeEvent:
    ticker: str
    old_label: str
    new_label: str
    old_score: float
    new_score: float
    old_signal_time: datetime
    new_signal_time: datetime
    delta_score: float
    reason: str  # "label_change" | "score_delta" | "both"
    top_evidence: Optional[str] = None  # human-readable one-liner

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_pairs(conn) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """For each ticker with >=2 OOS snapshots, return (older, newer) pair."""
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            WITH ranked AS (
                SELECT ticker, signal_label, total_score, signal_time, snapshot_id,
                       row_number() OVER (PARTITION BY ticker ORDER BY signal_time DESC) AS rn
                FROM signal_snapshots
                WHERE is_backfill = false
            )
            SELECT ticker, signal_label, total_score, signal_time, snapshot_id, rn
            FROM ranked
            WHERE rn <= 2
            ORDER BY ticker, rn
        """)
        rows = list(cur.fetchall())
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_ticker.setdefault(r["ticker"], []).append(dict(r))
    for t, lst in by_ticker.items():
        if len(lst) == 2:
            newer, older = lst[0], lst[1]  # rn 1 is newer
            pairs.append((older, newer))
    return pairs


def _top_evidence(conn, ticker: str, as_of: datetime) -> Optional[str]:
    """One-line summary of the highest magnitude*confidence event in the 7d
    window before `as_of`. Returns None if no events."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT event_type, direction, available_as_of, raw_excerpt
            FROM events
            WHERE ticker = %s
              AND event_status = 'accepted'
              AND available_as_of <= %s
              AND available_as_of > %s - INTERVAL '7 days'
            ORDER BY magnitude * llm_confidence DESC
            LIMIT 1
        """, (ticker, as_of, as_of))
        row = cur.fetchone()
    if not row:
        return None
    arrow = "↑" if (row["direction"] or 0) > 0 else ("↓" if (row["direction"] or 0) < 0 else "·")
    dstr = row["available_as_of"].strftime("%Y-%m-%d")
    excerpt = (row["raw_excerpt"] or "").replace("\n", " ")[:90]
    return f"{arrow} {dstr} {row['event_type']} — {excerpt}"


def detect_changes(conn=None, threshold: Optional[float] = None) -> list[ChangeEvent]:
    """Find material changes across the latest OOS pairs.

    `threshold` defaults to profile.alert_threshold; pass an explicit value
    to override (used by tests).
    """
    if threshold is None:
        prof = load_profile()
        threshold = float(prof.get("alert_threshold", 0.15))

    own_conn = False
    if conn is None:
        conn = psycopg2.connect(DB_DSN)
        own_conn = True
    try:
        pairs = _fetch_pairs(conn)
        out: list[ChangeEvent] = []
        for older, newer in pairs:
            label_changed = older["signal_label"] != newer["signal_label"]
            delta = float(newer["total_score"]) - float(older["total_score"])
            score_changed = abs(delta) >= threshold
            if not (label_changed or score_changed):
                continue
            reason = "both" if (label_changed and score_changed) \
                else ("label_change" if label_changed else "score_delta")
            evidence = _top_evidence(conn, newer["ticker"], newer["signal_time"])
            out.append(ChangeEvent(
                ticker=newer["ticker"],
                old_label=older["signal_label"],
                new_label=newer["signal_label"],
                old_score=float(older["total_score"]),
                new_score=float(newer["total_score"]),
                old_signal_time=older["signal_time"],
                new_signal_time=newer["signal_time"],
                delta_score=delta,
                reason=reason,
                top_evidence=evidence,
            ))
        # Stable order: biggest absolute delta first
        out.sort(key=lambda e: abs(e.delta_score), reverse=True)
        return out
    finally:
        if own_conn:
            conn.close()
