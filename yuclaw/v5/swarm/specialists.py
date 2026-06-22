"""YUCLAW v5 Layer 1 Day 4 — event-type specialists (model-agnostic, grounded).

The base swarm (Bull/Bear/Skeptic) is always on. On top of it, event-type SPECIALISTS are
spawned DETERMINISTICALLY from the event_type(s) the v4 extractor recorded for a filing
(public.events, READ-ONLY) — the model does NOT decide which specialists fire. A filing with no
matching event type spawns none (base swarm only).

Each specialist is a worker-tier agent (uses the model-agnostic WORKER_MODEL via call_worker) with
a type-specific lens, the SAME grounded output schema, and the SAME deterministic citation
verifier as the base swarm. Every specialist emits BOTH a return_view (directional research
opinion) and a risk_view (the C6 risk channel — vol/drawdown oriented).

C6 INSIDER-vs-MATERIAL SPLIT (the locked design, from the C6 investigation):
  insider-SELL clusters are a RISK signal, NOT a directional return signal — heavy insider
  selling reliably precedes higher realized volatility and deeper drawdowns (IC(C6, vol) =
  -0.317, IC(C6, maxDD) = +0.216) but does NOT cleanly predict return direction. So the Insider
  specialist must put insider-sell flow in risk_view (elevated) and keep return_view.direction
  NEUTRAL — it may not feed a bearish (or bullish) direction directly. Material non-insider
  events (M&A, regulatory, supply-chain) DO carry directional content and are handled separately.
"""

from __future__ import annotations

from typing import Optional

import psycopg2

from yuclaw.v5.swarm.agents import (
    _SCHEMA_BLOCK, MAX_FILING_CHARS, SwarmAgent,
)

# event_type (public.events) -> specialist key. Insider is split from material events.
SPAWN_MAP = {
    "M_AND_A_ANNOUNCE": "ma",
    "M_AND_A_CLOSE": "ma",
    "INSIDER_SELL": "insider",
    "INSIDER_BUY": "insider",
    "REGULATORY_ACTION": "regulatory",
}
SPECIALIST_KEYS = ("ma", "insider", "regulatory", "supplychain")

_MA_PROMPT = (
    "You are the M&A SPECIALIST. This filing reports a merger/acquisition/divestiture event. "
    "Analyse the DEAL strictly from what the filing states: deal terms, consideration/price, "
    "strategic rationale, financing, and any closing / regulatory-approval / integration risk. "
    "return_view is a directional research opinion on the deal's value impact for the filer. "
    "risk_view carries DEAL/EXECUTION risk (closing uncertainty, regulatory approval, integration, "
    "financing) — level high when the deal is unapproved/contingent or financing is uncertain.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_REGULATORY_PROMPT = (
    "You are the REGULATORY SPECIALIST. This filing references a regulatory/legal action or "
    "matter. Analyse only what the filing states: the nature of the action, the potential "
    "financial or operational exposure, and how quantified vs open-ended it is. Regulatory "
    "matters are usually directionally ambiguous, so return_view.direction should be neutral or "
    "mixed unless the text is clearly resolving. risk_view carries REGULATORY/LITIGATION risk — "
    "level high when exposure is material and unquantified.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_SUPPLYCHAIN_PROMPT = (
    "You are the SUPPLY-CHAIN SPECIALIST. This event propagates through the supply graph (a "
    "supplier/customer cascade). Analyse only what the filing states about supply, demand, "
    "component/input dependencies, customer concentration, and disruption. return_view is a "
    "directional opinion on the supply/demand impact. risk_view carries SUPPLY-DISRUPTION / "
    "CONCENTRATION risk — level high when dependencies are single-source or constrained.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_INSIDER_PROMPT = (
    "You are the INSIDER-FLOW SPECIALIST. This pertains to insider transactions (Form 4 / "
    "Section 16). CRITICAL RULE grounded in the C6 risk-gate finding: insider-SELL clusters are "
    "a RISK signal, NOT a directional return signal. Heavy insider selling reliably precedes "
    "higher volatility and deeper drawdowns, but does NOT predict return DIRECTION. Therefore:\n"
    "  - For insider SELLING, return_view.direction MUST be \"neutral\" — do NOT infer a bearish "
    "(or bullish) price direction from selling. Put the signal in risk_view: level \"high\" for a "
    "cluster of sells, drivers naming the insider-sell flow.\n"
    "  - Insider BUYING may carry a mild \"positive\" return_view direction.\n"
    "Ground every claim in the verbatim transaction facts.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

SPECIALIST_PROMPTS = {
    "ma": _MA_PROMPT,
    "insider": _INSIDER_PROMPT,
    "regulatory": _REGULATORY_PROMPT,
    "supplychain": _SUPPLYCHAIN_PROMPT,
}


class SpecialistAgent(SwarmAgent):
    """A worker-tier specialist. Same grounded run() + verifier as the base swarm; only the
    prompt (lens) differs. Uses the model-agnostic WORKER_MODEL via call_worker."""

    def __init__(self, key: str, **kw):
        super().__init__(**kw)
        self.role = key  # so grounding / outputs are tagged by specialist key

    def build_prompt(self, filing_text: str) -> str:
        return SPECIALIST_PROMPTS[self.role].replace("{text}", filing_text[:MAX_FILING_CHARS])


def spawn_specialists(accession: str, dsn: str = "dbname=yuclaw_events") -> list[dict]:
    """DETERMINISTIC: read the filing's event_type(s) (public.events, READ-ONLY) and return the
    specialists to spawn, each with the reason (the event_type that triggered it). No model in
    the loop. SupplyChain also fires when the filing's event is part of a supply cascade
    (cascade_depth >= 1)."""
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT e.event_type, e.cascade_depth "
                "FROM public.events e "
                "JOIN public.events_raw er ON er.source_url = e.source_url "
                "WHERE er.accession_number = %s", (accession,))
            rows = cur.fetchall()
    finally:
        cn.close()

    chosen: dict[str, str] = {}  # key -> reason (first trigger wins)
    for event_type, cascade_depth in rows:
        key = SPAWN_MAP.get(event_type)
        if key and key not in chosen:
            chosen[key] = event_type
        if (cascade_depth or 0) >= 1 and "supplychain" not in chosen:
            chosen["supplychain"] = f"{event_type} (cascade_depth={cascade_depth})"
    return [{"key": k, "reason": r} for k, r in chosen.items()]
