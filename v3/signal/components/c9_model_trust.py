"""
C9 — model trust.

Reads the `track_record` table for this ticker's recent realized outcomes
and modulates the composite by hit-rate at the 5-day horizon.

Day-7 schema in use (Day-13c fix — previous version queried columns from
an older draft schema and silently failed via compose_at's try/except):

    track_record.signal_date   DATE
    track_record.return_5d     REAL    (raw forward return at +5 trading days)
    track_record.hit_5d        BOOLEAN (direction match; NULL for NEUTRAL/WATCH)

Logic:
  - If no matured directional rows: cold-start. score=0, confidence=0.5
    (neutral; preserves the cold-start contribution to the composite
    denominator instead of silently dropping out).
  - If >=1 matured directional row in the last TRACK_RECORD_WINDOW
    snapshots: hit_rate = correct / evaluable; score = (hit_rate - 0.5) * 2.
    confidence = clip(n_evaluable / TRACK_RECORD_MIN_FOR_FULL_CONF, 0.3, 1.0).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from v3.signal.base import ComponentResult, SignalComponent
from v3.sources.edgar_poll import DB_DSN

TRACK_RECORD_WINDOW = 30                # rolling window of recent records
TRACK_RECORD_MIN_FOR_FULL_CONF = 30


def _fetch_recent_records(ticker: str, as_of: datetime, limit: int) -> list[dict[str, Any]]:
    """Pull matured directional rows for this ticker, newest-first."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT total_score, return_5d, hit_5d
                   FROM track_record
                   WHERE ticker = %s
                     AND signal_date <= %s
                     AND hit_5d IS NOT NULL
                     AND return_5d IS NOT NULL
                   ORDER BY signal_date DESC
                   LIMIT %s""",
                (ticker.upper(), as_of.date(), limit),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


class C9ModelTrust(SignalComponent):
    component_id = "c9"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        rows = _fetch_recent_records(ticker, as_of, TRACK_RECORD_WINDOW)

        if not rows:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.5,
                rationale="track_record has no matured directional rows yet "
                          "(cold start) — neutral",
                details={"n_evaluable": 0},
            )

        correct = sum(1 for r in rows if r["hit_5d"] is True)
        evaluable = len(rows)
        hit_rate = correct / evaluable
        s = (hit_rate - 0.5) * 2.0
        conf = max(0.3, min(1.0, evaluable / TRACK_RECORD_MIN_FOR_FULL_CONF))
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=conf,
            rationale=f"hit rate {correct}/{evaluable} = {hit_rate:.1%} → score {s:+.3f}",
            details={
                "n_evaluable": evaluable,
                "n_correct": correct,
                "hit_rate_5d": hit_rate,
                "window": TRACK_RECORD_WINDOW,
            },
        )
