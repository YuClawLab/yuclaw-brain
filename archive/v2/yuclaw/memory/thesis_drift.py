"""
yuclaw/memory/thesis_drift.py — Detects drift between thesis and reality using real data.

Compares original investment assumptions against current price and fundamental
metrics from yfinance. No LLM needed — pure data comparison.
"""
import yfinance as yf
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DriftReport:
    ticker: str
    days_since_thesis: int
    original_price: Optional[float]
    current_price: Optional[float]
    price_change: Optional[float]
    strengthened: list = field(default_factory=list)
    weakened: list = field(default_factory=list)
    falsified: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    conviction_change: str = "unchanged"
    action_required: str = "hold"
    is_real: bool = True

    def summary(self) -> str:
        lines = [
            f"{'='*60}",
            f"THESIS DRIFT REPORT — {self.ticker}",
            f"Days since thesis: {self.days_since_thesis}",
        ]
        if self.original_price and self.current_price:
            lines.append(f"Price: ${self.original_price:.2f} -> ${self.current_price:.2f} ({self.price_change:+.1%})")
        lines.append(f"Conviction: {self.conviction_change.upper()}")
        lines.append(f"Action: {self.action_required.upper()}")
        if self.strengthened:
            lines.append(f"\nSTRENGTHENED ({len(self.strengthened)}):")
            for s in self.strengthened:
                lines.append(f"  + {s}")
        if self.weakened:
            lines.append(f"\nWEAKENED ({len(self.weakened)}):")
            for s in self.weakened:
                lines.append(f"  ~ {s}")
        if self.falsified:
            lines.append(f"\nFALSIFIED ({len(self.falsified)}):")
            for s in self.falsified:
                lines.append(f"  X {s}")
        if self.unchanged:
            lines.append(f"\nUNCHANGED ({len(self.unchanged)}):")
            for s in self.unchanged:
                lines.append(f"  = {s}")
        lines.append("=" * 60)
        return "\n".join(lines)


class ThesisDriftDetector:
    """Detects drift between thesis and current reality using real data."""

    def detect(
        self,
        ticker: str,
        original_assumptions: list,
        original_price: float,
        days_elapsed: int,
    ) -> DriftReport:
        strengthened, weakened, falsified, unchanged = [], [], [], []

        try:
            info = yf.Ticker(ticker).info
            current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
            price_change = (current_price - original_price) / original_price if original_price else 0
            revenue_growth = info.get("revenueGrowth") or 0
            gross_margin = info.get("grossMargins") or 0
            pe_ratio = info.get("forwardPE") or 0
        except Exception:
            current_price = price_change = revenue_growth = gross_margin = pe_ratio = 0

        for assumption in original_assumptions:
            a = assumption.lower()

            if any(w in a for w in ["growth", "revenue", "expanding"]):
                if revenue_growth > 0.10:
                    strengthened.append(f"{assumption} — confirmed (rev growth {revenue_growth:.1%})")
                elif revenue_growth > 0:
                    unchanged.append(f"{assumption} — modest growth {revenue_growth:.1%}")
                elif revenue_growth < -0.05:
                    falsified.append(f"{assumption} — FALSIFIED (rev declined {revenue_growth:.1%})")
                else:
                    weakened.append(f"{assumption} — weakening (flat revenue)")

            elif any(w in a for w in ["margin", "profitability", "profit"]):
                if gross_margin > 0.50:
                    strengthened.append(f"{assumption} — confirmed (GM {gross_margin:.1%})")
                elif gross_margin > 0.35:
                    unchanged.append(f"{assumption} — acceptable (GM {gross_margin:.1%})")
                else:
                    weakened.append(f"{assumption} — below target (GM {gross_margin:.1%})")

            elif any(w in a for w in ["valuation", "cheap", "undervalued"]):
                if pe_ratio and pe_ratio < 20:
                    strengthened.append(f"{assumption} — confirmed (PE {pe_ratio:.1f}x)")
                elif pe_ratio and pe_ratio > 40:
                    falsified.append(f"{assumption} — FALSIFIED (PE {pe_ratio:.1f}x)")
                else:
                    unchanged.append(f"{assumption} — neutral valuation")

            elif any(w in a for w in ["price", "momentum", "uptrend"]):
                if price_change > 0.10:
                    strengthened.append(f"{assumption} — confirmed (+{price_change:.1%})")
                elif price_change < -0.20:
                    falsified.append(f"{assumption} — FALSIFIED ({price_change:.1%} decline)")
                elif price_change < 0:
                    weakened.append(f"{assumption} — under pressure {price_change:.1%}")
                else:
                    unchanged.append(f"{assumption} — small gain +{price_change:.1%}")
            else:
                unchanged.append(f"{assumption} — no new data")

        if falsified:
            conviction, action = "falsified", "exit"
        elif len(weakened) > len(strengthened):
            conviction, action = "weakened", "reduce"
        elif len(strengthened) > len(weakened):
            conviction, action = "strengthened", "add"
        else:
            conviction, action = "unchanged", "hold"

        return DriftReport(
            ticker=ticker, days_since_thesis=days_elapsed,
            original_price=original_price, current_price=current_price,
            price_change=round(price_change, 4) if price_change else None,
            strengthened=strengthened, weakened=weakened,
            falsified=falsified, unchanged=unchanged,
            conviction_change=conviction, action_required=action,
        )
