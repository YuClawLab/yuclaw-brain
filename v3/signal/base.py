"""
v3.0 signal framework — base contracts.

A Signal = weighted sum of nine independent ComponentResults, each in [-1, 1]
with an own confidence in [0, 1]. The composite formula is

    total_score = sum(weight[i] * score[i] * confidence[i])
                / sum(weight[i] * confidence[i])

and the public label is the threshold mapping in signal_label().

Component weights are LOCKED for v3.0 — the contract published in the
v3.0-evidence design doc. Changing them is a versioned release event.
Confidence on a stub is 0.0, so missing components self-mask out of the
denominator and don't bias the composite.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Component weights (LOCKED for v3.0). Must sum to 1.0.
# C6 (event impact) is intentionally the largest single weight — it's the
# component that v3.0 exists for. Don't quietly rebalance these.
# ---------------------------------------------------------------------------
COMPONENT_WEIGHTS: dict[str, float] = {
    "c1": 0.12,  # price momentum
    "c2": 0.08,  # volume confirmation
    "c3": 0.12,  # sector velocity
    "c4": 0.15,  # macro regime
    "c5": 0.05,  # oil / rates / FX
    "c6": 0.18,  # event impact (highest — v3.0 differentiator)
    "c7": 0.10,  # peer correlation
    "c8": 0.12,  # cascade effect
    "c9": 0.08,  # model trust
}

assert math.isclose(sum(COMPONENT_WEIGHTS.values()), 1.0, abs_tol=1e-9), \
    f"COMPONENT_WEIGHTS sum to {sum(COMPONENT_WEIGHTS.values())}, not 1.0"


# Public signal vocabulary (LOCKED). No SELL/SHORT in the public surface.
SIGNAL_THRESHOLDS: list[tuple[float, str]] = [
    (0.55, "STRONG_BUY"),
    (0.40, "BUY"),
    (0.20, "HOLD"),
    (0.00, "WATCH"),
    (-0.20, "WEAKENING"),
    (-0.40, "NEGATIVE_EVENT"),
    (-1.01, "DOWNSIDE_WATCH"),  # catches anything <= -0.40
]


def signal_label(total_score: float) -> str:
    """Map composite score → public vocabulary label."""
    for floor, label in SIGNAL_THRESHOLDS:
        if total_score >= floor:
            return label
    return "DOWNSIDE_WATCH"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class ComponentResult:
    """One component's contribution to a composite signal.

    score:           in [-1.0, 1.0]; sign carries direction
    confidence:      in [0.0, 1.0]; 0.0 means "we have no data, ignore me"
    not_implemented: True for stub components — caller drops these from the
                     composite denominator so stubs don't distort the score.
    rationale:       short human-readable string, surfaced in `yuclaw why`
    details:         optional dict for debugging / display (raw inputs etc.)
    """
    component: str
    score: float
    confidence: float
    rationale: str = ""
    not_implemented: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.not_implemented:
            # Hard-clip out-of-range values rather than silently allow them.
            self.score = max(-1.0, min(1.0, float(self.score)))
            self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Component ABC
# ---------------------------------------------------------------------------
class SignalComponent(ABC):
    """All Cn implementations subclass this and return a ComponentResult."""

    component_id: str = ""  # "c1", "c4", etc.

    @abstractmethod
    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        """Compute this component's contribution for (ticker, as_of).

        ctx is a shared dict the composite orchestrator threads through every
        component — typically holds:
            ctx["v2_state"]: docs/data/dashboard_state.json contents
            ctx["events"]:   list of event rows for `ticker`, latest first
        """
        ...


def stub_result(component_id: str, reason: str = "not yet implemented") -> ComponentResult:
    """Standard 'not implemented' result for Day 4+ components."""
    return ComponentResult(
        component=component_id,
        score=0.0,
        confidence=0.0,
        rationale=reason,
        not_implemented=True,
    )
