"""YUCLAW v5 Layer 1 Day 2 — deterministic grounding verifier (NO LLM).

The Day-1 swarm let 8B agents fabricate figures (a bull claiming "debt decreased"
while a bear claimed "debt increased" on the SAME filing). Day 2 makes every agent
claim *programmatically* traceable to a verbatim span of the source filing — the
proto-form of Layer 2's evidence tokens.

Nothing here trusts the model. Given an agent's structured v2 output and the raw
filing text, we:

  * verify_citation  — is a quote a real, verbatim span of the filing? Exact match
                       first, then a whitespace/case-normalized match (filings are
                       full of ragged whitespace), returning the LOCATED offsets in
                       the ORIGINAL text.
  * verify_numbers   — does every number token in a key_point actually appear inside
                       that point's verified quotes? (Catches altered/fabricated
                       figures even when a real quote is attached.)
  * grade_agent      — per-agent grounding report + the verified-citation ledger
                       (accession + spans) that downstream synthesis consumes.

A key_point is GROUNDED iff it has >= 1 verified quote AND every numeric token in
the point is present in those verified quotes. Otherwise it is DISCARDED (and the
reason recorded). grounding_rate = points_grounded / points_total.
"""

from __future__ import annotations

import re
from typing import Any, Optional

# A number token: an integer/decimal core, optionally with thousands separators.
# We deliberately capture only the DIGIT core ("1,575", "11", "3.2"); surrounding
# units/symbols ($, %, "million") are not part of the fabrication test — the
# digits are what get invented or altered.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


# --------------------------------------------------------------------------
# Whitespace/case normalization WITH an offset map back to the original text.
# --------------------------------------------------------------------------
def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Return (normalized_text, idx_map) where idx_map[k] is the offset in the
    ORIGINAL ``text`` of the k-th normalized character.

    Normalization: lowercase; every run of whitespace collapses to a single
    space. This lets a quote that differs from the filing only in whitespace
    (line wraps, doubled spaces) or letter case still match — while idx_map lets
    us report the span in the original, un-normalized text.
    """
    norm_chars: list[str] = []
    idx_map: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            norm_chars.append(" ")
            idx_map.append(i)
            prev_space = True
        else:
            norm_chars.append(ch.lower())
            idx_map.append(i)
            prev_space = False
    return "".join(norm_chars), idx_map


def verify_citation(
    quote: str,
    filing_text: str,
    norm_cache: Optional[tuple[str, list[int]]] = None,
) -> dict:
    """Is ``quote`` a verbatim span of ``filing_text``?

    Returns ``{verified, match_type, start, end}``. ``match_type`` is ``"exact"``,
    ``"normalized"``, or ``None``. ``start``/``end`` are offsets into the ORIGINAL
    filing text (end exclusive), or ``None`` when unverified.

    ``norm_cache`` is the result of ``_normalize_with_map(filing_text)``; pass it
    when grading many quotes against one filing to avoid recomputing.
    """
    miss = {"verified": False, "match_type": None, "start": None, "end": None}
    if not quote or not quote.strip():
        return dict(miss)

    # 1. Exact substring.
    idx = filing_text.find(quote)
    if idx != -1:
        return {"verified": True, "match_type": "exact",
                "start": idx, "end": idx + len(quote)}

    # 2. Whitespace/case-normalized substring, offsets mapped back to original.
    norm_text, idx_map = norm_cache or _normalize_with_map(filing_text)
    nquote, _ = _normalize_with_map(quote)
    nquote = nquote.strip()
    if not nquote:
        return dict(miss)
    pos = norm_text.find(nquote)
    if pos != -1:
        start = idx_map[pos]
        end = idx_map[pos + len(nquote) - 1] + 1
        return {"verified": True, "match_type": "normalized", "start": start, "end": end}

    return dict(miss)


# --------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------
def _number_tokens(text: str) -> list[str]:
    """Digit cores in ``text``, thousands separators stripped: '$1,575'->'1575'."""
    return [m.group(0).replace(",", "") for m in _NUM_RE.finditer(text or "")]


def verify_numbers(point_text: str, verified_quotes: list[str]) -> tuple[bool, list[dict]]:
    """Every number in ``point_text`` must appear in this point's verified quotes.

    Compared token-wise on the comma-stripped digit core (so '5' does NOT spuriously
    satisfy a claim of '1575', and '$1,575'/'1575' match). A point with no numbers
    passes vacuously. Returns (all_found, [{token, found}, ...]).
    """
    point_nums = _number_tokens(point_text)
    quote_nums: set[str] = set()
    for q in verified_quotes:
        quote_nums.update(_number_tokens(q))
    report = [{"token": n, "found": n in quote_nums} for n in point_nums]
    all_found = all(r["found"] for r in report)
    return all_found, report


# --------------------------------------------------------------------------
# Per-agent grade
# --------------------------------------------------------------------------
def grade_agent(output: dict, filing_text: str) -> dict:
    """Grade one agent's v2 ``output`` against the filing.

    ``output["key_points"]`` is ``[{"point": str, "quotes": [str, ...]}, ...]``.
    Returns a grounding report; ``ledger`` holds the de-duplicated verified spans
    (the proto evidence token) and ``grounded_points`` is the subset that survives
    for synthesis.
    """
    norm = _normalize_with_map(filing_text)
    key_points = output.get("key_points") or []

    points_report: list[dict] = []
    citations_total = 0
    citations_verified = 0
    points_grounded = 0
    ledger: list[dict] = []
    seen_spans: set[tuple[int, int]] = set()

    for kp in key_points:
        point_text = kp.get("point") or ""
        quotes = kp.get("quotes") or []
        q_reports: list[dict] = []
        verified_texts: list[str] = []
        for q in quotes:
            citations_total += 1
            vc = verify_citation(q, filing_text, norm_cache=norm)
            if vc["verified"]:
                citations_verified += 1
                verified_texts.append(q)
                span = (vc["start"], vc["end"])
                if span not in seen_spans:
                    seen_spans.add(span)
                    ledger.append({"quote": q, "start": vc["start"],
                                   "end": vc["end"], "match_type": vc["match_type"]})
            q_reports.append({"quote": q, **vc})

        nums_ok, nums_report = verify_numbers(point_text, verified_texts)
        has_quote = len(verified_texts) >= 1
        grounded = has_quote and nums_ok
        if not has_quote:
            discard_reason = "no verified quote"
        elif not nums_ok:
            bad = [r["token"] for r in nums_report if not r["found"]]
            discard_reason = f"number(s) not in cited quote: {bad}"
        else:
            discard_reason = None
        if grounded:
            points_grounded += 1

        points_report.append({
            "point": point_text,
            "grounded": grounded,
            "discard_reason": discard_reason,
            "quotes": q_reports,
            "numbers": nums_report,
        })

    points_total = len(key_points)
    points_discarded = points_total - points_grounded
    grounding_rate = (points_grounded / points_total) if points_total else 0.0

    return {
        "citations_total": citations_total,
        "citations_verified": citations_verified,
        "points_total": points_total,
        "points_grounded": points_grounded,
        "points_discarded": points_discarded,
        "grounding_rate": round(grounding_rate, 4),
        "points": points_report,
        "grounded_points": [p["point"] for p in points_report if p["grounded"]],
        "discarded_points": [
            {"point": p["point"], "reason": p["discard_reason"]}
            for p in points_report if not p["grounded"]
        ],
        "ledger": ledger,
    }
