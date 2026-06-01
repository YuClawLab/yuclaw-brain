"""
LlamaIndex integration for YUCLAW — ultra-thin tools + a citing retriever.

Makes YUCLAW a first-class, citable source inside a LlamaIndex RAG/agent:

    yuclaw_function_tools()  -> [FunctionTool(yuclaw_why), FunctionTool(yuclaw_memo)]
    YuclawTool(...)          -> the yuclaw_why FunctionTool (convenience)
    YuclawRetriever(...)     -> BaseRetriever; query_str = ticker. Returns one TextNode
                               per evidence item, each carrying citation metadata:
                               source_url, accession_number, ledger_hash, event_type,
                               available_as_of, ticker, as_of.

So an agent can answer "why is AMD neutral?" and cite the individual SEC filings
behind each point via the standard LlamaIndex citation pattern.

Score is gated OFF by default (Q3). A missing ticker yields a status='no_data'
envelope (Q4): the retriever simply returns zero nodes.

Example:
    from llama_index.core import VectorStoreIndex
    from v4.integrations.llamaindex_yuclaw import YuclawRetriever, yuclaw_function_tools

    nodes = YuclawRetriever().retrieve("AMD")          # -> NodeWithScore per filing
    tools = yuclaw_function_tools()                    # for a FunctionAgent / ReActAgent

Set YUCLAW_API_URL (default http://127.0.0.1:8088) to point at your YUCLAW API.
"""
from __future__ import annotations

from typing import Any, Optional

from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.core.tools import FunctionTool

from v4.integrations._client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    EVIDENCE_FIRST_BLURB,
    get_memo,
    get_why,
)

# Keep hashes/ids out of the embedding text (they're for citation, not similarity),
# but retain them in metadata so the agent can cite them.
_EXCLUDE_FROM_EMBED = ["ledger_hash", "accession_number", "source_url", "ticker", "as_of"]


class YuclawRetriever(BaseRetriever):
    """Retrieve YUCLAW evidence for a ticker as citable LlamaIndex nodes.

    query_bundle.query_str is the ticker (e.g. "AMD"). One TextNode per evidence item.
    """

    def __init__(
        self,
        *,
        as_of: Optional[str] = None,
        include_score: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._as_of = as_of
        self._include_score = include_score
        self._base_url = base_url
        self._timeout = timeout
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        ticker = query_bundle.query_str.strip().upper()
        why = get_why(ticker, as_of=self._as_of, include_score=self._include_score,
                      base_url=self._base_url, timeout=self._timeout)
        out: list[NodeWithScore] = []
        for e in why.get("evidence", []):
            text = (e.get("raw_excerpt")
                    or f"{e.get('event_type', 'EVENT')} for {why['ticker']}").strip()
            node = TextNode(
                id_=e.get("event_id"),
                text=text,
                metadata={
                    "source_url": e.get("source_url"),
                    "accession_number": e.get("accession_number"),
                    "ledger_hash": e.get("ledger_hash"),
                    "event_type": e.get("event_type"),
                    "available_as_of": e.get("available_as_of"),
                    "ticker": why["ticker"],
                    "as_of": why["as_of"],
                },
                excluded_embed_metadata_keys=_EXCLUDE_FROM_EMBED,
                excluded_llm_metadata_keys=["ledger_hash"],
            )
            mag = e.get("magnitude") or 0.0
            conf = e.get("llm_confidence") or 0.0
            out.append(NodeWithScore(node=node, score=(float(mag * conf) or None)))
        return out


def yuclaw_function_tools(
    *,
    include_score: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[FunctionTool]:
    """Build [yuclaw_why, yuclaw_memo] FunctionTools for a LlamaIndex agent."""

    def yuclaw_why(ticker: str, as_of: Optional[str] = None, include_cascade: bool = False) -> dict[str, Any]:
        return get_why(ticker, as_of=as_of, include_score=include_score,
                       include_cascade=include_cascade, base_url=base_url, timeout=timeout)

    def yuclaw_memo(ticker: str, as_of: Optional[str] = None, n_evidence: int = 20) -> dict[str, Any]:
        return get_memo(ticker, as_of=as_of, include_score=include_score,
                        n_evidence=n_evidence, base_url=base_url, timeout=timeout)

    why_tool = FunctionTool.from_defaults(
        fn=yuclaw_why, name="yuclaw_why",
        description="YUCLAW structured research signal for a ticker. " + EVIDENCE_FIRST_BLURB,
    )
    memo_tool = FunctionTool.from_defaults(
        fn=yuclaw_memo, name="yuclaw_memo",
        description="YUCLAW Markdown research memo for a ticker. " + EVIDENCE_FIRST_BLURB,
    )
    return [why_tool, memo_tool]


def YuclawTool(*, include_score: bool = False, base_url: str = DEFAULT_BASE_URL,
               timeout: float = DEFAULT_TIMEOUT) -> FunctionTool:
    """Convenience: the yuclaw_why FunctionTool."""
    return yuclaw_function_tools(include_score=include_score, base_url=base_url, timeout=timeout)[0]


__all__ = ["YuclawRetriever", "yuclaw_function_tools", "YuclawTool"]
