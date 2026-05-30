"""
SourceLock Guard — deterministic validator for LLM-extracted events.

No LLM calls. Eight rules (R1..R8) check that the LLM's JSON output is
well-formed AND verifiable against the original raw text. A failure
returns the rule name so rejected_events can be audited.

Public API:
    validate(llm_json: dict, raw_text: str, ticker: str) -> (bool, reason_or_None)
"""
from __future__ import annotations

import html
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


# Order 1D — tight typographic-only Unicode→ASCII map for R7's last
# substring fallback. Covers exactly the substitutions the Order-1C
# audit observed Llama 70B applying when copying source spans:
#   NBSP → ASCII space             (12/12 nbsp gap rows)
#   curly doubles → ASCII "        (3/12 rows, incl. cascade-eligible CVX + INTC)
#   whitespace run collapse        (HTML render artifact)
# Deliberately does NOT touch en/em-dashes or curly singles (no gap row
# needed them) — keeps the substitution surface as small as possible.
# This is NOT NFKC/NFKD normalization. Cannot turn "raised" into "cut".
# Corruption probe 0/14 false-accepts verified before commit.
_FANCY_DOUBLE_QUOTE_RE = re.compile(r"[“”„‟]")
_WS_RE = re.compile(r"\s+")


def _r7_normalize(s: str) -> str:
    s = s.lower()
    s = s.replace(" ", " ")           # NBSP → space
    s = _FANCY_DOUBLE_QUOTE_RE.sub('"', s) # curly doubles → ASCII "
    s = _WS_RE.sub(" ", s).strip()         # collapse whitespace runs
    return s


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

    # R7 — most-restrictive-first cascade. Each fallback fires only if the
    # prior check did not match. Substring is the canonical check; the two
    # fallbacks below only relax character encoding, never semantics.
    raw_lc = raw_text.lower()
    excerpt_lc = excerpt.lower().strip()
    if excerpt_lc not in raw_lc:
        # Fallback 1 — HTML-decode the source (see Order 1C-prompt audit).
        # EDGAR raw_text preserves entities like `&#8220;` / `&#160;`; Llama 70B
        # occasionally unescapes them when copying. Recovers ~24/45 of the
        # Order-1C R7 rejections. Cannot change semantic tokens — a flipped
        # direction word or number still won't appear in the decoded source.
        raw_decoded_lc = html.unescape(raw_text).lower()
        if excerpt_lc not in raw_decoded_lc:
            # Fallback 2 — tight typographic Unicode→ASCII normalize on both
            # sides (Order 1D). Recovers an additional 3 rows including the
            # cascade-eligible CVX GUIDANCE_RAISE and INTC M_AND_A_CLOSE that
            # were blocked by curly double quotes / NBSP. _r7_normalize is a
            # 3-substitution map — see the function docstring above. Verified
            # 0/14 false-accepts on the full corruption probe before commit.
            if _r7_normalize(excerpt) not in _r7_normalize(html.unescape(raw_text)):
                # Fallback 3 — Jaccard sanity net (kept from original R7).
                if _jaccard(excerpt, raw_text) < 0.85:
                    return False, "R7_excerpt_verifiable"

    # R8 — advice-language in excerpt or rationale
    rationale = llm_json.get("rationale", "") or ""
    if _ADVICE_RE.search(excerpt) or _ADVICE_RE.search(rationale):
        return False, "R8_no_advice_language"

    return True, None
