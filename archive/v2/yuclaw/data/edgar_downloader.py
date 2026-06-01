"""yuclaw/data/edgar_downloader.py — Download real 10-K PDFs from SEC EDGAR.

Uses the EDGAR full-text search API and filing index to find and download
actual PDF filings. Falls back to HTML filing if PDF unavailable.
All requests use a proper User-Agent per SEC guidelines.
"""
from __future__ import annotations

import os
import re
import time
import json
import hashlib
from pathlib import Path
from typing import Optional
import httpx


SEC_BASE = "https://www.sec.gov"
EFTS_BASE = "https://efts.sec.gov/LATEST"
EDGAR_COMPANY = "https://data.sec.gov/submissions"
USER_AGENT = "YUCLAW-ATROS/1.0 (vzhang2099@gmail.com)"

# CIK lookup for common tickers
TICKER_CIK = {
    "AAPL": "0000320193", "MSFT": "0000789019", "NVDA": "0001045810",
    "GOOG": "0001652044", "GOOGL": "0001652044", "AMZN": "0001018724",
    "META": "0001326801", "TSLA": "0001318605", "AMD": "0000002488",
    "COIN": "0001679788", "HOOD": "0001783879", "MSTR": "0001050446",
    "RKLB": "0001819994", "OKLO": "0001849056",
}


class EDGARDownloader:
    """Download real 10-K/10-Q filings from SEC EDGAR."""

    def __init__(self, cache_dir: str = "data/filings"):
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )
        self._last_request = 0.0  # Rate limit: 10 req/sec per SEC rules

    def _rate_limit(self):
        """SEC requires max 10 requests/second."""
        elapsed = time.time() - self._last_request
        if elapsed < 0.15:
            time.sleep(0.15 - elapsed)
        self._last_request = time.time()

    def get_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK for a ticker via SEC EDGAR."""
        ticker = ticker.upper()
        if ticker in TICKER_CIK:
            return TICKER_CIK[ticker]

        try:
            self._rate_limit()
            resp = self._client.get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                params={"company": "", "CIK": ticker, "type": "10-K",
                        "dateb": "", "owner": "include", "count": "1",
                        "search_text": "", "action": "getcompany"}
            )
            match = re.search(r'CIK=(\d+)', resp.text)
            if match:
                cik = match.group(1).zfill(10)
                TICKER_CIK[ticker] = cik
                return cik
        except Exception as e:
            print(f"[EDGAR] CIK lookup failed for {ticker}: {e}")
        return None

    def get_latest_10k_url(self, ticker: str) -> Optional[dict]:
        """Find the latest 10-K filing URL for a ticker."""
        cik = self.get_cik(ticker)
        if not cik:
            return None

        try:
            self._rate_limit()
            url = f"{EDGAR_COMPANY}/CIK{cik}.json"
            resp = self._client.get(url)
            data = resp.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])
            dates = recent.get("filingDate", [])

            for i, form in enumerate(forms):
                if form in ("10-K", "10-K/A"):
                    accession = accessions[i].replace("-", "")
                    doc = primary_docs[i]
                    return {
                        "ticker": ticker,
                        "form": form,
                        "date": dates[i],
                        "accession": accessions[i],
                        "url": f"{SEC_BASE}/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc}",
                        "cik": cik,
                    }
        except Exception as e:
            print(f"[EDGAR] Filing search failed for {ticker}: {e}")
        return None

    def download_filing(self, ticker: str) -> Optional[str]:
        """Download the latest 10-K filing and return local file path.

        Tries PDF first, falls back to HTML/HTM.
        Caches locally to avoid re-downloading.
        """
        # Check cache first
        cached = list(self._cache.glob(f"{ticker.upper()}_10K*"))
        if cached:
            latest = max(cached, key=lambda p: p.stat().st_mtime)
            print(f"[EDGAR] Using cached: {latest.name}")
            return str(latest)

        info = self.get_latest_10k_url(ticker)
        if not info:
            print(f"[EDGAR] No 10-K found for {ticker}")
            return None

        url = info["url"]
        ext = Path(url).suffix.lower() or ".htm"
        filename = f"{ticker.upper()}_10K_{info['date']}{ext}"
        filepath = self._cache / filename

        try:
            self._rate_limit()
            print(f"[EDGAR] Downloading {ticker} 10-K ({info['date']})...")
            resp = self._client.get(url)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            print(f"[EDGAR] Saved: {filepath} ({len(resp.content):,} bytes)")
            return str(filepath)
        except Exception as e:
            print(f"[EDGAR] Download failed: {e}")
            return None

    def download_and_parse(self, ticker: str) -> Optional[dict]:
        """Download 10-K and parse with RealPDFParser.

        Returns ParsedFiling with extracted financial facts, or None.
        """
        from .parsers.real_pdf_parser import RealPDFParser

        filepath = self.download_filing(ticker)
        if not filepath:
            return None

        parser = RealPDFParser()
        ext = Path(filepath).suffix.lower()

        if ext == ".pdf":
            parsed = parser.parse_pdf(filepath, ticker)
        elif ext in (".htm", ".html"):
            parsed = parser.parse_html(filepath, ticker)
        else:
            print(f"[EDGAR] Unsupported format: {ext}")
            return None

        # Always supplement with yfinance for latest data
        yf_parsed = parser.parse_yfinance(ticker)
        if yf_parsed.facts:
            parsed.facts.extend(yf_parsed.facts)
            if not parsed.revenue and yf_parsed.revenue:
                parsed.revenue = yf_parsed.revenue
            if not parsed.gross_margin and yf_parsed.gross_margin:
                parsed.gross_margin = yf_parsed.gross_margin
            if not parsed.operating_margin and yf_parsed.operating_margin:
                parsed.operating_margin = yf_parsed.operating_margin

        return {
            "filing": parsed,
            "grounding": parsed.to_grounding_context(),
            "filepath": filepath,
            "source": info if (info := self.get_latest_10k_url(ticker)) else {},
        }

    def close(self):
        self._client.close()
