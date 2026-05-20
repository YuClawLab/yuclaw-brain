"""
SourceLock Guard — deterministic validator for LLM-extracted events.

No LLM calls. Eight rules (R1..R8) check that the LLM's JSON output is
well-formed AND verifiable against the original raw text. A failure
returns the rule name so rejected_events can be audited.

Public API:
    validate(llm_json: dict, raw_text: str, ticker: str) -> (bool, reason_or_None)
"""
from __future__ import annotations

import re
from typing import Optional

EVENT_TYPES = {
    "EARNINGS_BEAT", "EARNINGS_MISS", "GUIDANCE_RAISE", "GUIDANCE_CUT",
    "M_AND_A_ANNOUNCE", "M_AND_A_CLOSE", "REGULATORY_ACTION", "EXEC_CHANGE",
    "BUYBACK_ANNOUNCE", "DIVIDEND_CHANGE", "PRODUCT_LAUNCH", "LAWSUIT",
    "PARTNERSHIP", "CONTRACT_WIN", "LAYOFFS", "CAPACITY_CHANGE",
    "INSIDER_BUY", "INSIDER_SELL", "OTHER_MATERIAL",
}

REQUIRED_KEYS = {
    "event_type", "magnitude", "direction",
    "confidence", "raw_excerpt", "rationale",
}

# Regex for R8 — advice-language detection.
_ADVICE_RE = re.compile(
    r"\b(buy now|sell immediately|you should|we recommend|investors should)\b",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"\w+")


def _jaccard(a: str, b: str) -> float:
    """Token Jaccard similarity, lowercased. Returns 0.0 if either side empty."""
    ta = set(_TOKEN_RE.findall(a.lower()))
    tb = set(_TOKEN_RE.findall(b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def validate(llm_json: dict, raw_text: str, ticker: str) -> tuple[bool, Optional[str]]:
    """Validate an LLM extraction against R1..R8.

    Returns (True, None) when all rules pass, or (False, "Rx_name") on the
    first failure. A {"no_event": true} sentinel passes immediately.

    Rules:
        R1 schema_complete           — required keys all present (or no_event)
        R2 event_type_in_vocabulary  — event_type in the 19-string set
        R3 direction_in              — direction in {-1, 0, 1}
        R4 magnitude_in              — 0.0 <= magnitude <= 1.0
        R5 confidence_floor          — confidence >= 0.5
        R6 excerpt_length            — <= 50 words AND <= 400 chars
        R7 excerpt_verifiable        — substring of raw_text OR Jaccard >= 0.85
        R8 no_advice_language        — advice regex matches neither field
    """
    # Sentinel: explicit no-event is always valid, no further checks.
    if isinstance(llm_json, dict) and llm_json.get("no_event") is True:
        return True, None

    if not isinstance(llm_json, dict):
        return False, "R1_schema_complete"

    # R1
    if not REQUIRED_KEYS.issubset(llm_json.keys()):
        return False, "R1_schema_complete"

    # R2
    if llm_json["event_type"] not in EVENT_TYPES:
        return False, "R2_event_type_in_vocabulary"

    # R3
    if llm_json["direction"] not in (-1, 0, 1):
        return False, "R3_direction_in"

    # R4
    mag = llm_json["magnitude"]
    if not isinstance(mag, (int, float)) or not 0.0 <= mag <= 1.0:
        return False, "R4_magnitude_in"

    # R5
    conf = llm_json["confidence"]
    if not isinstance(conf, (int, float)) or conf < 0.5:
        return False, "R5_confidence_floor"

    excerpt = llm_json["raw_excerpt"]
    if not isinstance(excerpt, str):
        return False, "R6_excerpt_length"

    # R6
    if len(excerpt) > 400 or len(excerpt.split()) > 50:
        return False, "R6_excerpt_length"

    # R7 — substring OR Jaccard >= 0.85
    raw_lc = raw_text.lower()
    if excerpt.lower().strip() not in raw_lc:
        if _jaccard(excerpt, raw_text) < 0.85:
            return False, "R7_excerpt_verifiable"

    # R8 — advice-language in excerpt or rationale
    rationale = llm_json.get("rationale", "") or ""
    if _ADVICE_RE.search(excerpt) or _ADVICE_RE.search(rationale):
        return False, "R8_no_advice_language"

    return True, None
