"""
yuclaw/modules/earnings_war_room.py

Earnings War Room — complete earnings season automation.
Input:  ticker
Output: earnings analysis, management language shifts, consensus vs actual,
        key questions, risk flags — all in your style, delivered before 5:30am.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
import yfinance as yf
from ..core.router import get_router
from ..memory.evidence_graph import EvidenceGraph
from ..core.ontology.models import EvidenceNode


EARNINGS_SYSTEM = """You are the YUCLAW Earnings War Room analyst.
Analyze earnings data thoroughly for investment professionals.
Output JSON only:
{
  "verdict": "beat|miss|in_line",
  "headline": "one sentence key takeaway",
  "revenue": {"actual": str, "consensus": str, "growth_yoy": str, "surprise_pct": str},
  "earnings_per_share": {"actual": str, "consensus": str, "surprise_pct": str},
  "gross_margin": {"actual": str, "prior_quarter": str, "prior_year": str, "trend": "expanding|stable|contracting"},
  "operating_margin": {"actual": str, "trend": str},
  "guidance": {"revenue_next_q": str, "vs_consensus": str, "tone": "raised|maintained|lowered|withdrawn"},
  "management_language": {
    "tone": "bullish|neutral|cautious|defensive",
    "key_phrases": [str],
    "notable_changes_vs_prior": [str]
  },
  "segment_highlights": [{"segment": str, "performance": str, "key_metric": str}],
  "key_concerns": [str],
  "bull_case_strengthened": [str],
  "bear_case_strengthened": [str],
  "key_questions_for_call": [str],
  "one_week_reaction_view": str,
  "evidence_page_refs": [{"claim": str, "page": int}]
}
JSON only. No preamble."""


class EarningsWarRoom:
    def __init__(self, evidence_graph: EvidenceGraph):
        self._router = get_router()
        self._graph  = evidence_graph

    async def analyze(self, ticker: str, doc_text: str = "", doc_id: str = "") -> dict:
        """
        Full earnings analysis pipeline.
        Uses Yahoo Finance for quick data + optional full transcript text.
        """
        # Get Yahoo Finance earnings data
        t = yf.Ticker(ticker)
        info = t.info

        # Build context
        context_parts = []

        # Core financials from Yahoo
        yf_data = {
            "ticker":           ticker.upper(),
            "company":          info.get("shortName", ticker),
            "sector":           info.get("sector", ""),
            "price":            info.get("currentPrice"),
            "revenue_ttm":      info.get("totalRevenue"),
            "gross_margin":     info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "ebitda":           info.get("ebitda"),
            "eps_trailing":     info.get("trailingEps"),
            "eps_forward":      info.get("forwardEps"),
            "pe_trailing":      info.get("trailingPE"),
            "pe_forward":       info.get("forwardPE"),
            "revenue_growth":   info.get("revenueGrowth"),
            "earnings_growth":  info.get("earningsGrowth"),
            "free_cashflow":    info.get("freeCashflow"),
            "analyst_target":   info.get("targetMeanPrice"),
            "recommendation":   info.get("recommendationMean"),
        }
        context_parts.append(f"LIVE MARKET DATA:\n{json.dumps(yf_data, indent=2)}")

        # Try to get recent earnings calendar
        try:
            cal = t.calendar
            if cal is not None and not cal.empty:
                context_parts.append(f"\nEARNINGS CALENDAR:\n{cal.to_string()}")
        except Exception:
            pass

        # Add transcript/filing text if provided
        if doc_text:
            context_parts.append(f"\nEARNINGS DOCUMENT ({doc_id}):\n{doc_text[:40000]}")

        full_context = "\n\n".join(context_parts)

        prompt = (
            f"TICKER: {ticker.upper()}\n\n"
            f"{full_context}\n\n"
            f"Perform comprehensive earnings analysis. Every metric claim must reference page numbers."
        )

        response = await self._router.complete(
            prompt=prompt,
            system=EARNINGS_SYSTEM,
            max_tokens=6144
        )

        try:
            result = json.loads(response)
        except Exception:
            result = {"raw_analysis": response, "ticker": ticker, "error": "parse_failed"}

        # Build Evidence Graph nodes
        now = datetime.now(timezone.utc).isoformat()
        node_ids = []
        for ref in result.get("evidence_page_refs", []):
            node = EvidenceNode(
                claim=ref.get("claim", ""),
                source_doc_id=doc_id or f"{ticker}_earnings_live",
                page_number=max(int(ref.get("page", 1)), 1),
                paragraph_hash=f"earnings_{ticker}_{len(node_ids)}",
                extraction_timestamp=now,
                model_version="nemotron-3-super",
                confidence=0.88,
                ontology_tags=["event:earnings", f"ticker:{ticker.upper()}"]
            )
            nid = await self._graph.add_node(node)
            node_ids.append(nid)

        result["ticker"]           = ticker.upper()
        result["evidence_node_ids"] = node_ids
        result["analyzed_at"]      = now
        return result

    def format_console_output(self, result: dict) -> str:
        lines = [
            f"\n{'═'*60}",
            f"  EARNINGS WAR ROOM — {result.get('ticker','')}",
            f"{'═'*60}",
        ]

        verdict = result.get("verdict", "unknown").upper()
        headline = result.get("headline", "")
        icon = "✅" if verdict == "BEAT" else "❌" if verdict == "MISS" else "➡️"
        lines.append(f"  {icon}  {verdict}  |  {headline}")
        lines.append("")

        rev = result.get("revenue", {})
        if rev:
            lines.append(f"  Revenue:  Actual {rev.get('actual','')}  |  Consensus {rev.get('consensus','')}  |  {rev.get('surprise_pct','')} surprise  |  YoY {rev.get('growth_yoy','')}")

        eps = result.get("earnings_per_share", {})
        if eps:
            lines.append(f"  EPS:      Actual {eps.get('actual','')}  |  Consensus {eps.get('consensus','')}  |  {eps.get('surprise_pct','')} surprise")

        gm = result.get("gross_margin", {})
        if gm:
            lines.append(f"  Gross Margin: {gm.get('actual','')}  (Prior Q: {gm.get('prior_quarter','')}  |  Prior Y: {gm.get('prior_year','')})  [{gm.get('trend','')}]")

        guidance = result.get("guidance", {})
        if guidance:
            lines.append(f"  Guidance: {guidance.get('revenue_next_q','')}  |  {guidance.get('vs_consensus','')} vs consensus  |  Tone: {guidance.get('tone','').upper()}")

        lang = result.get("management_language", {})
        if lang:
            lines.append(f"\n  Management Tone: {lang.get('tone','').upper()}")
            for phrase in lang.get("key_phrases", [])[:3]:
                lines.append(f"    \"{phrase}\"")
            for change in lang.get("notable_changes_vs_prior", [])[:2]:
                lines.append(f"    ⚡ {change}")

        concerns = result.get("key_concerns", [])
        if concerns:
            lines.append("\n  Key Concerns:")
            for c in concerns[:3]:
                lines.append(f"    ⚠  {c}")

        questions = result.get("key_questions_for_call", [])
        if questions:
            lines.append("\n  Questions for Mgmt Call:")
            for q in questions[:4]:
                lines.append(f"    ❓  {q}")

        view = result.get("one_week_reaction_view", "")
        if view:
            lines.append(f"\n  1-Week View: {view}")

        n = len(result.get("evidence_node_ids", []))
        lines.append(f"\n  Evidence anchors: {n} claims traceable to source")
        lines.append("═"*60)

        return "\n".join(lines)
