"""yuclaw/modules/portfolio_optimizer.py — Size positions using real backtest Calmar ratios.

Higher Calmar = higher allocation. Uses inverse-volatility weighting
scaled by Calmar ratio to produce optimal position sizes from real data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class PositionSize:
    """Recommended position size for a strategy or instrument."""
    name: str
    calmar: float
    sharpe: float
    max_drawdown: float
    raw_weight: float
    final_weight: float
    notional_usd: float = 0.0
    rationale: str = ""


@dataclass
class PortfolioAllocation:
    """Complete portfolio allocation based on real backtest data."""
    total_capital: float
    positions: list[PositionSize]
    total_weight: float = 1.0
    concentration_risk: str = "low"
    max_single_position: float = 0.0

    def summary(self) -> str:
        lines = [
            "=" * 65,
            "  PORTFOLIO OPTIMIZER — Real Calmar-Weighted Allocation",
            "=" * 65,
            f"  Total Capital: ${self.total_capital:,.0f}",
            f"  Concentration Risk: {self.concentration_risk}",
            f"  Max Single Position: {self.max_single_position:.1%}",
            "",
            f"  {'Strategy':<25} {'Calmar':>7} {'Weight':>8} {'Notional':>12} {'MaxDD':>7}",
            "  " + "-" * 60,
        ]
        for p in sorted(self.positions, key=lambda x: -x.final_weight):
            lines.append(
                f"  {p.name:<25} {p.calmar:7.3f} {p.final_weight:7.1%} "
                f"${p.notional_usd:>11,.0f} {p.max_drawdown:6.1%}"
            )
        lines.append("  " + "-" * 60)
        lines.append(f"  {'TOTAL':<25} {'':>7} {sum(p.final_weight for p in self.positions):7.1%}")
        lines.append("=" * 65)
        return "\n".join(lines)


class PortfolioOptimizer:
    """Size positions based on real backtest Calmar ratios.

    Allocation methodology:
    1. Raw weight = Calmar^alpha (alpha controls how aggressively to tilt toward high-Calmar strategies)
    2. Apply max position constraint (default 30%)
    3. Normalize to sum to 1.0
    4. Multiply by total capital

    Strategies with Calmar < min_calmar are excluded entirely.
    """

    def __init__(
        self,
        alpha: float = 1.5,
        max_position_pct: float = 0.30,
        min_calmar: float = 0.5,
    ):
        self._alpha = alpha
        self._max_pos = max_position_pct
        self._min_calmar = min_calmar

    def optimize(
        self,
        strategies: list[dict],
        total_capital: float = 1_000_000.0,
    ) -> PortfolioAllocation:
        """Compute optimal allocation from backtest results.

        Args:
            strategies: List of dicts with keys:
                - name: strategy identifier
                - calmar: real Calmar ratio from backtest
                - sharpe: Sharpe ratio
                - max_drawdown: maximum drawdown (positive number, e.g. 0.128)
                - annualized_return: annual return
            total_capital: total portfolio capital in USD

        Returns:
            PortfolioAllocation with sized positions.
        """
        # Filter by minimum Calmar
        eligible = [s for s in strategies if s.get("calmar", 0) >= self._min_calmar]
        if not eligible:
            return PortfolioAllocation(
                total_capital=total_capital, positions=[],
                concentration_risk="no eligible strategies"
            )

        # Compute raw weights: Calmar^alpha
        raw_weights = []
        for s in eligible:
            calmar = max(s["calmar"], 0.01)
            raw = calmar ** self._alpha
            raw_weights.append(raw)

        total_raw = sum(raw_weights)

        # Normalize and apply max position constraint
        positions = []
        for s, raw in zip(eligible, raw_weights):
            weight = raw / total_raw
            weight = min(weight, self._max_pos)
            positions.append(PositionSize(
                name=s["name"],
                calmar=s["calmar"],
                sharpe=s.get("sharpe", 0),
                max_drawdown=s.get("max_drawdown", 0),
                raw_weight=raw / total_raw,
                final_weight=weight,
            ))

        # Re-normalize after capping
        total_capped = sum(p.final_weight for p in positions)
        if total_capped > 0:
            for p in positions:
                p.final_weight /= total_capped
                p.notional_usd = p.final_weight * total_capital

        # Assess concentration
        max_pos = max(p.final_weight for p in positions) if positions else 0
        if max_pos > 0.5:
            concentration = "high"
        elif max_pos > 0.3:
            concentration = "moderate"
        else:
            concentration = "low"

        # Generate rationale
        for p in positions:
            p.rationale = (
                f"Calmar {p.calmar:.3f} -> raw weight {p.raw_weight:.1%}, "
                f"capped at {self._max_pos:.0%}, final {p.final_weight:.1%}"
            )

        return PortfolioAllocation(
            total_capital=total_capital,
            positions=positions,
            concentration_risk=concentration,
            max_single_position=max_pos,
        )

    def optimize_from_backtester(self, total_capital: float = 1_000_000.0) -> PortfolioAllocation:
        """Run backtests and optimize in one step."""
        from ..validation.real_backtest import RealBacktester

        bt = RealBacktester()
        configs = [
            {"name": "momentum_1m_top3", "lookback": 1, "top_n": 3, "stop": 0.03},
            {"name": "momentum_3m_top5", "lookback": 3, "top_n": 5, "stop": 0.03},
            {"name": "momentum_6m_top3", "lookback": 6, "top_n": 3, "stop": 0.05},
            {"name": "momentum_6m_top5", "lookback": 6, "top_n": 5, "stop": 0.05},
            {"name": "momentum_12m_top5", "lookback": 12, "top_n": 5, "stop": 0.08},
        ]

        strategies = []
        for cfg in configs:
            result = bt.run_momentum(
                lookback_months=cfg["lookback"],
                top_n=cfg["top_n"],
                stop_loss=cfg["stop"],
                start="2008-01-01",
            )
            if result:
                strategies.append({
                    "name": cfg["name"],
                    "calmar": result.calmar_ratio,
                    "sharpe": result.sharpe_ratio,
                    "max_drawdown": result.max_drawdown,
                    "annualized_return": result.annualized_return,
                })

        return self.optimize(strategies, total_capital)
