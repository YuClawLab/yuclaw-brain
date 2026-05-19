"""
Day-3 stub components for C2/C3/C5/C7/C8/C9.

Each returns ComponentResult(not_implemented=True, confidence=0.0) so the
composite orchestrator can drop them from the denominator without distorting
the score. Day 4 work replaces these one at a time.

Why stubs and not absent components: the composite contract enumerates all
nine components by name. Keeping the slots present (even if zero-weighted
in practice) makes the breakdown JSON shape stable across Day 3 → Day 4,
so the dashboard / `yuclaw why` UI doesn't need to be rewritten when we
fill them in.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent, stub_result


class _Stub(SignalComponent):
    """Shared stub implementation."""

    def __init__(self, component_id: str, reason: str = "scheduled for Day 4") -> None:
        self.component_id = component_id
        self._reason = reason

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        return stub_result(self.component_id, reason=self._reason)


class C2VolumeConfirmation(_Stub):
    def __init__(self) -> None:
        super().__init__("c2", "volume confirmation — Day 4")


class C3SectorVelocity(_Stub):
    def __init__(self) -> None:
        super().__init__("c3", "sector velocity — Day 4 (needs ticker→sector map)")


class C5OilRatesFX(_Stub):
    def __init__(self) -> None:
        super().__init__("c5", "oil / rates / FX — Day 4")


class C7PeerCorrelation(_Stub):
    def __init__(self) -> None:
        super().__init__("c7", "peer correlation — Day 4 (needs correlation matrix)")


class C8CascadeEffect(_Stub):
    def __init__(self) -> None:
        super().__init__("c8", "cascade effect — Day 4 (needs cascade engine)")


class C9ModelTrust(_Stub):
    def __init__(self) -> None:
        super().__init__("c9", "model trust — Day 4 (needs track-record table)")
