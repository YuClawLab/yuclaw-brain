"""
C6 — event impact (v3.0 differentiator).

Aggregates all accepted events for `ticker` within the lookback window,
weighted by recency-decay × magnitude × direction × per-event confidence.

For each event:
    recency_w = exp(-ln(2) * age_days / HALF_LIFE_DAYS)
    impact    = direction * magnitude * llm_confidence * recency_w

Day 13c addition: the COLLECTIVE signed insider-event impact is clamped
to ±INSIDER_AGGREGATE_CAP (0.5) before being summed with non-insider
events. Without the cap, a single Form 4 cluster (e.g. AMD's 24 CEO
sells in a week) could saturate C6 to ±1.0 and drown out a single
8-K earnings beat — multi-collinear with the underlying insider
narrative is fine but it shouldn't dominate the evidence story.

  raw_insider_impact   = sum(impact_i for events of type INSIDER_BUY/SELL)
  capped_insider_impact = clamp(raw_insider_impact, -CAP, +CAP)
  other_impact         = sum(impact_i for non-insider events)
  total_impact         = capped_insider_impact + other_impact
  score                = tanh(total_impact)

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
INSIDER_AGGREGATE_CAP = 0.5   # collective |insider sum| clamped before tanh
INSIDER_EVENT_TYPES = frozenset(("INSIDER_BUY", "INSIDER_SELL"))


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

        insider_impact_sum = 0.0
        other_impact_sum = 0.0
        contributors = []
        for ev in events:
            avail = _ensure_aware(ev["available_as_of"])
            age_days = max(0.0, (as_of_utc - avail).total_seconds() / 86400.0)
            recency_w = math.exp(-LN2 * age_days / HALF_LIFE_DAYS)
            mag = float(ev.get("magnitude") or 0.0)
            direction = int(ev.get("direction") or 0)
            ev_conf = float(ev.get("llm_confidence") or 0.0)
            impact = direction * mag * ev_conf * recency_w
            etype = ev.get("event_type")
            is_insider = etype in INSIDER_EVENT_TYPES
            if is_insider:
                insider_impact_sum += impact
            else:
                other_impact_sum += impact
            contributors.append({
                "event_id": ev.get("event_id"),
                "type": etype,
                "age_days": round(age_days, 2),
                "magnitude": mag,
                "direction": direction,
                "confidence": ev_conf,
                "impact": round(impact, 4),
                "is_insider": is_insider,
            })

        # Cap the collective insider impact so a Form-4 flood can't drown
        # out a single material 8-K. Non-insider events keep full voice.
        capped_insider = max(-INSIDER_AGGREGATE_CAP,
                             min(INSIDER_AGGREGATE_CAP, insider_impact_sum))
        total_impact = capped_insider + other_impact_sum
        s = math.tanh(total_impact)
        n = len(events)
        comp_conf = min(1.0, n / CONFIDENCE_FULL_N)

        # Cap contributors detail at top-5 by absolute impact for `yuclaw why`.
        top5 = sorted(contributors, key=lambda c: abs(c["impact"]), reverse=True)[:5]
        # event_ids is the FULL list of inputs (needed by the replay leak audit
        # and by snapshot_writer's evidence trail; top_contributors is the
        # truncated display version).
        all_event_ids = [c["event_id"] for c in contributors if c.get("event_id")]
        n_insider = sum(1 for c in contributors if c["is_insider"])
        rationale = (
            f"{n} event(s) in 30d "
            f"(insider sum {insider_impact_sum:+.3f} → capped {capped_insider:+.3f}; "
            f"other sum {other_impact_sum:+.3f}) "
            f"→ tanh {s:+.3f}"
        )
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=comp_conf,
            rationale=rationale,
            details={
                "n_events": n,
                "n_insider": n_insider,
                "insider_impact_sum_raw": round(insider_impact_sum, 4),
                "insider_impact_sum_capped": round(capped_insider, 4),
                "other_impact_sum": round(other_impact_sum, 4),
                "total_impact": round(total_impact, 4),
                "top_contributors": top5,
                "inputs": {"event_ids": all_event_ids},
            },
        )
