"""
C7 — peer correlation.

True C7 needs 20d return correlations across the sector cohort. v2.3.0
dashboard_state.json publishes per-ticker mom_1m but not return time series,
so we use a proxy:

    1. Look up the ticker's sector cohort (same XL_ ETF members).
    2. Compare this ticker's mom_1m sign to the cohort majority sign.
    3. Score = (this_mom_sign × cohort_majority_fraction × |cohort_mean_mom|/sat)
       saturated via tanh.
    4. Confidence = (cohort tickers with data) / (cohort size).

Interpretation: ticker moving WITH a strong cohort consensus gets a
positive C7; against consensus gets negative.

Day 5+: replace with real correlation-matrix-of-returns once we publish
20d returns to dashboard_state (or move price history into Postgres).
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.components.c3_sector_velocity import TICKER_TO_SECTOR_ETF
from v3.signal.data_loader import get_mom_1m, is_historical

# Per-sector cohort lists — same membership as supply_chain ETF edges.
_COHORTS: dict[str, list[str]] = {
    "XLK": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD", "INTC", "MU",
            "MRVL", "ARM", "AMAT", "LRCX", "AMZN"],
    "XLF": ["JPM", "BAC", "GS", "MS", "WFC", "C", "AXP", "V", "MA", "PYPL"],
    "XLE": ["XOM", "CVX", "COP", "SLB", "PSX"],
    "XLV": ["UNH", "JNJ", "PFE", "MRK", "ABBV", "LLY", "TMO", "DHR", "ABT", "BMY"],
    "XLP": ["PG", "KO", "PEP", "WMT", "COST"],
}

_MOM_SATURATION = 0.15  # cohort mean mom of ±15% saturates the score


class C7PeerCorrelation(SignalComponent):
    component_id = "c7"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        state = ctx.get("v2_state") or {}
        t = ticker.upper()
        etf = TICKER_TO_SECTOR_ETF.get(t)
        if etf is None or etf not in _COHORTS:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale=f"no sector cohort for {t}",
                details={"sector_etf": etf},
            )

        my_mom = get_mom_1m(state, t)
        if my_mom is None:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale=f"{t} has no mom_1m",
                details={"sector_etf": etf},
            )

        cohort = [p for p in _COHORTS[etf] if p != t]
        moms = []
        for p in cohort:
            m = get_mom_1m(state, p)
            if m is not None:
                moms.append(m)

        if not moms:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale=f"no peer mom data for cohort {etf}",
                details={"sector_etf": etf, "cohort_size": len(cohort)},
            )

        cohort_mean = sum(moms) / len(moms)
        same_sign = sum(1 for m in moms if (m > 0) == (my_mom > 0))
        majority_frac = same_sign / len(moms)

        # Sign convention: positive when ticker moves WITH the cohort.
        agree_sign = 1.0 if (my_mom > 0) == (cohort_mean > 0) else -1.0
        magnitude_term = math.tanh(abs(cohort_mean) / _MOM_SATURATION)
        s = agree_sign * majority_frac * magnitude_term

        conf = min(1.0, len(moms) / len(cohort)) if cohort else 0.0
        historical = is_historical(as_of)
        if historical:
            conf = min(conf, 0.3)
        rationale = (f"cohort {etf} mean mom {cohort_mean*100:+.2f}%, "
                     f"majority agree {same_sign}/{len(moms)} → score {s:+.3f}")
        if historical:
            rationale += " (warning: point-in-time approximation — cohort moms come from latest dashboard only)"

        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=conf,
            rationale=rationale,
            details={
                "sector_etf": etf,
                "cohort_size_total": len(cohort),
                "cohort_size_with_data": len(moms),
                "ticker_mom_1m": my_mom,
                "cohort_mean_mom_1m": cohort_mean,
                "majority_fraction": majority_frac,
                "historical_approximation": historical,
            },
        )
