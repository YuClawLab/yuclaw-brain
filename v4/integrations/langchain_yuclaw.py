"""
LangChain integration for YUCLAW — ultra-thin tools over the v4 REST API.

Two tools, both returning the structured ResearchResponse (Q2) so an agent can
reason over signal + components + evidence (+ ledger hashes for citation):

    YuclawWhyTool   — structured research signal. include_memo=True also attaches
                      the rendered Markdown memo under `memo_markdown` (Q2).
    YuclawMemoTool  — the full MemoOutput (markdown + compact response).

Both gate the raw score OFF by default (Q3, include_score). A missing ticker
returns a status='no_data' envelope, not an error (Q4) — agents branch on `status`.

Example:
    from langchain.agents import create_react_agent       # or your agent factory
    from v4.integrations.langchain_yuclaw import YuclawWhyTool, YuclawMemoTool

    agent = create_react_agent(llm, [YuclawWhyTool(), YuclawMemoTool()])
    # YuclawWhyTool().invoke({"ticker": "AMD"}) -> ResearchResponse dict

Set YUCLAW_API_URL (default http://127.0.0.1:8088) to point at your YUCLAW API.
"""
from __future__ import annotations

from typing import Any, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from v4.integrations._client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    EVIDENCE_FIRST_BLURB,
    get_memo,
    get_why,
)


class _WhyArgs(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. 'AMD'")
    as_of: Optional[str] = Field(None, description="ISO-8601 instant for point-in-time replay")
    include_score: bool = Field(False, description="Include the raw composite score (default off)")
    include_cascade: bool = Field(False, description="Attach the supply-chain cascade tree (default off)")
    include_memo: bool = Field(False, description="Also attach a rendered Markdown memo under 'memo_markdown'")


class _MemoArgs(BaseModel):
    ticker: str = Field(..., description="Ticker symbol, e.g. 'AMD'")
    as_of: Optional[str] = Field(None, description="ISO-8601 instant for point-in-time replay")
    include_score: bool = Field(False, description="Include numeric scores (default off)")
    n_evidence: int = Field(20, ge=1, le=50, description="Evidence items in the memo (default 20, max 50)")


class YuclawWhyTool(BaseTool):
    """Structured YUCLAW research signal for a ticker."""
    name: str = "yuclaw_why"
    description: str = (
        "Get YUCLAW's structured research signal for a stock ticker: a research "
        "classification label (never buy/sell), a graded confidence (A/B/C/Insufficient), "
        "nine scored components with rationale, and an evidence array. " + EVIDENCE_FIRST_BLURB
    )
    args_schema: Type[BaseModel] = _WhyArgs
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    api_key: Optional[str] = None

    def _run(self, ticker: str, as_of: Optional[str] = None, include_score: bool = False,
             include_cascade: bool = False, include_memo: bool = False, **_: Any) -> dict[str, Any]:
        if include_memo:
            memo = get_memo(ticker, as_of=as_of, include_score=include_score,
                            base_url=self.base_url, timeout=self.timeout, api_key=self.api_key)
            out = dict(memo["response"])
            out["memo_markdown"] = memo["markdown"]
            return out
        return get_why(ticker, as_of=as_of, include_score=include_score, include_cascade=include_cascade,
                       base_url=self.base_url, timeout=self.timeout, api_key=self.api_key)


class YuclawMemoTool(BaseTool):
    """A ready-to-read YUCLAW Markdown research memo for a ticker."""
    name: str = "yuclaw_memo"
    description: str = (
        "Get a ready-to-read Markdown research memo for a ticker (headline signal + grade, "
        "component anatomy, numbered evidence trail with source filings, limitations, and the "
        "compliance notice), plus the structured response. " + EVIDENCE_FIRST_BLURB
    )
    args_schema: Type[BaseModel] = _MemoArgs
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    api_key: Optional[str] = None

    def _run(self, ticker: str, as_of: Optional[str] = None,
             include_score: bool = False, n_evidence: int = 20, **_: Any) -> dict[str, Any]:
        return get_memo(ticker, as_of=as_of, include_score=include_score, n_evidence=n_evidence,
                        base_url=self.base_url, timeout=self.timeout, api_key=self.api_key)


__all__ = ["YuclawWhyTool", "YuclawMemoTool"]
