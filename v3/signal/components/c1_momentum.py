"""
C1 — price momentum.

Reads 1-month momentum from v2.3.0 dashboard_state.json (parsed out of the
`reasoning` array, where v2 publishes it as "mom_1m=+10.20%"). v2.3.0 owns the
price-history math; v3.0 doesn't duplicate it.

Scoring rule:
    raw = mom_1m / MOM_FULL_SCALE         # ±20% → ±1.0
    score = clamp(raw, -1.0, 1.0)
    confidence = 0.9 if mom_1m available, else 0.0

MOM_FULL_SCALE = 0.20 is calibrated against the v2.3.0 dashboard: tickers
the dashboard labels STRONG_BULLISH tend to have mom_1m in the +15% to +25%
range, so saturating at 20% gives a meaningful spread without clipping
the bulk of the population.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.data_loader import get_mom_1m, is_historical

MOM_FULL_SCALE = 0.20  # ±20% one-month return → ±1.0 score

# When this component is called with as_of in the past, the underlying
# dashboard_state.json doesn't carry history — we approximate using whatever
# the file holds today. Degrade confidence so the composite knows the input
# is suspect for replays.
HISTORICAL_CONFIDENCE = 0.3


class C1Momentum(SignalComponent):
    component_id = "c1"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        state = ctx.get("v2_state") or {}
        mom_1m = get_mom_1m(state, ticker)
        if mom_1m is None:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale="no mom_1m available in v2.3.0 state",
                details={"ticker": ticker},
            )

        raw = mom_1m / MOM_FULL_SCALE
        s = max(-1.0, min(1.0, raw))
        historical = is_historical(as_of)
        confidence = HISTORICAL_CONFIDENCE if historical else 0.9
        rationale = f"1-month momentum {mom_1m*100:+.2f}% → score {s:+.3f}"
        if historical:
            rationale += " (warning: point-in-time approximation — v2.3.0 dashboard holds latest snapshot only)"
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=confidence,
            rationale=rationale,
            details={
                "mom_1m": mom_1m,
                "full_scale": MOM_FULL_SCALE,
                "historical_approximation": historical,
            },
        )
