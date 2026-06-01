"""
Risk Engine — real portfolio risk calculation.
VaR, Expected Shortfall, Kelly sizing, position limits.
All from real historical returns. Zero LLM involvement.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PortfolioRisk:
    tickers: list[str]
    weights: list[float]
    var_95: float
    var_99: float
    expected_shortfall: float
    portfolio_volatility: float
    portfolio_sharpe: float
    max_drawdown: float
    kelly_fraction: float
    max_position_size: float
    risk_budget_used: float
    is_real: bool = True
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 55,
            "  PORTFOLIO RISK ANALYSIS (Real Data)",
            "=" * 55,
            f"  VaR 95% (1-day):      {self.var_95:.2%}",
            f"  VaR 99% (1-day):      {self.var_99:.2%}",
            f"  Expected Shortfall:   {self.expected_shortfall:.2%}",
            f"  Portfolio Volatility: {self.portfolio_volatility:.2%}",
            f"  Sharpe Ratio:         {self.portfolio_sharpe:.2f}",
            f"  Max Drawdown:         {self.max_drawdown:.2%}",
            f"  Kelly Fraction:       {self.kelly_fraction:.2%}",
            f"  Max Position Size:    {self.max_position_size:.2%}",
            f"  Risk Budget Used:     {self.risk_budget_used:.1%}",
            f"  Is Real: {self.is_real}",
        ]
        if self.warnings:
            lines.append("  WARNINGS:")
            for w in self.warnings:
                lines.append(f"    {w}")
        lines.append("=" * 55)
        return "\n".join(lines)


class RiskEngine:
    """Institutional-grade risk calculations from real price history."""

    def analyze_portfolio(
        self,
        tickers: list[str],
        weights: list[float],
        confidence: float = 0.95,
    ) -> PortfolioRisk:
        warnings = []

        prices = yf.download(tickers, period="2y", progress=False, auto_adjust=True)["Close"]
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(tickers[0])
        prices = prices.dropna()

        if len(prices) < 60:
            warnings.append("Insufficient price history")

        returns = prices.pct_change().dropna()
        w = np.array(weights)
        w = w / w.sum()

        port_returns = (returns * w).sum(axis=1)

        var_95 = float(np.percentile(port_returns, (1 - confidence) * 100))
        var_99 = float(np.percentile(port_returns, 1.0))

        es_threshold = np.percentile(port_returns, (1 - confidence) * 100)
        es = float(port_returns[port_returns <= es_threshold].mean())

        cov_matrix = returns.cov() * 252
        port_vol = float(np.sqrt(w @ cov_matrix.values @ w))

        port_ann_return = float(port_returns.mean() * 252)
        sharpe = port_ann_return / port_vol if port_vol > 0 else 0

        equity = (1 + port_returns).cumprod()
        roll_max = equity.cummax()
        max_dd = float(((equity - roll_max) / roll_max).min())

        win_rate = float((port_returns > 0).mean())
        avg_win = float(port_returns[port_returns > 0].mean()) if (port_returns > 0).any() else 0
        avg_loss = float(abs(port_returns[port_returns < 0].mean())) if (port_returns < 0).any() else 1
        kelly = (win_rate / avg_loss - (1 - win_rate) / avg_win) if avg_win > 0 else 0
        kelly = max(0, min(kelly * 0.5, 0.25))

        max_pos = min(kelly, 0.20)
        risk_used = abs(var_95) / 0.02

        if abs(var_95) > 0.03:
            warnings.append(f"High daily VaR: {var_95:.1%}")
        if max_dd < -0.20:
            warnings.append(f"High max drawdown: {max_dd:.1%}")

        return PortfolioRisk(
            tickers=tickers, weights=list(w),
            var_95=var_95, var_99=var_99,
            expected_shortfall=es, portfolio_volatility=port_vol,
            portfolio_sharpe=sharpe, max_drawdown=max_dd,
            kelly_fraction=float(kelly), max_position_size=float(max_pos),
            risk_budget_used=float(risk_used), is_real=True, warnings=warnings,
        )
