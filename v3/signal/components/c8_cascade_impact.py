"""
C8 — cascade impact.

Reads cascade child events (parent_event_id IS NOT NULL) for this ticker in
the last 7 days and aggregates them. Distinct from C6, which counts the
ticker's own primary events. C8 captures derived/downstream impact —
"someone upstream had a shock, here's the inferred knock-on".

For each cascade event on `ticker`:
    impact = direction × magnitude × llm_confidence × recency_decay

Sum impacts → tanh squash to [-1, 1].

Recency: 7-day half-life (faster than C6's 7d, since cascades are
already discounted by hop decay — we want freshness above all).

Confidence: clip(n_cascade_events / 3, 0.1, 1.0). The clip floor of 0.1
keeps C8 from completely dropping out when only one cascade lands.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from v3.signal.base import ComponentResult, SignalComponent
from v3.sources.edgar_poll import DB_DSN

CASCADE_LOOKBACK_DAYS = 7
HALF_LIFE_DAYS = 3.5
LN2 = math.log(2.0)


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _fetch_cascade_events(ticker: str, as_of: datetime) -> list[dict[str, Any]]:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT event_id, parent_event_id, ticker, event_type,
                          magnitude, direction, available_as_of, llm_confidence,
                          cascade_depth, raw_excerpt
                   FROM events
                   WHERE ticker = %s
                     AND parent_event_id IS NOT NULL
                     AND event_status = 'accepted'
                     AND available_as_of <= %s
                     AND available_as_of >= %s - (%s || ' days')::interval
                   ORDER BY available_as_of DESC""",
                (ticker.upper(), as_of, as_of, str(CASCADE_LOOKBACK_DAYS)),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


class C8CascadeEffect(SignalComponent):
    component_id = "c8"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        rows = _fetch_cascade_events(ticker, as_of)
        if not rows:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale="no cascade events in 7d window",
                details={"n_cascade_events": 0},
            )

        as_of_utc = _ensure_aware(as_of)
        total = 0.0
        contributors = []
        for ev in rows:
            age_days = max(0.0, (as_of_utc - _ensure_aware(ev["available_as_of"])).total_seconds() / 86400.0)
            recency = math.exp(-LN2 * age_days / HALF_LIFE_DAYS)
            impact = (int(ev["direction"]) * float(ev["magnitude"])
                      * float(ev["llm_confidence"] or 0.0) * recency)
            total += impact
            contributors.append({
                "event_id": ev["event_id"],
                "parent_event_id": ev["parent_event_id"],
                "depth": ev["cascade_depth"],
                "age_days": round(age_days, 2),
                "impact": round(impact, 4),
            })

        s = math.tanh(total)
        n = len(rows)
        conf = max(0.1, min(1.0, n / 3.0))
        top = sorted(contributors, key=lambda c: abs(c["impact"]), reverse=True)[:5]
        all_event_ids = [c["event_id"] for c in contributors if c.get("event_id")]
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=conf,
            rationale=(f"{n} cascade event(s) → impact sum {total:+.3f} → "
                       f"tanh {s:+.3f}"),
            details={
                "n_cascade_events": n,
                "raw_impact_sum": round(total, 4),
                "top_cascades": top,
                "inputs": {"event_ids": all_event_ids},
            },
        )
