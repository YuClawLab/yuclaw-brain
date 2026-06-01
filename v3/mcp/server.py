"""
YUCLAW MCP v2 server (stdio) — on the unified v4 schema.

Two PRIMARY research tools, both produced by the single v4 assembler
(v4.api.builder.build_response) — no local response stamping, no divergence:

    yuclaw_why(ticker, as_of=None, include_score=False)
        → structured ResearchResponse (signal + 9 components + evidence + ledger hashes)
    yuclaw_memo(ticker, as_of=None, include_score=False, n_evidence=20)
        → MemoOutput (Markdown research memo + the compact ResearchResponse)

Plus three AUXILIARY read-only tools retained from v3 (distinct utilities, not
research signals): yuclaw_universe, yuclaw_validation, yuclaw_verify.

Every research response carries a REQUIRED compliance block. Signal labels are
research classifications — never SELL or SHORT. Missing data returns a full
status='no_data' envelope (with compliance), never a bare error.

Run:
    python3 -m v3.mcp.server            # stdio (Claude Desktop, etc.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

import yuclaw_py
from yuclaw_py._compliance import COMPLIANCE

from v3.proof.verify import verify as proof_verify
from v4.api.builder import build_response
from v4.memo.generator import generate_memo

_INSTRUCTIONS = (
    "YUCLAW is an evidence-first financial research tool. Every signal is a RESEARCH "
    "CLASSIFICATION, not investment advice and never a buy/sell/short recommendation. "
    "Every claim is backed by a source SEC filing and a ledger hash; surface those when "
    "you cite YUCLAW. Always preserve the `compliance` block and `limitations` from any "
    "response in what you show the user. When `status` is 'no_data', say so plainly — do "
    "not invent a signal."
)

mcp = FastMCP("yuclaw", instructions=_INSTRUCTIONS)

# Auxiliary tools still read via the SDK Client (universe/validation are not signals).
_CLIENT = yuclaw_py.Client(source="postgres", dsn="dbname=yuclaw_events")
_DSN = "dbname=yuclaw_events"


def _parse_as_of(as_of: Optional[str]) -> Optional[datetime]:
    if not as_of:
        return None
    dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# PRIMARY research tools (unified schema)
# ---------------------------------------------------------------------------
@mcp.tool()
def yuclaw_why(
    ticker: str, as_of: Optional[str] = None, include_score: bool = False
) -> dict[str, Any]:
    """Structured, evidence-first research signal for a ticker (the full ResearchResponse).

    Returns the locked signal label (STRONG_BULLISH / BULLISH / NEUTRAL / WATCH /
    WEAKENING / RISK_ALERT / NEGATIVE_EVENT / BEARISH_WATCH — never SELL or SHORT),
    a graded confidence (A/B/C/Insufficient), the 9 component anatomies with rationale,
    and an `evidence` array where EVERY item carries a source_url, SEC accession_number,
    and ledger_hash so the answer is independently verifiable.

    Args:
        ticker: e.g. "AMD".
        as_of: optional ISO-8601 instant for point-in-time replay (default: latest).
        include_score: default False — the label + grade lead; set True to also return
            the raw composite score.

    Missing data returns a full status='no_data' envelope (with compliance), not an error.
    Research/education only — not investment advice."""
    resp = build_response(ticker, as_of=_parse_as_of(as_of), include_score=include_score)
    return resp.model_dump(mode="json")


@mcp.tool()
def yuclaw_memo(
    ticker: str,
    as_of: Optional[str] = None,
    include_score: bool = False,
    n_evidence: int = 20,
) -> dict[str, Any]:
    """A ready-to-read Markdown research memo for a ticker, plus the compact ResearchResponse.

    The memo leads with the signal + Evidence Quality Grade, explains each component, lists
    the numbered evidence trail (with source filings + ledger hashes), states explicit
    limitations, and ends with the required compliance notice. Insufficient-grade tickers
    render as a conservative "evidence-limited research note"; RISK_ALERT tickers lead with
    the triggering regulatory/legal event.

    Args:
        ticker: e.g. "AMD".
        as_of: optional ISO-8601 instant for point-in-time replay.
        include_score: default False (memos are score-free prose); True surfaces numbers.
        n_evidence: evidence items to include (default 20, capped at 50).

    Returns {ticker, signal, grade, mode, markdown, response}. The `response` holds the
    structured ResearchResponse including the compliance block.
    Research/education only — not investment advice."""
    memo = generate_memo(ticker, as_of=_parse_as_of(as_of),
                         include_score=include_score, n_evidence=n_evidence)
    return memo.model_dump(mode="json")


# ---------------------------------------------------------------------------
# AUXILIARY read-only tools (retained from v3)
# ---------------------------------------------------------------------------
@mcp.tool()
def yuclaw_universe() -> dict[str, Any]:
    """The tickers YUCLAW tracks (equities + sector ETFs + broad ETFs + macro).

    Research/education only — not investment advice."""
    return {"universe": _CLIENT.universe(), "compliance": dict(COMPLIANCE)}


@mcp.tool()
def yuclaw_validation() -> dict[str, Any]:
    """In-Sample Event Validation panel + out-of-sample Forward Tracking Ledger.

    Returns two record lists: `in_sample` and `forward` (return_1d/5d/20d, hit_1d/5d/20d,
    excess vs SPY). Hit rates MUST be shown with their `n` — never headline a percentage
    alone; small-n panels are preliminary. See docs/methodology/backfill.md for the
    in-sample reconstruction caveat.

    Research/education only — not investment advice."""
    panels = _CLIENT.validation()
    out: dict[str, Any] = {}
    for name in ("in_sample", "forward"):
        df = panels[name]
        if "signal_date" in df.columns:
            df = df.copy()
            df["signal_date"] = df["signal_date"].astype(str)
        out[name] = df.where(df.notna(), None).to_dict(orient="records")
    out["compliance"] = dict(COMPLIANCE)
    return out


@mcp.tool()
def yuclaw_verify(ticker: str, date: str) -> dict[str, Any]:
    """Verified Research Ledger check for `ticker` on `date` (YYYY-MM-DD).

    Recomputes the content_hash from the live row and reports VERIFIED /
    INTEGRITY_FAILURE / NOT_FOUND. Verifies record integrity and timing — not
    investment merit.

    Research/education only — not investment advice."""
    return {**proof_verify(ticker, date), "compliance": dict(COMPLIANCE)}


# ---------------------------------------------------------------------------
def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
