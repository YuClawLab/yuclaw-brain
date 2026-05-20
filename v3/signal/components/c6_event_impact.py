"""
C6 — event impact (v3.0 differentiator).

Aggregates all accepted events for `ticker` within the lookback window,
weighted by recency-decay × magnitude × direction × per-event confidence.

For each event:
    recency_w = exp(-ln(2) * age_days / HALF_LIFE_DAYS)
    impact    = direction * magnitude * llm_confidence * recency_w

Sum impacts → tanh squash into [-1, 1]. tanh keeps the score bounded even
when many events stack up.

Component confidence:
    confidence = min(1.0, n_events_in_window / CONFIDENCE_FULL_N)
    (0.0 if no events — C6 self-masks out of composite denominator.)
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.data_loader import fetch_events

HALF_LIFE_DAYS = 7.0          # event halves in weight every 7 days
CONFIDENCE_FULL_N = 5         # 5+ events in window → full confidence
LN2 = math.log(2.0)


def _ensure_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC (Postgres timestamps are tz-aware)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class C6EventImpact(SignalComponent):
    component_id = "c6"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        events = ctx.get("events")
        if events is None:
            events = fetch_events(ticker, as_of)

        if not events:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale="no events in lookback window",
                details={"n_events": 0, "lookback_days": 30},
            )

        as_of_utc = _ensure_aware(as_of)

        total_impact = 0.0
        contributors = []
        for ev in events:
            avail = _ensure_aware(ev["available_as_of"])
            age_days = max(0.0, (as_of_utc - avail).total_seconds() / 86400.0)
            recency_w = math.exp(-LN2 * age_days / HALF_LIFE_DAYS)
            mag = float(ev.get("magnitude") or 0.0)
            direction = int(ev.get("direction") or 0)
            ev_conf = float(ev.get("llm_confidence") or 0.0)
            impact = direction * mag * ev_conf * recency_w
            total_impact += impact
            contributors.append({
                "event_id": ev.get("event_id"),
                "type": ev.get("event_type"),
                "age_days": round(age_days, 2),
                "magnitude": mag,
                "direction": direction,
                "confidence": ev_conf,
                "impact": round(impact, 4),
            })

        s = math.tanh(total_impact)
        n = len(events)
        comp_conf = min(1.0, n / CONFIDENCE_FULL_N)

        # Cap contributors detail at top-5 by absolute impact for `yuclaw why`.
        top5 = sorted(contributors, key=lambda c: abs(c["impact"]), reverse=True)[:5]
        # event_ids is the FULL list of inputs (needed by the replay leak audit
        # and by snapshot_writer's evidence trail; top_contributors is the
        # truncated display version).
        all_event_ids = [c["event_id"] for c in contributors if c.get("event_id")]
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=comp_conf,
            rationale=f"{n} event(s) in 30d → impact sum {total_impact:+.3f} → tanh {s:+.3f}",
            details={
                "n_events": n,
                "raw_impact_sum": round(total_impact, 4),
                "top_contributors": top5,
                "inputs": {"event_ids": all_event_ids},
            },
        )
