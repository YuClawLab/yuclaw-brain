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
from yuclaw.v5.extract.reclassify import corrected_event_types

import re as _re

# CORRECTED event_type (yuclaw_v5.event_type_corrected, falling back to v4) -> specialist key(s).
# Day 5A: spawn reads the corrected layer so a financing no longer fires the M&A specialist.
# A type can fire multiple specialists (e.g. REGULATORY_ACTION -> regulatory + litigation).
SPAWN_MAP = {
    "M_AND_A": ["ma"],
    "M_AND_A_ANNOUNCE": ["ma"],
    "M_AND_A_CLOSE": ["ma"],
    "INSIDER_SELL": ["insider"],
    "INSIDER_BUY": ["insider"],
    "REGULATORY_ACTION": ["regulatory", "litigation"],
    "EARNINGS_RESULT": ["earningsquality"],
    "EARNINGS_BEAT": ["earningsquality"],
    "GUIDANCE_RAISE": ["earningsquality", "sentimentdrift"],
    "GUIDANCE_CUT": ["earningsquality", "sentimentdrift"],
}

# Theme specialists fire on DETERMINISTIC content signatures in the filing narrative (keyword
# presence; the matched phrase is the SourceLock span / spawn reason). These are theme overlays,
# not discrete corporate events.
CONTENT_TRIGGERS = {
    "macro": _re.compile(r"\b(tariff|inflation|interest rate|macroeconomic|monetary policy|"
                         r"foreign exchange|currency fluctuation)\b", _re.I),
    "geopolitical": _re.compile(r"\b(sanction|export control|geopolitical|trade restriction|"
                                r"national security|armed conflict|war in)\b", _re.I),
    "esg": _re.compile(r"\b(greenhouse gas|emissions|sustainability|climate|renewable|"
                       r"diversity|human rights)\b", _re.I),
}

SPECIALIST_KEYS = ("ma", "insider", "regulatory", "supplychain",
                   "macro", "geopolitical", "earningsquality", "litigation",
                   "sentimentdrift", "esg")

# Risk-natured specialists: their signal feeds the RISK channel, NOT direction (C6 discipline).
# Their prompts force return_view.direction neutral; they raise risk_view. Same separation as the
# Insider specialist established on Day 4.
RISK_NATURED = {"insider", "litigation", "geopolitical"}

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

# --------------------------------------------------------------------------
# Day 5A specialists #5-#10
# --------------------------------------------------------------------------
_MACRO_PROMPT = (
    "You are the MACRO SPECIALIST. Analyse how MACROECONOMIC conditions named in this filing "
    "(tariffs, interest rates, inflation, currency/FX, monetary policy) bear on the company, "
    "strictly from what the text states. return_view may carry a directional read (macro tailwind "
    "positive / headwind negative / mixed). risk_view carries MACRO risk — level high when the "
    "filing flags material, unhedged macro exposure.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_GEOPOLITICAL_PROMPT = (
    "You are the GEOPOLITICAL SPECIALIST. Analyse geopolitical exposure named in this filing "
    "(sanctions, export controls, trade restrictions, armed conflict, national-security review). "
    "Geopolitical exposure is RISK-natured: return_view.direction MUST be \"neutral\" or "
    "\"mixed\" — do NOT infer a price direction from geopolitical risk. Put the signal in "
    "risk_view: level high for material sanctions/export-control/conflict exposure, drivers naming "
    "the specific exposure.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_EARNINGSQUALITY_PROMPT = (
    "You are the EARNINGS-QUALITY SPECIALIST. This filing reports results or guidance. Assess the "
    "QUALITY of the earnings, not just the headline: is growth organic vs one-off, are margins "
    "sustainable, are there non-GAAP adjustments, charges, or revenue-recognition flags — strictly "
    "from the text. return_view is a quality-ADJUSTED directional read (a beat of low quality is "
    "not strongly positive). risk_view carries EARNINGS-QUALITY risk — level high for aggressive "
    "adjustments or unsustainable drivers.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_LITIGATION_PROMPT = (
    "You are the LITIGATION SPECIALIST. Analyse legal/litigation exposure in this filing (lawsuits, "
    "claims, settlements, regulatory enforcement, investigations). Litigation is RISK-natured: "
    "return_view.direction MUST be \"neutral\" or \"mixed\" — do NOT infer a price direction from "
    "litigation. Put the signal in risk_view: level high when exposure is material and "
    "unquantified, drivers naming the specific matter. Ground every claim in the filing text.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_SENTIMENTDRIFT_PROMPT = (
    "You are the SENTIMENT-DRIFT SPECIALIST. This filing signals a shift in management's forward "
    "tone (e.g. raised or cut guidance, changed outlook language). Assess the DIRECTION and "
    "magnitude of the sentiment shift strictly from the text: is management more or less "
    "confident, and on what basis. return_view carries the directional sentiment read (raised "
    "guidance / improving tone positive; cut / cautious negative). risk_view carries the risk that "
    "the shift signals (e.g. a cut implies demand/margin risk).\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

_ESG_PROMPT = (
    "You are the ESG SPECIALIST. Analyse environmental, social, and governance matters named in "
    "this filing (emissions/climate commitments, sustainability, diversity, human rights, "
    "governance changes), strictly from the text. ESG is usually direction-ambiguous in the short "
    "term, so return_view.direction should be \"neutral\" or \"mixed\" unless the filing states a "
    "clearly material financial impact. risk_view carries ESG/transition/reputational risk.\n\n"
    + _SCHEMA_BLOCK + "\n\nFILING EXCERPT:\n{text}\n\nJSON:"
)

SPECIALIST_PROMPTS = {
    "ma": _MA_PROMPT,
    "insider": _INSIDER_PROMPT,
    "regulatory": _REGULATORY_PROMPT,
    "supplychain": _SUPPLYCHAIN_PROMPT,
    "macro": _MACRO_PROMPT,
    "geopolitical": _GEOPOLITICAL_PROMPT,
    "earningsquality": _EARNINGSQUALITY_PROMPT,
    "litigation": _LITIGATION_PROMPT,
    "sentimentdrift": _SENTIMENTDRIFT_PROMPT,
    "esg": _ESG_PROMPT,
}


class SpecialistAgent(SwarmAgent):
    """A worker-tier specialist. Same grounded run() + verifier as the base swarm; only the
    prompt (lens) differs. Uses the model-agnostic WORKER_MODEL via call_worker."""

    def __init__(self, key: str, **kw):
        super().__init__(**kw)
        self.role = key  # so grounding / outputs are tagged by specialist key

    def build_prompt(self, filing_text: str) -> str:
        return SPECIALIST_PROMPTS[self.role].replace("{text}", filing_text[:MAX_FILING_CHARS])


def spawn_specialists(accession: str, dsn: str = "dbname=yuclaw_events",
                      narrative_text: Optional[str] = None) -> list[dict]:
    """DETERMINISTIC spawn. No model in the loop. Three trigger sources:
      1. CORRECTED event_type (yuclaw_v5.event_type_corrected, falling back to v4) via SPAWN_MAP
         — so a financing no longer fires the M&A specialist;
      2. supply cascade (cascade_depth >= 1) -> supplychain;
      3. content signatures in the filing narrative (CONTENT_TRIGGERS) -> theme specialists
         (macro / geopolitical / esg), with the matched phrase as the SourceLock spawn reason.
    Returns [{key, reason, trigger}]."""
    chosen: dict[str, dict] = {}  # key -> {reason, trigger}

    # 1. corrected event-type triggers
    for et in corrected_event_types(accession, dsn):  # [{event_type, source}]
        for key in SPAWN_MAP.get(et["event_type"], []):
            chosen.setdefault(key, {"reason": f"{et['event_type']} ({et['source']})",
                                    "trigger": "event_type"})

    # 2. supply cascade
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT max(e.cascade_depth) FROM public.events e "
                "JOIN public.events_raw er ON er.source_url = e.source_url "
                "WHERE er.accession_number = %s", (accession,))
            row = cur.fetchone()
            max_depth = (row[0] if row and row[0] is not None else 0)
    finally:
        cn.close()
    if max_depth >= 1:
        chosen.setdefault("supplychain", {"reason": f"cascade_depth={max_depth}",
                                          "trigger": "cascade"})

    # 3. content-signature theme triggers (deterministic keyword presence)
    if narrative_text:
        for key, rx in CONTENT_TRIGGERS.items():
            m = rx.search(narrative_text)
            if m and key not in chosen:
                chosen[key] = {"reason": f"content:'{m.group(0)}'", "trigger": "content"}

    return [{"key": k, "reason": v["reason"], "trigger": v["trigger"]} for k, v in chosen.items()]
