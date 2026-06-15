"""Unit tests for the deterministic grounding verifier (NO LLM, NO Postgres).

Synthetic cases covering the three behaviours the Day-2 gate depends on:
verbatim hit, paraphrase miss, and fabricated-number catch — plus normalized
matching and offset correctness. These MUST pass before any LLM run.

Run:  python3 -m pytest yuclaw/v5/swarm/tests/test_grounding.py -q
"""

from __future__ import annotations

from yuclaw.v5.swarm.grounding import (
    grade_agent, verify_citation, verify_numbers,
)

FILING = (
    "ITEM 7. MANAGEMENT DISCUSSION.\n"
    "The Company's long-term debt decreased by $1,575 million during the year "
    "ended December 31, 2024.\n"
    "Operating income increased by $1,234 million, or 11%, to $12,345 million.\n"
)


# -- verify_citation -------------------------------------------------------
def test_exact_verbatim_hit():
    q = "long-term debt decreased by $1,575 million"
    r = verify_citation(q, FILING)
    assert r["verified"] is True
    assert r["match_type"] == "exact"
    # Offsets point back at the real span.
    assert FILING[r["start"]:r["end"]] == q


def test_normalized_hit_whitespace_and_case():
    # Same text, but with collapsed/extra whitespace and different case — a
    # verbatim span modulo whitespace/case must still verify, with offsets that
    # land on the ORIGINAL text.
    q = "LONG-TERM   debt   DECREASED by $1,575 million"
    r = verify_citation(q, FILING)
    assert r["verified"] is True
    assert r["match_type"] == "normalized"
    assert FILING[r["start"]:r["end"]].lower().split() == \
        "long-term debt decreased by $1,575 million".split()


def test_paraphrase_miss():
    # Not a verbatim span (words reordered / changed) — must NOT verify.
    q = "the long term debt went down by about 1.5 billion dollars"
    r = verify_citation(q, FILING)
    assert r["verified"] is False
    assert r["match_type"] is None
    assert r["start"] is None


def test_empty_quote_miss():
    assert verify_citation("", FILING)["verified"] is False
    assert verify_citation("   ", FILING)["verified"] is False


# -- verify_numbers --------------------------------------------------------
def test_numbers_all_present():
    ok, rep = verify_numbers("debt fell by $1,575 million",
                             ["long-term debt decreased by $1,575 million"])
    assert ok is True
    assert rep[0]["token"] == "1575" and rep[0]["found"] is True


def test_fabricated_number_caught():
    # The quote is real, but the point states a DIFFERENT figure -> caught.
    ok, rep = verify_numbers("debt fell by $9,999 million",
                             ["long-term debt decreased by $1,575 million"])
    assert ok is False
    assert {"token": "9999", "found": False} in rep


def test_no_numbers_passes_vacuously():
    ok, rep = verify_numbers("margins are improving", ["operating income increased"])
    assert ok is True and rep == []


def test_substring_number_not_spurious():
    # '5' must NOT be satisfied by '1575' / '12345' — token-wise comparison.
    ok, rep = verify_numbers("up 5 points", ["increased by $1,575 million to $12,345"])
    assert ok is False
    assert rep[0]["token"] == "5" and rep[0]["found"] is False


# -- grade_agent (end-to-end on a synthetic agent output) ------------------
def _agent(points):
    return {"stance": "x", "key_points": points, "confidence": 0.5,
            "return_view": {}, "risk_view": {}}


def test_grade_mixed_grounding():
    out = _agent([
        # grounded: verbatim quote + the number is inside it
        {"point": "Long-term debt decreased by $1,575 million.",
         "quotes": ["long-term debt decreased by $1,575 million"]},
        # discarded: quote does not exist in filing
        {"point": "Revenue doubled year over year.",
         "quotes": ["revenue doubled year over year"]},
        # discarded: real quote, but fabricated number in the point
        {"point": "Operating income rose to $99,999 million.",
         "quotes": ["Operating income increased by $1,234 million, or 11%, to $12,345 million"]},
    ])
    g = grade_agent(out, FILING)
    assert g["points_total"] == 3
    assert g["points_grounded"] == 1
    assert g["points_discarded"] == 2
    assert g["grounding_rate"] == round(1 / 3, 4)
    assert g["citations_total"] == 3
    assert g["citations_verified"] == 2          # 2 quotes real, 1 fabricated
    # The grounded point's span is in the ledger.
    assert any("long-term debt decreased" in led["quote"] for led in g["ledger"])
    # Discard reasons are specific.
    reasons = {d["point"][:8]: d["reason"] for d in g["discarded_points"]}
    assert "no verified quote" in reasons["Revenue "]
    assert "not in cited quote" in reasons["Operatin"]


def test_grade_all_grounded_rate_one():
    out = _agent([
        {"point": "Debt down $1,575 million.",
         "quotes": ["long-term debt decreased by $1,575 million"]},
        {"point": "Operating income up 11%.",
         "quotes": ["Operating income increased by $1,234 million, or 11%, to $12,345 million"]},
    ])
    g = grade_agent(out, FILING)
    assert g["grounding_rate"] == 1.0
    assert g["points_grounded"] == 2 and g["points_discarded"] == 0


def test_grade_empty_points():
    g = grade_agent(_agent([]), FILING)
    assert g["points_total"] == 0
    assert g["grounding_rate"] == 0.0
    assert g["ledger"] == []
