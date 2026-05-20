"""
C3 — sector velocity.

For each equity ticker, look up its sector ETF, then compute its 1-day
change_pct's z-score across all 11 sectors in sector.rotation. Tickers in
sectors that are outperforming the sector average get a positive C3,
underperformers get negative.

v2.3.0 only publishes 1-day change_pct; once 5d/20d roll-ups land, we'll
add a weighted average. For now: tanh(z / 1.5) gives a sane spread —
±1.5σ saturates the score.

For ETF tickers (XLK, SPY, etc.) C3 reads the ETF's own row directly.
For tickers we have no sector mapping for, score=0, confidence=0.3 so
the component doesn't dominate but still surfaces a placeholder.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any, Optional

from v3.signal.base import ComponentResult, SignalComponent
from v3.signal.data_loader import is_historical

# Locked ticker → sector-ETF mapping for the v3.0 universe.
# Keeps C3 deterministic; replace with a real S&P-classification lookup later.
TICKER_TO_SECTOR_ETF: dict[str, str] = {
    # XLK — Technology
    **{t: "XLK" for t in [
        "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMD", "INTC", "MU", "MRVL",
        "ARM", "AMAT", "LRCX", "AMZN", "HPE", "DELL", "TSM", "QCOM",
    ]},
    # XLF — Financials
    **{t: "XLF" for t in [
        "JPM", "BAC", "GS", "MS", "WFC", "C", "AXP", "V", "MA", "PYPL",
    ]},
    # XLV — Healthcare
    **{t: "XLV" for t in [
        "UNH", "JNJ", "PFE", "MRK", "ABBV", "LLY", "TMO", "DHR", "ABT", "BMY",
    ]},
    # XLE — Energy
    **{t: "XLE" for t in [
        "XOM", "CVX", "COP", "SLB", "PSX",
    ]},
    # XLP — Consumer staples
    **{t: "XLP" for t in [
        "PG", "KO", "PEP", "WMT", "COST",
    ]},
    # XLY — Consumer discretionary
    "TSLA": "XLY",
    # XLC — Communications
    "GOOGL": "XLC",  # GOOGL spans XLC + XLK; XLK takes priority above
}

# ETFs map to themselves so we can score them directly.
_SECTOR_ETFS = {"XLK", "XLF", "XLE", "XLV", "XLU", "XLI", "XLY",
                "XLP", "XLB", "XLRE", "XLC", "SMH", "KRE", "IBB", "XBI"}


def _sector_zscore(state: dict[str, Any], target_etf: str) -> Optional[tuple[float, float]]:
    """Compute (z_score, sector_pct_change) for `target_etf`.
    Returns None if we can't find the etf or have <3 sectors to compare.
    """
    rotation = (state.get("sector") or {}).get("rotation") or []
    pcts = []
    target_pct: Optional[float] = None
    for r in rotation:
        etf = (r.get("etf") or "").upper()
        try:
            pct = float(r.get("change_pct"))
        except (TypeError, ValueError):
            continue
        pcts.append(pct)
        if etf == target_etf.upper():
            target_pct = pct
    if target_pct is None or len(pcts) < 3:
        return None
    mean = statistics.mean(pcts)
    stdev = statistics.pstdev(pcts) or 1e-9
    return ((target_pct - mean) / stdev, target_pct)


class C3SectorVelocity(SignalComponent):
    component_id = "c3"

    def score(self, ticker: str, as_of: datetime, ctx: dict[str, Any]) -> ComponentResult:
        state = ctx.get("v2_state") or {}
        t = ticker.upper()

        target_etf: Optional[str] = None
        if t in _SECTOR_ETFS:
            target_etf = t
        elif t in TICKER_TO_SECTOR_ETF:
            target_etf = TICKER_TO_SECTOR_ETF[t]

        if target_etf is None:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.3,
                rationale=f"no sector mapping for {t}",
                details={"sector_etf": None},
            )

        result = _sector_zscore(state, target_etf)
        if result is None:
            return ComponentResult(
                component=self.component_id,
                score=0.0,
                confidence=0.0,
                rationale=f"no sector.rotation data for {target_etf}",
                details={"sector_etf": target_etf},
            )

        z, pct = result
        s = math.tanh(z / 1.5)
        historical = is_historical(as_of)
        confidence = 0.3 if historical else 0.8
        rationale = f"{target_etf} 1d {pct:+.2f}% (z={z:+.2f}) → score {s:+.3f}"
        if historical:
            rationale += " (warning: point-in-time approximation — v2.3.0 dashboard holds latest snapshot only)"
        return ComponentResult(
            component=self.component_id,
            score=s,
            confidence=confidence,
            rationale=rationale,
            details={
                "sector_etf": target_etf,
                "change_pct_1d": pct,
                "z_score": z,
                "historical_approximation": historical,
            },
        )
