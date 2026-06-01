"""
Shared ultra-thin HTTP client for the YUCLAW v4 agent wrappers.

Both the LangChain and LlamaIndex integrations wrap the SAME REST endpoints
(/v1/why, /v1/memo) through these helpers — one place that knows the wire format.
No orchestration, no caching: a GET and a JSON body.

Base URL resolves from the YUCLAW_API_URL env var, default http://127.0.0.1:8088.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = os.environ.get("YUCLAW_API_URL", "http://127.0.0.1:8088")
DEFAULT_TIMEOUT = 30.0

# Shared, agent-facing tool description fragment (Q2).
EVIDENCE_FIRST_BLURB = (
    "Evidence-first research output: every claim has a source SEC filing and a ledger "
    "hash, so the answer is independently verifiable. Signal labels are research "
    "classifications, never buy/sell/short recommendations. Responses carry a required "
    "compliance block and explicit limitations; a missing ticker returns a status='no_data' "
    "envelope (still compliant), not an error."
)


def _get(base_url: str, path: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    clean = {k: v for k, v in params.items() if v is not None}
    r = httpx.get(f"{base_url.rstrip('/')}{path}", params=clean, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_why(
    ticker: str,
    *,
    as_of: Optional[str] = None,
    include_score: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """GET /v1/why → ResearchResponse dict (status='no_data' envelope if absent)."""
    return _get(base_url, f"/v1/why/{ticker.upper()}",
                {"as_of": as_of, "include_score": include_score}, timeout)


def get_memo(
    ticker: str,
    *,
    as_of: Optional[str] = None,
    include_score: bool = False,
    n_evidence: int = 20,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """GET /v1/memo → MemoOutput dict {ticker, signal, grade, mode, markdown, response}."""
    return _get(base_url, f"/v1/memo/{ticker.upper()}",
                {"as_of": as_of, "include_score": include_score, "n_evidence": n_evidence}, timeout)
