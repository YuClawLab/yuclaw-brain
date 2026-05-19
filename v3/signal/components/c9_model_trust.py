"""
C9 — model trust.

Reads the track_record table for this ticker's recent realized outcomes and
modulates the composite by hit-rate. A model with a strong track record on
this ticker earns confident multiplier; a model that's been wrong recently
gets damped.

For v3.0 launch (and any window where track_record is empty for `ticker`),
C9 returns:
    score = 0.0
    confidence = 0.5   # neutral — composite still uses C9's slot but
                       # doesn't over-trust or over-distrust

Once track_record fills (Day 6+ when we run the live snapshotter long
enough to evaluate forward returns), the rule becomes:

    hit_rate = (# correct sign predictions / n_records, last 30 records)
    score    = (hit_rate - 0.5) * 2.0     # 50% hit → 0, 100% → +1, 0% → -1
    confidence = clip(n_records / 30, 0.3, 1.0)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras

from v3.signal.base import ComponentResult, SignalComponent
from v3.sources.edgar_poll import DB_DSN

TRACK_RECORD_WINDOW = 30   # rolling window of recent records
TRACK_RECORD_MIN_FOR_FULL_CONF = 30


def _fetch_recent_records(ticker: str, as_of: datetime, limit: int) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT total_score, forward_return, outcome_status
                   FROM track_record
                   WHERE ticker = %s
                     AND signal_time <= %s
                     AND outcome_status IS NOT NULL
                   ORDER BY signal_time DESC
                   LIMIT %s""",
                (ticker.upper(), as_of, limit),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


class C9ModelTrust(SignalComponent):
    component_id = "c9"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        rows = _fetch_recent_records(ticker, as_of, TRACK_RECORD_WINDOW)

        if not rows:
            # Default neutral until we have outcomes — composite still sees a
            # real slot, just at 0.5 confidence. (Not stubbed: this is the
            # *real* C9 contract for the cold-start window.)
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.5,
                rationale="track_record empty (cold start) — neutral",
                details={"n_records": 0},
            )

        correct = 0
        for r in rows:
            score = float(r["total_score"] or 0.0)
            fwd = float(r["forward_return"] or 0.0)
            if score == 0.0:
                continue
            if (score > 0) == (fwd > 0):
                correct += 1
        evaluable = sum(1 for r in rows if float(r["total_score"] or 0.0) != 0.0)
        if evaluable == 0:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.3,
                rationale="track_record has no non-zero scores yet",
                details={"n_records": len(rows), "n_evaluable": 0},
            )

        hit_rate = correct / evaluable
        s = (hit_rate - 0.5) * 2.0
        conf = max(0.3, min(1.0, evaluable / TRACK_RECORD_MIN_FOR_FULL_CONF))
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=conf,
            rationale=f"hit rate {correct}/{evaluable} = {hit_rate:.1%} → score {s:+.3f}",
            details={
                "n_records": len(rows),
                "n_evaluable": evaluable,
                "hit_rate": hit_rate,
            },
        )
