"""yuclaw/data/parsers/real_pdf_parser.py — Extract real financial facts from SEC filings.

Parses 10-K/10-Q PDFs and HTML filings to extract structured financial data:
revenue, margins, segment breakdowns, risk factors, and key metrics.
Uses regex pattern matching on real EDGAR documents — no LLM hallucination.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FinancialFact:
    """A single verified fact extracted from a filing."""
    metric: str
    value: str
    period: str
    page: int
    source: str  # "10-K", "10-Q", "yfinance"
    confidence: float = 1.0


@dataclass
class ParsedFiling:
    """Structured output from parsing a financial filing."""
    ticker: str
    filing_type: str
    facts: list[FinancialFact] = field(default_factory=list)
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    total_assets: Optional[float] = None
    total_debt: Optional[float] = None
    risk_factors: list[str] = field(default_factory=list)
    segments: dict[str, float] = field(default_factory=dict)
    raw_text: str = ""

    def to_grounding_context(self) -> str:
        """Format as grounding context for the LLM prompt."""
        lines = [f"=== VERIFIED FINANCIAL DATA FOR {self.ticker} ==="]
        lines.append(f"Source: {self.filing_type} (parsed from EDGAR)")
        lines.append("")

        if self.revenue:
            lines.append(f"Revenue: ${self.revenue:,.0f}")
        if self.net_income:
            lines.append(f"Net Income: ${self.net_income:,.0f}")
        if self.gross_margin:
            lines.append(f"Gross Margin: {self.gross_margin:.1%}")
        if self.operating_margin:
            lines.append(f"Operating Margin: {self.operating_margin:.1%}")
        if self.total_assets:
            lines.append(f"Total Assets: ${self.total_assets:,.0f}")
        if self.total_debt:
            lines.append(f"Total Debt: ${self.total_debt:,.0f}")

        if self.segments:
            lines.append("\nSegment Revenue:")
            for seg, val in self.segments.items():
                lines.append(f"  {seg}: ${val:,.0f}")

        if self.facts:
            lines.append(f"\nExtracted Facts ({len(self.facts)}):")
            for f in self.facts[:20]:
                lines.append(f"  [{f.source} p.{f.page}] {f.metric}: {f.value} ({f.period})")

        if self.risk_factors:
            lines.append(f"\nKey Risk Factors ({len(self.risk_factors)}):")
            for r in self.risk_factors[:5]:
                lines.append(f"  - {r[:150]}")

        lines.append("\n=== END VERIFIED DATA ===")
        lines.append("IMPORTANT: Use these real numbers. Do NOT estimate or hallucinate financial figures.")
        return "\n".join(lines)


class RealPDFParser:
    """Parse real SEC filings (PDF or HTML) into structured financial data."""

    # Regex patterns for common financial line items
    MONEY_PATTERN = re.compile(
        r'[\$]?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion|thousand)?',
        re.IGNORECASE
    )
    PERCENT_PATTERN = re.compile(r'([\d]+(?:\.\d+)?)\s*%')

    REVENUE_PATTERNS = [
        re.compile(r'(?:total\s+)?(?:net\s+)?revenue[s]?\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', re.I),
        re.compile(r'(?:total\s+)?net\s+sales\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', re.I),
    ]
    INCOME_PATTERNS = [
        re.compile(r'net\s+income\s*[\$]?\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', re.I),
    ]
    MARGIN_PATTERNS = [
        re.compile(r'gross\s+margin\s*(?:was|of|:)?\s*([\d]+(?:\.\d+)?)\s*%', re.I),
        re.compile(r'operating\s+margin\s*(?:was|of|:)?\s*([\d]+(?:\.\d+)?)\s*%', re.I),
    ]

    def parse_pdf(self, pdf_path: str, ticker: str) -> ParsedFiling:
        """Parse a PDF filing using PyMuPDF."""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text_pages = []
            for i, page in enumerate(doc):
                text_pages.append((i + 1, page.get_text()))
            doc.close()
            full_text = "\n".join(t for _, t in text_pages)
            return self._extract(full_text, text_pages, ticker, "10-K")
        except Exception as e:
            print(f"[RealPDFParser] PDF parse error: {e}")
            return ParsedFiling(ticker=ticker, filing_type="10-K")

    def parse_html(self, html_path: str, ticker: str) -> ParsedFiling:
        """Parse an HTML filing from EDGAR."""
        try:
            with open(html_path, 'r', errors='ignore') as f:
                raw = f.read()
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = re.sub(r'\s+', ' ', text)
            return self._extract(text, [(1, text)], ticker, "10-K")
        except Exception as e:
            print(f"[RealPDFParser] HTML parse error: {e}")
            return ParsedFiling(ticker=ticker, filing_type="10-K")

    def parse_yfinance(self, ticker: str) -> ParsedFiling:
        """Extract real financial data from yfinance as fallback."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            info = t.info

            filing = ParsedFiling(ticker=ticker, filing_type="yfinance")
            filing.revenue = info.get("totalRevenue")
            filing.net_income = info.get("netIncomeToCommon")
            filing.gross_margin = info.get("grossMargins")
            filing.operating_margin = info.get("operatingMargins")
            filing.total_assets = info.get("totalAssets")
            filing.total_debt = info.get("totalDebt")

            # Extract facts
            fact_map = {
                "Revenue": "totalRevenue",
                "Net Income": "netIncomeToCommon",
                "Gross Margins": "grossMargins",
                "Operating Margins": "operatingMargins",
                "EBITDA": "ebitda",
                "Free Cash Flow": "freeCashflow",
                "Total Cash": "totalCash",
                "Total Debt": "totalDebt",
                "Current Ratio": "currentRatio",
                "Return on Equity": "returnOnEquity",
                "PE Ratio (Trailing)": "trailingPE",
                "PE Ratio (Forward)": "forwardPE",
                "Price to Book": "priceToBook",
                "Market Cap": "marketCap",
                "Enterprise Value": "enterpriseValue",
                "Profit Margins": "profitMargins",
                "Revenue Growth": "revenueGrowth",
                "Earnings Growth": "earningsGrowth",
                "52 Week High": "fiftyTwoWeekHigh",
                "52 Week Low": "fiftyTwoWeekLow",
                "Dividend Yield": "dividendYield",
                "Beta": "beta",
            }

            for name, key in fact_map.items():
                val = info.get(key)
                if val is not None:
                    if isinstance(val, float) and abs(val) < 1 and "margin" in name.lower() or "ratio" in key.lower() or "growth" in key.lower() or "yield" in key.lower():
                        display = f"{val:.2%}"
                    elif isinstance(val, (int, float)) and abs(val) > 1_000_000:
                        display = f"${val:,.0f}"
                    else:
                        display = str(round(val, 4)) if isinstance(val, float) else str(val)

                    filing.facts.append(FinancialFact(
                        metric=name, value=display,
                        period="TTM", page=0, source="yfinance"
                    ))

            return filing
        except Exception as e:
            print(f"[RealPDFParser] yfinance error: {e}")
            return ParsedFiling(ticker=ticker, filing_type="yfinance")

    def _extract(self, text: str, pages: list[tuple[int, str]],
                 ticker: str, filing_type: str) -> ParsedFiling:
        """Extract structured data from filing text."""
        filing = ParsedFiling(ticker=ticker, filing_type=filing_type, raw_text=text[:100000])
        facts = []

        for page_num, page_text in pages:
            # Revenue
            for pat in self.REVENUE_PATTERNS:
                for m in pat.finditer(page_text):
                    val = float(m.group(1).replace(",", ""))
                    unit = (m.group(2) or "").lower()
                    if unit == "billion":
                        val *= 1_000_000_000
                    elif unit == "million":
                        val *= 1_000_000
                    if filing.revenue is None or val > filing.revenue:
                        filing.revenue = val
                    facts.append(FinancialFact(
                        metric="Revenue", value=f"${val:,.0f}",
                        period="Annual", page=page_num, source=filing_type
                    ))

            # Net Income
            for pat in self.INCOME_PATTERNS:
                for m in pat.finditer(page_text):
                    val = float(m.group(1).replace(",", ""))
                    unit = (m.group(2) or "").lower()
                    if unit == "billion":
                        val *= 1_000_000_000
                    elif unit == "million":
                        val *= 1_000_000
                    filing.net_income = val
                    facts.append(FinancialFact(
                        metric="Net Income", value=f"${val:,.0f}",
                        period="Annual", page=page_num, source=filing_type
                    ))

            # Margins
            for pat in self.MARGIN_PATTERNS:
                for m in pat.finditer(page_text):
                    pct = float(m.group(1)) / 100.0
                    metric = "Gross Margin" if "gross" in pat.pattern else "Operating Margin"
                    if "gross" in pat.pattern:
                        filing.gross_margin = pct
                    else:
                        filing.operating_margin = pct
                    facts.append(FinancialFact(
                        metric=metric, value=f"{pct:.1%}",
                        period="Annual", page=page_num, source=filing_type
                    ))

        # Risk factors
        risk_section = re.search(r'risk\s+factors(.*?)(?:item\s+2|unresolved)', text, re.I | re.S)
        if risk_section:
            risk_text = risk_section.group(1)
            risks = re.split(r'(?:^|\n)\s*[•●▪]\s*|\n\n', risk_text)
            filing.risk_factors = [r.strip()[:200] for r in risks if len(r.strip()) > 30][:10]

        filing.facts = facts[:50]
        return filing
