"""yuclaw/validation/real_backtest.py — Real backtesting with actual price data.

Uses yfinance to download real historical prices and compute actual returns,
drawdowns, Calmar ratios, and Sharpe ratios. No LLM estimation anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    """Result of a real backtest with actual price data."""
    strategy_name: str
    start_date: str
    end_date: str
    annualized_return: float
    max_drawdown: float
    calmar_ratio: float
    sharpe_ratio: float
    total_return: float
    volatility: float
    num_trades: int
    win_rate: float
    crisis_returns: dict[str, float] = field(default_factory=dict)
    is_real: bool = True  # Always True — this uses actual prices

    def summary(self) -> str:
        lines = [
            f"=== REAL BACKTEST: {self.strategy_name} ===",
            f"Period:          {self.start_date} to {self.end_date}",
            f"Annual Return:   {self.annualized_return:.1%}",
            f"Max Drawdown:    {self.max_drawdown:.1%}",
            f"Calmar Ratio:    {self.calmar_ratio:.3f}",
            f"Sharpe Ratio:    {self.sharpe_ratio:.2f}",
            f"Total Return:    {self.total_return:.1%}",
            f"Volatility:      {self.volatility:.1%}",
            f"Trades:          {self.num_trades}",
            f"Win Rate:        {self.win_rate:.1%}",
            f"IS_REAL:         {self.is_real}",
        ]
        if self.crisis_returns:
            lines.append("Crisis Performance:")
            for name, ret in self.crisis_returns.items():
                lines.append(f"  {name}: {ret:.1%}")
        return "\n".join(lines)


# Crisis periods for stress testing
CRISIS_PERIODS = {
    "GFC_2008": ("2008-09-01", "2009-03-31"),
    "COVID_2020": ("2020-02-15", "2020-03-31"),
    "RATES_2022": ("2022-01-01", "2022-10-31"),
    "SVB_2023": ("2023-03-01", "2023-03-31"),
}

# Default ETF universe for momentum strategies
DEFAULT_UNIVERSE = [
    "SPY", "QQQ", "IWM", "EFA", "EEM",
    "XLK", "XLF", "XLE", "XLV", "XLI",
    "XLP", "XLU", "XLY", "XLB", "XLRE",
    "TLT", "GLD", "SLV", "VNQ", "HYG",
]


class RealBacktester:
    """Backtest strategies using real historical price data from yfinance."""

    def __init__(self, universe: Optional[list[str]] = None):
        self.universe = universe or DEFAULT_UNIVERSE

    def _download_prices(self, tickers: list[str], start: str, end: Optional[str] = None) -> pd.DataFrame:
        """Download adjusted close prices for all tickers."""
        import yfinance as yf
        data = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)
        if isinstance(data.columns, pd.MultiIndex):
            prices = data["Close"]
        else:
            prices = data[["Close"]]
            prices.columns = tickers[:1]
        return prices.dropna(how="all")

    def run_momentum(
        self,
        start: str = "2010-01-01",
        end: Optional[str] = None,
        lookback_months: int = 6,
        top_n: int = 3,
        stop_loss: float = 0.05,
        rebalance_freq: str = "ME",
    ) -> Optional[BacktestResult]:
        """Run a real momentum strategy backtest.

        Strategy: each month, rank ETFs by trailing N-month return.
        Buy the top_n, equal weight. Apply stop-loss intra-month.

        All numbers are from REAL prices. No estimation.
        """
        try:
            prices = self._download_prices(self.universe, start, end)
            if prices.empty or len(prices) < lookback_months * 21:
                print("[RealBacktest] Insufficient price data")
                return None

            # Monthly returns for momentum scoring
            monthly = prices.resample(rebalance_freq).last()
            lookback = lookback_months

            portfolio_returns = []
            trade_returns = []
            dates = []

            for i in range(lookback, len(monthly) - 1):
                # Momentum signal: trailing N-month return
                past = monthly.iloc[i - lookback]
                current = monthly.iloc[i]
                momentum = (current / past - 1).dropna()

                if len(momentum) < top_n:
                    continue

                # Select top N
                top = momentum.nlargest(top_n).index.tolist()

                # Get daily returns for the next month
                start_date = monthly.index[i]
                end_date = monthly.index[i + 1]
                mask = (prices.index > start_date) & (prices.index <= end_date)
                period_prices = prices.loc[mask, top].dropna(how="all")

                if period_prices.empty:
                    continue

                # Equal weight, apply stop-loss
                daily_rets = period_prices.pct_change().dropna()
                cum_rets = (1 + daily_rets).cumprod() - 1

                for col in cum_rets.columns:
                    stopped = cum_rets[col] < -stop_loss
                    if stopped.any():
                        stop_idx = stopped.idxmax()
                        daily_rets.loc[stop_idx:, col] = 0.0

                # Portfolio return (equal weight)
                port_daily = daily_rets.mean(axis=1)
                portfolio_returns.extend(port_daily.tolist())
                dates.extend(port_daily.index.tolist())

                # Track trade returns for win rate
                month_ret = (1 + port_daily).prod() - 1
                trade_returns.append(month_ret)

            if not portfolio_returns:
                print("[RealBacktest] No valid trading periods")
                return None

            # Build equity curve
            returns = pd.Series(portfolio_returns, index=dates)
            equity = (1 + returns).cumprod()

            # Calculate metrics
            ann_return = (equity.iloc[-1]) ** (252 / len(equity)) - 1
            running_max = equity.cummax()
            drawdowns = equity / running_max - 1
            max_dd = abs(drawdowns.min())
            calmar = ann_return / max_dd if max_dd > 0 else 0.0
            vol = returns.std() * np.sqrt(252)
            sharpe = ann_return / vol if vol > 0 else 0.0
            total_ret = equity.iloc[-1] - 1
            win_rate = sum(1 for r in trade_returns if r > 0) / max(len(trade_returns), 1)

            # Crisis returns
            crisis_returns = {}
            for name, (c_start, c_end) in CRISIS_PERIODS.items():
                mask = (returns.index >= pd.Timestamp(c_start)) & (returns.index <= pd.Timestamp(c_end))
                crisis_rets = returns[mask]
                if len(crisis_rets) > 0:
                    crisis_returns[name] = (1 + crisis_rets).prod() - 1

            return BacktestResult(
                strategy_name=f"Momentum_{lookback_months}m_top{top_n}_stop{int(stop_loss*100)}pct",
                start_date=str(returns.index[0].date()),
                end_date=str(returns.index[-1].date()),
                annualized_return=ann_return,
                max_drawdown=max_dd,
                calmar_ratio=calmar,
                sharpe_ratio=sharpe,
                total_return=total_ret,
                volatility=vol,
                num_trades=len(trade_returns),
                win_rate=win_rate,
                crisis_returns=crisis_returns,
                is_real=True,
            )

        except Exception as e:
            print(f"[RealBacktest] Error: {e}")
            import traceback
            traceback.print_exc()
            return None
