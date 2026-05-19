"""
C4 — macro regime.

Reads the v2.3.0 dashboard's macro regime label + confidence and maps to a
ticker-independent score. Every equity in a RISK_ON regime gets the same C4
contribution.

Scoring rule:
    RISK_ON   →  +0.6
    NEUTRAL   →   0.0
    RISK_OFF  →  -0.6
    (unknown labels → 0.0 score, 0.0 confidence)

Magnitude is 0.6 not 1.0 because the regime is one of nine inputs, and
saturating macro on every signal would crowd out ticker-specific factors.
v2.3.0 confidence flows through to ComponentResult.confidence so a low-
conviction NEUTRAL regime doesn't drag the composite as much.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.data_loader import get_macro_regime

_REGIME_SCORE: dict[str, float] = {
    "RISK_ON": 0.6,
    "NEUTRAL": 0.0,
    "RISK_OFF": -0.6,
}


class C4MacroRegime(SignalComponent):
    component_id = "c4"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        state = ctx.get("v2_state") or {}
        macro = get_macro_regime(state)
        regime = (macro.get("regime") or "").upper()
        confidence = float(macro.get("confidence") or 0.0)

        if regime not in _REGIME_SCORE:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale=f"unknown regime label {regime!r}",
                details={"regime": regime, "raw_confidence": confidence},
            )

        s = _REGIME_SCORE[regime]
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=confidence,
            rationale=f"macro regime {regime} (conf {confidence:.2f}) → score {s:+.2f}",
            details={"regime": regime, "raw_confidence": confidence},
        )
