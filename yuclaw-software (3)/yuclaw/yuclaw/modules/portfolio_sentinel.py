"""
yuclaw/modules/portfolio_sentinel.py

Portfolio Sentinel — continuous monitoring of your holdings.
Checks thesis integrity, consensus drift, catalysts, risk exposure.
Proactively flags when new evidence contradicts your investment assumptions.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
import yfinance as yf
from ..core.router import get_router
from ..memory.portfolio_memory import PortfolioMemory


SENTINEL_SYSTEM = """You are the YUCLAW Portfolio Sentinel. Monitor portfolio positions and flag issues.
Given a position's thesis, assumptions, and current market data, identify:
- Which assumptions have been strengthened by recent data
- Which assumptions have been weakened or falsified
- Upcoming catalysts to watch
- Risk level change
Output JSON only:
{
  "ticker": str,
  "thesis_integrity": "strong|moderate|weakened|under_threat",
  "overall_alert_level": "clear|watch|warning|critical",
  "strengthened_assumptions": [str],
  "weakened_assumptions": [{"assumption": str, "new_evidence": str}],
  "falsified_assumptions": [{"assumption": str, "evidence": str}],
  "upcoming_catalysts": [{"event": str, "timeframe": str, "direction": "positive|negative|uncertain"}],
  "risk_changes": [str],
  "recommended_action": "hold|review|reduce|exit|add",
  "one_line_summary": str
}
JSON only. No preamble."""


class PortfolioSentinel:
    def __init__(self, portfolio_memory: PortfolioMemory):
        self._router  = get_router()
        self._memory  = portfolio_memory

    async def check_position(self, ticker: str) -> dict:
        """Check a single position for thesis integrity."""
        history = await self._memory.get_history(ticker)
        if not history:
            return {"ticker": ticker, "error": "No thesis in Portfolio Memory. Run research first."}

        latest = history[0]

        # Get current market data
        try:
            info = yf.Ticker(ticker).info
            market_data = {
                "price":            info.get("currentPrice"),
                "52w_high":         info.get("fiftyTwoWeekHigh"),
                "52w_low":          info.get("fiftyTwoWeekLow"),
                "revenue_growth":   info.get("revenueGrowth"),
                "earnings_growth":  info.get("earningsGrowth"),
                "pe_ratio":         info.get("trailingPE"),
                "analyst_target":   info.get("targetMeanPrice"),
                "recommendation":   info.get("recommendationMean"),
                "short_ratio":      info.get("shortRatio"),
            }
        except Exception:
            market_data = {}

        prompt = (
            f"TICKER: {ticker.upper()}\n\n"
            f"ORIGINAL THESIS:\n{latest.thesis}\n\n"
            f"KEY ASSUMPTIONS:\n{json.dumps(latest.key_assumptions, indent=2)}\n\n"
            f"THESIS STATUS: {latest.status}\n"
            f"THESIS DATE: {latest.created_at[:10]}\n\n"
            f"CURRENT MARKET DATA:\n{json.dumps(market_data, indent=2)}\n\n"
            f"PRIOR FALSIFICATION FLAGS:\n{json.dumps(latest.falsified_by, indent=2)}\n\n"
            f"Assess thesis integrity. Flag any assumptions that have been weakened or falsified by current data."
        )

        response = await self._router.complete(
            prompt=prompt, system=SENTINEL_SYSTEM, max_tokens=3000
        )

        try:
            result = json.loads(response)
        except Exception:
            result = {"ticker": ticker, "raw": response, "error": "parse_failed"}

        # Auto-flag falsified assumptions in Portfolio Memory
        for falsified in result.get("falsified_assumptions", []):
            await self._memory.flag_falsified(
                ticker=ticker,
                assumption=falsified.get("assumption", ""),
                new_evidence=falsified.get("evidence", "")
            )

        result["ticker"]           = ticker.upper()
        result["thesis_date"]      = latest.created_at[:10]
        result["thesis_status"]    = latest.status
        result["market_data"]      = market_data
        result["checked_at"]       = datetime.now(timezone.utc).isoformat()
        return result

    async def scan_watchlist(self, tickers: list[str]) -> list[dict]:
        """Scan all watchlist tickers and return prioritized alerts."""
        results = []
        for ticker in tickers:
            print(f"  Scanning {ticker}...")
            r = await self.check_position(ticker)
            results.append(r)

        # Sort by alert level
        priority = {"critical": 0, "warning": 1, "watch": 2, "clear": 3}
        results.sort(key=lambda x: priority.get(x.get("overall_alert_level", "clear"), 4))
        return results

    def format_alert(self, result: dict) -> str:
        alert = result.get("overall_alert_level", "unknown").upper()
        icons = {"CRITICAL": "🚨", "WARNING": "⚠️", "WATCH": "👁️", "CLEAR": "✅"}
        icon  = icons.get(alert, "❓")
        lines = [
            f"  {icon} {result.get('ticker','?'):8} [{alert:8}]  {result.get('one_line_summary','')}",
            f"           Thesis: {result.get('thesis_integrity','?')}  |  Action: {result.get('recommended_action','?').upper()}",
        ]
        if result.get("falsified_assumptions"):
            lines.append(f"           ❌ Falsified: {result['falsified_assumptions'][0].get('assumption','')[:60]}")
        if result.get("upcoming_catalysts"):
            cat = result["upcoming_catalysts"][0]
            lines.append(f"           📅 Catalyst: {cat.get('event','')} ({cat.get('timeframe','')})")
        return "\n".join(lines)
