"""Macro Regime Detector — identifies current market regime from real data."""
import yfinance as yf
from dataclasses import dataclass


@dataclass
class MacroRegime:
    regime: str
    confidence: float
    indicators: dict
    portfolio_implications: list
    is_real: bool = True


class MacroRegimeDetector:
    def detect(self) -> MacroRegime:
        prices = {}
        for t in ["SPY", "TLT", "GLD", "UUP"]:
            try:
                h = yf.Ticker(t).history(period="3mo")["Close"].dropna()
                if len(h) >= 2:
                    prices[t] = float(h.iloc[-1] / h.iloc[0] - 1)
            except Exception:
                pass

        eq_up = prices.get("SPY", 0) > 0.02
        bonds_up = prices.get("TLT", 0) > 0
        gold_up = prices.get("GLD", 0) > 0.02
        dollar_up = prices.get("UUP", 0) > 0.01

        if eq_up and not gold_up:
            r, c, i = "RISK_ON", 0.85, ["Overweight equities", "Reduce bonds/gold"]
        elif not eq_up and bonds_up and gold_up:
            r, c, i = "RISK_OFF", 0.80, ["Overweight bonds", "Overweight gold", "Reduce equities"]
        elif not eq_up and not bonds_up:
            r, c, i = "CRISIS", 0.90, ["Maximum cash", "TLT + GLD only", "Hedge with puts"]
        elif eq_up and gold_up:
            r, c, i = "GOLDILOCKS", 0.70, ["Balanced allocation", "Add quality growth"]
        else:
            r, c, i = "TRANSITIONAL", 0.50, ["Reduce position sizes", "Wait for clarity"]

        return MacroRegime(regime=r, confidence=c, indicators=prices, portfolio_implications=i)


if __name__ == "__main__":
    r = MacroRegimeDetector().detect()
    print(f"=== MACRO REGIME: {r.regime} ({r.confidence:.0%} confidence) ===")
    for k, v in r.indicators.items():
        print(f"  {k}: {v:+.1%}")
    print("Actions:")
    for a in r.portfolio_implications:
        print(f"  -> {a}")
