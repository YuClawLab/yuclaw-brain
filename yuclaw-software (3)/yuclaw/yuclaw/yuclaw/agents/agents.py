"""yuclaw/agents/agents.py — All YUCLAW agents."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from ..core.router import get_router
from ..core.ontology.models import EvidenceNode, ValidationStatus
from ..memory.evidence_graph import EvidenceGraph
from ..memory.portfolio_memory import PortfolioMemory


# ─────────────────────────────────────────────────────────
#  CIO AGENT
# ─────────────────────────────────────────────────────────

CIO_SYSTEM = """You are the CIO Agent of YUCLAW financial intelligence system.
Decompose the research request into ordered tasks for specialist agents.
Output JSON array only. Each task: {"task_id":str, "agent":str, "instruction":str, "priority":"high|medium|low"}
agent options: research | macro | quant | risk | compliance
No preamble. JSON only."""


@dataclass
class Task:
    task_id: str
    agent: str
    instruction: str
    priority: str = "medium"
    result: str | None = None


@dataclass  
class WorkPlan:
    request: str
    tasks: list[Task]
    capital_limit_usd: float = 0.0  # Always 0 until Execution Agent activated


class CIOAgent:
    def __init__(self):
        self._router = get_router()

    async def decompose(self, request: str) -> WorkPlan:
        response = await self._router.complete(
            prompt=f"Research request: {request}",
            system=CIO_SYSTEM,
            fast=True
        )
        try:
            tasks = [Task(**t) for t in json.loads(response)]
        except Exception:
            tasks = [Task(task_id="t1", agent="research",
                          instruction=request, priority="high")]
        return WorkPlan(request=request, tasks=tasks, capital_limit_usd=0.0)


# ─────────────────────────────────────────────────────────
#  RESEARCH AGENT
# ─────────────────────────────────────────────────────────

RESEARCH_SYSTEM = """You are the YUCLAW Research Agent. Analyze financial documents.
CRITICAL: Every factual claim MUST include a citation: [DOC:<id>|PAGE:<n>]
Output JSON only:
{
  "summary": "comprehensive investment analysis",
  "key_metrics": [{"name":str, "value":str, "page":int, "significance":str}],
  "thesis": {"bull":str, "base":str, "bear":str},
  "key_assumptions": [str],
  "catalysts": [str],
  "risks": [str],
  "claims": [{"claim":str, "page":int, "confidence":float, "ontology_tags":[str]}]
}
JSON only. No preamble."""


class ResearchAgent:
    def __init__(self, evidence_graph: EvidenceGraph, portfolio_memory: PortfolioMemory):
        self._router   = get_router()
        self._graph    = evidence_graph
        self._memory   = portfolio_memory
        # Wire in real PDF parser for grounding with actual financial data
        try:
            from ..data.parsers.real_pdf_parser import RealPDFParser
            self._real_parser = RealPDFParser()
        except ImportError:
            self._real_parser = None

    async def analyze(self, doc_text: str, doc_id: str, ticker: str, query: str) -> dict:
        # Pull prior thesis from memory
        history = await self._memory.get_history(ticker)
        history_context = ""
        if history:
            history_context = (
                f"\n\nPRIOR THESIS HISTORY FOR {ticker} ({len(history)} records):\n"
                + "\n".join(f"- [{h.created_at[:10]}] {h.thesis[:120]}" for h in history[:3])
                + "\n\nCompare current analysis against prior thesis.\n"
            )

        # Ground with REAL financial data from yfinance
        grounding_context = ""
        if self._real_parser:
            try:
                parsed = self._real_parser.parse_yfinance(ticker)
                if parsed.facts:
                    grounding_context = "\n\n" + parsed.to_grounding_context() + "\n"
            except Exception:
                pass

        prompt = (
            f"DOCUMENT ID: {doc_id}\nTICKER: {ticker}\n"
            f"{grounding_context}"
            f"{history_context}"
            f"\nDOCUMENT TEXT:\n{doc_text[:50000]}\n\n"
            f"QUERY: {query}"
        )

        response = await self._router.complete(
            prompt=prompt, system=RESEARCH_SYSTEM, max_tokens=8192
        )

        try:
            result = json.loads(response)
        except Exception:
            result = {"summary": response, "claims": [], "key_metrics": [],
                      "thesis": {}, "key_assumptions": [], "catalysts": [], "risks": []}

        # Build Evidence Graph nodes
        now = datetime.now(timezone.utc).isoformat()
        node_ids = []
        for i, c in enumerate(result.get("claims", [])):
            if not c.get("claim"):
                continue
            node = EvidenceNode(
                claim=c["claim"],
                source_doc_id=doc_id,
                page_number=max(int(c.get("page") or 1), 1),
                paragraph_hash=f"{doc_id}_claim_{i}",
                extraction_timestamp=now,
                model_version="nemotron-3-super",
                confidence=float(c.get("confidence") or 0.8),
                ontology_tags=c.get("ontology_tags", [])
            )
            nid = await self._graph.add_node(node)
            node_ids.append(nid)

        result["evidence_node_ids"] = node_ids
        result["ticker"]  = ticker
        result["doc_id"]  = doc_id
        result["status"]  = ValidationStatus.EVIDENCE_EXTRACTED.value
        result["prior_thesis_count"] = len(history)

        return result


# ─────────────────────────────────────────────────────────
#  MACRO AGENT
# ─────────────────────────────────────────────────────────

MACRO_SYSTEM = """You are the YUCLAW Macro Agent. Analyze macro events and their market impact.
Output JSON only:
{
  "event": str,
  "severity": "low|medium|high|critical",
  "first_order_impacts": [
    {"asset_class":str, "direction":"positive|negative|neutral", "magnitude":"small|medium|large", "reasoning":str}
  ],
  "second_order_impacts": [{"asset_class":str, "mechanism":str}],
  "sectors": {"beneficiaries":[str], "casualties":[str]},
  "portfolio_actions": [str],
  "time_horizon": {"days_1_5":str, "weeks_1_4":str, "months_1_3":str}
}
JSON only. No preamble."""


class MacroAgent:
    def __init__(self):
        self._router = get_router()

    async def analyze_event(self, event: str) -> dict:
        response = await self._router.complete(
            prompt=f"Macro event to analyze: {event}",
            system=MACRO_SYSTEM,
            max_tokens=4096
        )
        try:
            return json.loads(response)
        except Exception:
            return {"event": event, "raw_analysis": response, "error": "parse_failed"}


# ─────────────────────────────────────────────────────────
#  QUANT AGENT
# ─────────────────────────────────────────────────────────

QUANT_SYSTEM = """You are the YUCLAW Quant Agent. Generate quantitative strategy specifications.
Output JSON only:
{
  "strategy_name": str,
  "strategy_description": str,
  "universe": str,
  "signal_logic": str,
  "holding_period": str,
  "rebalance_frequency": str,
  "risk_controls": [str],
  "expected_calmar_ratio": float,
  "python_pseudocode": str,
  "known_failure_conditions": [str]
}
JSON only. No preamble."""


class QuantAgent:
    def __init__(self):
        self._router = get_router()

    async def generate_strategy(self, instruction: str) -> dict:
        response = await self._router.complete(
            prompt=f"Generate a quantitative strategy for: {instruction}",
            system=QUANT_SYSTEM,
            max_tokens=4096
        )
        try:
            return json.loads(response)
        except Exception:
            return {"strategy_description": response, "error": "parse_failed"}
