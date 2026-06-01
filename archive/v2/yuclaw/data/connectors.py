"""yuclaw/data/connectors.py — Free data sources, no API key required."""
from __future__ import annotations
import asyncio
from pathlib import Path
import httpx
import yfinance as yf


EDGAR_HEADERS = {
    "User-Agent": "YUCLAW Research contact@yuclaw.io",
    "Accept-Encoding": "gzip"
}


class EDGARConnector:
    def __init__(self, cache_dir: str = "data/filings"):
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self._cache = Path(cache_dir)
        self._client = httpx.AsyncClient(headers=EDGAR_HEADERS, timeout=30.0)

    async def get_10k_text(self, ticker: str) -> tuple[str, str] | None:
        """Returns (text, doc_id) or None. Caches locally."""
        await asyncio.sleep(0.12)  # Respect SEC 10 req/sec limit
        try:
            r = await self._client.get(
                f"https://data.sec.gov/submissions/CIK{ticker.upper().zfill(10)}.json"
            )
            if r.status_code != 200:
                return None
            data    = r.json()
            cik     = data.get("cik", "")
            filings = data.get("filings", {}).get("recent", {})
            forms   = filings.get("form", [])

            for i, form in enumerate(forms):
                if form == "10-K":
                    date    = filings["filingDate"][i]
                    acc     = filings["accessionNumber"][i].replace("-", "")
                    doc_id  = f"{ticker.upper()}_10K_{date}"
                    cached  = self._cache / f"{doc_id}.txt"

                    if cached.exists():
                        return cached.read_text(errors="ignore"), doc_id

                    primary = filings.get("primaryDocument", [""])[i]
                    url     = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{primary}"
                    await asyncio.sleep(0.12)
                    doc_r = await self._client.get(url)
                    if doc_r.status_code == 200:
                        text = doc_r.text
                        cached.write_text(text, errors="ignore")
                        return text, doc_id
        except Exception as e:
            print(f"[EDGAR] Error for {ticker}: {e}")
        return None

    async def close(self):
        await self._client.aclose()


class YahooFinanceConnector:
    def get_snapshot(self, ticker: str) -> dict:
        try:
            info = yf.Ticker(ticker).info
            return {
                "ticker":       ticker.upper(),
                "price":        info.get("currentPrice", 0.0),
                "market_cap":   info.get("marketCap"),
                "pe_ratio":     info.get("trailingPE"),
                "revenue_ttm":  info.get("totalRevenue"),
                "gross_margin": info.get("grossMargins"),
                "ebitda":       info.get("ebitda"),
                "fcf":          info.get("freeCashflow"),
                "short_name":   info.get("shortName", ticker),
                "sector":       info.get("sector", "Unknown"),
                "industry":     info.get("industry", "Unknown"),
            }
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    def get_history(self, ticker: str, period: str = "1y"):
        try:
            return yf.Ticker(ticker).history(period=period)
        except Exception:
            return None
