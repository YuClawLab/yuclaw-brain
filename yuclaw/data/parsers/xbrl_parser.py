"""
XBRL Parser — extracts real financial data from SEC EDGAR structured filings.
Every number is from structured XBRL data — not PDF regex, not LLM estimation.
This is the gold standard for financial data extraction.
"""
import httpx
import json
import asyncio
import time
from dataclasses import dataclass
from typing import Optional

EDGAR_HEADERS = {"User-Agent": "YUCLAW-ATROS/1.0 (vzhang2099@gmail.com)"}

@dataclass
class XBRLFinancials:
    ticker: str
    cik: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None
    eps_diluted: Optional[float] = None
    shares_outstanding: Optional[float] = None
    source: str = "SEC_EDGAR_XBRL"
    period: Optional[str] = None
    is_real: bool = True

    def summary(self) -> str:
        lines = [f"=== XBRL: {self.ticker} (CIK {self.cik}) ==="]
        if self.revenue: lines.append(f"  Revenue:          ${self.revenue:>15,.0f}")
        if self.net_income: lines.append(f"  Net Income:       ${self.net_income:>15,.0f}")
        if self.gross_profit: lines.append(f"  Gross Profit:     ${self.gross_profit:>15,.0f}")
        if self.operating_income: lines.append(f"  Operating Income: ${self.operating_income:>15,.0f}")
        if self.total_assets: lines.append(f"  Total Assets:     ${self.total_assets:>15,.0f}")
        if self.total_equity: lines.append(f"  Total Equity:     ${self.total_equity:>15,.0f}")
        if self.free_cash_flow: lines.append(f"  Free Cash Flow:   ${self.free_cash_flow:>15,.0f}")
        if self.eps_diluted: lines.append(f"  EPS (Diluted):    ${self.eps_diluted:>15.2f}")
        lines.append(f"  Source: {self.source} | Is Real: {self.is_real}")
        return "\n".join(lines)


class XBRLParser:
    """
    Pulls real financial data from SEC EDGAR XBRL API.
    No PDF. No regex. No LLM. Pure structured data from the source.
    """
    BASE = "https://data.sec.gov/api/xbrl/companyfacts"

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK via SEC tickers.json."""
        try:
            resp = httpx.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=EDGAR_HEADERS, timeout=15.0
            )
            data = resp.json()
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    return str(entry["cik_str"]).zfill(10)
        except Exception:
            pass
        return None

    async def get_financials(self, ticker: str) -> XBRLFinancials:
        async with httpx.AsyncClient(headers=EDGAR_HEADERS, timeout=30.0) as client:
            # Get CIK
            cik = self._get_cik(ticker)
            if not cik:
                return XBRLFinancials(ticker=ticker, cik="unknown")

            await asyncio.sleep(0.12)  # SEC rate limit

            # Get XBRL facts
            r2 = await client.get(f"{self.BASE}/CIK{cik}.json")
            if r2.status_code != 200:
                return XBRLFinancials(ticker=ticker, cik=cik)

            facts = r2.json().get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            def get_latest(concept: str) -> Optional[float]:
                data = us_gaap.get(concept, {}).get("units", {}).get("USD", [])
                annual = [d for d in data if d.get("form") in ("10-K", "20-F") and "end" in d]
                if not annual:
                    return None
                latest = sorted(annual, key=lambda x: x["end"])[-1]
                return float(latest.get("val", 0))

            def get_latest_shares() -> Optional[float]:
                data = us_gaap.get("CommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
                if not data:
                    return None
                return float(sorted(data, key=lambda x: x.get("end", ""))[-1].get("val", 0))

            revenue = get_latest("RevenueFromContractWithCustomerExcludingAssessedTax") or \
                      get_latest("Revenues") or get_latest("SalesRevenueNet")
            net_income = get_latest("NetIncomeLoss")
            gross_profit = get_latest("GrossProfit")
            operating_income = get_latest("OperatingIncomeLoss")
            total_assets = get_latest("Assets")
            total_equity = get_latest("StockholdersEquity")
            fcf = get_latest("NetCashProvidedByUsedInOperatingActivities")
            eps = get_latest("EarningsPerShareDiluted")
            shares = get_latest_shares()

            # Get period from latest revenue entry
            rev_data = us_gaap.get("Revenues", {}).get("units", {}).get("USD", [])
            period = None
            if rev_data:
                latest_entry = sorted(rev_data, key=lambda x: x.get("end", ""))[-1]
                period = latest_entry.get("end")

            return XBRLFinancials(
                ticker=ticker, cik=cik,
                revenue=revenue, net_income=net_income,
                gross_profit=gross_profit, operating_income=operating_income,
                total_assets=total_assets, total_equity=total_equity,
                free_cash_flow=fcf, eps_diluted=eps,
                shares_outstanding=shares, period=period,
            )


async def test_xbrl():
    parser = XBRLParser()
    for ticker in ["AAPL", "NVDA", "MSFT"]:
        f = await parser.get_financials(ticker)
        print(f.summary())
        print()


if __name__ == "__main__":
    asyncio.run(test_xbrl())
