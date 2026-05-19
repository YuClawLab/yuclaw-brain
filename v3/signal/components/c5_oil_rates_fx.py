"""
C5 — Oil / rates / FX exposure.

Sector-conditional response to three macro factors:
    Oil    (proxy: XLE 1d change_pct, since v2.3.0 has no raw WTI)
    Rates  (proxy: TLT momentum from regime.indicators; TLT ↑ → rates ↓)
    FX     (proxy: UUP momentum from regime.indicators; UUP ↑ → USD strong)

Per-sector wiring (cohorts hardcoded — change-controlled):
    Energy        (XOM, CVX, COP, SLB, PSX): oil↑ → + ; rates neutral; USD↓ → +
    Banks         (JPM, BAC, GS, MS, WFC, C, AXP): rates↑ → + ; USD↑ → modest +
    Multinat tech (NVDA, AAPL, MSFT, GOOGL, META, AMZN, AMD): USD↑ → -
    Other         no mapping → score 0, confidence 0.3

Final score = mean(applicable sub-scores), each sub-score is tanh-squashed.
Confidence reflects how many of {oil, rates, fx} we could resolve for this
ticker.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.data_loader import get_macro_regime, get_sector_velocity

_ENERGY = {"XOM", "CVX", "COP", "SLB", "PSX"}
_BANKS = {"JPM", "BAC", "GS", "MS", "WFC", "C", "AXP"}
_MULTINAT_TECH = {"NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "AMD", "QCOM"}

# Saturation scales — calibrated to v2.3.0 regime.indicators typical ranges
# (TLT/UUP momentum sit around ±0.05; XLE day moves ±2%).
_TLT_SATURATION = 0.05
_UUP_SATURATION = 0.05
_OIL_SATURATION = 2.0  # XLE change_pct in percent


def _safe_tanh(x: float, sat: float) -> float:
    return math.tanh(x / sat) if sat > 0 else 0.0


class C5OilRatesFX(SignalComponent):
    component_id = "c5"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        state = ctx.get("v2_state") or {}
        t = ticker.upper()
        macro = get_macro_regime(state)
        indicators = macro.get("indicators") or {}

        tlt_mom = indicators.get("TLT")           # bonds momentum
        uup_mom = indicators.get("UUP")           # USD momentum (DXY proxy)
        xle_row = get_sector_velocity(state, "XLE")
        oil_proxy = xle_row.get("change_pct") if xle_row else None  # 1d energy ETF

        sub_scores: list[float] = []
        contributions: dict[str, Any] = {}

        # Energy: oil↑ → +; bonds neutral; USD↓ → + (USD strength makes
        # exporters' oil revenue weaker in $).
        if t in _ENERGY:
            if oil_proxy is not None:
                s = _safe_tanh(float(oil_proxy), _OIL_SATURATION)
                sub_scores.append(s)
                contributions["oil"] = {"input": oil_proxy, "score": round(s, 3)}
            if uup_mom is not None:
                # USD strength hurts → negate
                s = -_safe_tanh(float(uup_mom), _UUP_SATURATION)
                sub_scores.append(s)
                contributions["usd"] = {"input": uup_mom, "score": round(s, 3)}

        # Banks: rates↑ → + (TLT ↓ means rates ↑, so flip TLT sign)
        elif t in _BANKS:
            if tlt_mom is not None:
                s = -_safe_tanh(float(tlt_mom), _TLT_SATURATION)
                sub_scores.append(s)
                contributions["rates"] = {"input_tlt": tlt_mom, "score": round(s, 3)}
            if uup_mom is not None:
                s = 0.5 * _safe_tanh(float(uup_mom), _UUP_SATURATION)
                sub_scores.append(s)
                contributions["usd"] = {"input": uup_mom, "score": round(s, 3)}

        # Multinational tech: USD↑ → - (foreign revenue translation hit).
        elif t in _MULTINAT_TECH:
            if uup_mom is not None:
                s = -_safe_tanh(float(uup_mom), _UUP_SATURATION)
                sub_scores.append(s)
                contributions["usd"] = {"input": uup_mom, "score": round(s, 3)}

        else:
            # No sector-conditional mapping — issue a low-confidence placeholder
            # so the composite doesn't double-count macro via C4.
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.3,
                rationale=f"no oil/rates/FX mapping for {t}",
                details={"sector": None},
            )

        if not sub_scores:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.1,
                rationale="all required macro indicators missing in v2.3.0 state",
                details=contributions,
            )

        avg = sum(sub_scores) / len(sub_scores)
        # Confidence proportional to how many sub-signals we had
        conf = min(1.0, 0.4 + 0.3 * len(sub_scores))
        return ComponentResult(
            component=self.component_id,
            score=avg,
            confidence=conf,
            rationale=f"{len(sub_scores)} sub-signal(s) → avg {avg:+.3f}",
            details=contributions,
        )
