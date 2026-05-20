"""
C2 — volume confirmation.

Volume data is NOT yet published in v2.3.0 dashboard_state.json (Day 5
gap: we'll wire a real EOD volume feed). For Day 4 we ship a real
ComponentResult that self-masks via confidence=0.0 with a clear rationale,
rather than a stub. As soon as the volume feed lands, this file's score()
flips from a 0-confidence return to a real signal — no contract change
elsewhere in the framework.

When the feed exists, the rule is:
    z = (current_volume / 20d_avg_volume) - 1.0
    score = tanh(z * sign(price_move))  → confirms or contradicts direction
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent


class C2VolumeConfirmation(SignalComponent):
    component_id = "c2"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        # Real volume data not in v2.3.0 dashboard_state.json — return
        # zero-confidence so we drop out of the composite denominator
        # without faking signal.
        return ComponentResult(
            component=self.component_id,
            score=0.0,
            confidence=0.0,
            rationale="volume feed not yet wired (Day 5)",
            details={"data_source": None},
        )
