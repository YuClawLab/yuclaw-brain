"""Sector Rotation Model — real momentum-based sector signals."""
import yfinance as yf
from dataclasses import dataclass

SECTORS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE",
    "Healthcare": "XLV", "Industrials": "XLI", "Materials": "XLB",
    "Utilities": "XLU", "ConsumerStaples": "XLP", "ConsumerDisc": "XLY",
    "Communication": "XLC",
}

@dataclass
class SectorSignal:
    sector: str
    etf: str
    momentum_1m: float
    momentum_3m: float
    relative_strength: float
    signal: str
    rank: int


class SectorRotationModel:
    def analyze(self) -> list[SectorSignal]:
        etfs = list(SECTORS.values())
        prices = yf.download(etfs, period="6mo", progress=False, auto_adjust=True)["Close"].dropna()
        spy = yf.Ticker("SPY").history(period="6mo")["Close"]
        spy_m3 = float(spy.iloc[-1] / spy.iloc[-66] - 1) if len(spy) >= 66 else 0

        signals = []
        for sector, etf in SECTORS.items():
            if etf not in prices.columns:
                continue
            p = prices[etf]
            m1 = float(p.iloc[-1] / p.iloc[-22] - 1) if len(p) >= 22 else 0
            m3 = float(p.iloc[-1] / p.iloc[-66] - 1) if len(p) >= 66 else 0
            rs = m3 - spy_m3
            sig = ("OVERWEIGHT" if m1 > 0.02 and rs > 0 else
                   "UNDERWEIGHT" if m1 < -0.02 and rs < 0 else "NEUTRAL")
            signals.append(SectorSignal(
                sector=sector, etf=etf, momentum_1m=m1,
                momentum_3m=m3, relative_strength=rs, signal=sig, rank=0,
            ))
        signals.sort(key=lambda x: x.momentum_1m, reverse=True)
        for i, s in enumerate(signals):
            s.rank = i + 1
        return signals


if __name__ == "__main__":
    print("=== SECTOR ROTATION ===")
    for s in SectorRotationModel().analyze():
        print(f"  {s.rank}. {s.sector:20} {s.signal:12} Mom1m:{s.momentum_1m:+.1%} RS:{s.relative_strength:+.1%}")
