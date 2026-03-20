"""
Factor Library — real quantitative factors from actual price history.
No LLM estimation. Every factor calculated from real market data.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from dataclasses import dataclass
from typing import Optional


@dataclass
class FactorScores:
    ticker: str
    momentum_1m: Optional[float] = None
    momentum_3m: Optional[float] = None
    momentum_6m: Optional[float] = None
    momentum_12m: Optional[float] = None
    mean_reversion_20d: Optional[float] = None
    volatility_30d: Optional[float] = None
    volatility_90d: Optional[float] = None
    rsi_14: Optional[float] = None
    volume_momentum: Optional[float] = None
    sharpe_90d: Optional[float] = None
    max_drawdown_90d: Optional[float] = None
    calmar_90d: Optional[float] = None
    composite_score: Optional[float] = None
    signal: Optional[str] = None
    is_real: bool = True


class FactorLibrary:
    """Calculates 12 real quantitative factors from price history."""

    def calculate(self, ticker: str, period: str = "1y") -> FactorScores:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty or len(hist) < 30:
                return FactorScores(ticker=ticker, is_real=False)

            close = hist["Close"]
            volume = hist["Volume"]
            returns = close.pct_change().dropna()

            mom_1m = (close.iloc[-1] / close.iloc[-22] - 1) if len(close) >= 22 else None
            mom_3m = (close.iloc[-1] / close.iloc[-66] - 1) if len(close) >= 66 else None
            mom_6m = (close.iloc[-1] / close.iloc[-132] - 1) if len(close) >= 132 else None
            mom_12m = (close.iloc[-1] / close.iloc[-252] - 1) if len(close) >= 252 else None

            ret_20 = returns.tail(20)
            mean_rev = (returns.iloc[-1] - ret_20.mean()) / ret_20.std() if ret_20.std() > 0 else None

            vol_30 = returns.tail(30).std() * np.sqrt(252) if len(returns) >= 30 else None
            vol_90 = returns.tail(90).std() * np.sqrt(252) if len(returns) >= 90 else None

            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - 100 / (1 + rs)).iloc[-1]) if not rs.empty else None

            vol_ratio = float(volume.tail(5).mean() / volume.tail(20).mean()) if len(volume) >= 20 else None

            ret_90 = returns.tail(90)
            sharpe_90 = float(ret_90.mean() / ret_90.std() * np.sqrt(252)) if len(ret_90) >= 30 and ret_90.std() > 0 else None

            prices_90 = close.tail(90)
            roll_max = prices_90.cummax()
            dd_90 = float(((prices_90 - roll_max) / roll_max).min())
            ann_ret_90 = float(ret_90.mean() * 252) if len(ret_90) >= 30 else 0
            calmar_90 = ann_ret_90 / abs(dd_90) if dd_90 != 0 else None

            scores = []
            if mom_1m is not None: scores.append(min(max(mom_1m * 10, -1), 1))
            if mom_3m is not None: scores.append(min(max(mom_3m * 5, -1), 1))
            if mom_6m is not None: scores.append(min(max(mom_6m * 3, -1), 1))
            if sharpe_90 is not None: scores.append(min(max(sharpe_90 / 3, -1), 1))
            composite = float(np.mean(scores)) if scores else None

            signal = ("STRONG_BUY" if composite and composite > 0.5 else
                      "BUY" if composite and composite > 0.2 else
                      "HOLD" if composite and composite > -0.2 else
                      "SELL" if composite and composite > -0.5 else
                      "STRONG_SELL" if composite else "UNKNOWN")

            return FactorScores(
                ticker=ticker,
                momentum_1m=float(mom_1m) if mom_1m is not None else None,
                momentum_3m=float(mom_3m) if mom_3m is not None else None,
                momentum_6m=float(mom_6m) if mom_6m is not None else None,
                momentum_12m=float(mom_12m) if mom_12m is not None else None,
                mean_reversion_20d=float(mean_rev) if mean_rev is not None else None,
                volatility_30d=float(vol_30) if vol_30 is not None else None,
                volatility_90d=float(vol_90) if vol_90 is not None else None,
                rsi_14=rsi, volume_momentum=float(vol_ratio) if vol_ratio is not None else None,
                sharpe_90d=sharpe_90, max_drawdown_90d=dd_90, calmar_90d=calmar_90,
                composite_score=composite, signal=signal, is_real=True,
            )
        except Exception:
            return FactorScores(ticker=ticker, is_real=False)

    def scan_universe(self, tickers: list[str]) -> list[FactorScores]:
        results = []
        for ticker in tickers:
            score = self.calculate(ticker)
            results.append(score)
            if score.composite_score is not None and score.momentum_1m is not None:
                print(f"{ticker:6} | {score.signal:12} | Comp:{score.composite_score:+.2f} | Mom1m:{score.momentum_1m:+.1%}")
        return sorted(results, key=lambda x: x.composite_score or -99, reverse=True)
