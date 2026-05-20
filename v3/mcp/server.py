"""
YUCLAW MCP server (stdio).

Exposes seven read-only tools backed directly by the yuclaw_py SDK:

    yuclaw_signal(ticker)
    yuclaw_why(ticker, n_evidence=5)
    yuclaw_replay(ticker, date)
    yuclaw_backtest()
    yuclaw_events(ticker, since=None)
    yuclaw_universe()
    yuclaw_verify(ticker, date)

Every tool response embeds the locked compliance payload
    {"not_advice": True, "research_only": True, "not_registered_adviser": True}
and the public-label validator from the SDK refuses to emit any label
outside the locked vocabulary (no SELL, no SHORT — ever).

Each tool's MCP description ends with the locked footer text
"Research/education only — not investment advice." baked into the
docstring at definition time so MCP clients see it when they list tools.

Run:
    python3 -m v3.mcp.server                # stdio mode (Claude Desktop, etc.)
"""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

import yuclaw_py
from yuclaw_py._client import _validate_label
from yuclaw_py._compliance import COMPLIANCE, COMPLIANCE_NOTICE

from v3.proof.verify import verify as proof_verify

mcp = FastMCP("yuclaw")

# Single Client instance — psycopg2 connections inside PostgresBackend are
# short-lived (open/close per call), so this is safe to share.
_CLIENT = yuclaw_py.Client(source="postgres", dsn="dbname=yuclaw_events")


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    """Add compliance + notice to a signal-bearing response."""
    if "label" in payload:
        _validate_label(payload["label"])
    out = dict(payload)
    out["compliance"] = dict(COMPLIANCE)
    out["compliance_notice"] = COMPLIANCE_NOTICE
    return out


# ---------------------------------------------------------------------------
@mcp.tool()
def yuclaw_signal(ticker: str) -> dict[str, Any]:
    """Latest YUCLAW composite signal for a ticker, plus the 9 component scores.

    Returns label (one of STRONG_BUY / BUY / HOLD / WATCH / WEAKENING /
    NEGATIVE_EVENT / DOWNSIDE_WATCH / RISK_ALERT — never SELL or SHORT),
    score in [-1, 1], signal_time, and c1..c9.

    Research/education only — not investment advice."""
    try:
        return _stamp(_CLIENT.signal(ticker))
    except LookupError as e:
        return {"error": "not_found", "detail": str(e), "compliance": dict(COMPLIANCE)}


@mcp.tool()
def yuclaw_why(ticker: str, n_evidence: int = 5) -> dict[str, Any]:
    """Signal for `ticker` plus the top `n_evidence` material events that informed it,
    each with event_type, magnitude, direction, raw_excerpt, and source_url.

    The evidence trail is what makes this signal explainable, not the score alone.

    Research/education only — not investment advice."""
    try:
        return _stamp(_CLIENT.why(ticker, n_evidence=n_evidence))
    except LookupError as e:
        return {"error": "not_found", "detail": str(e), "compliance": dict(COMPLIANCE)}


@mcp.tool()
def yuclaw_replay(ticker: str, date: str) -> dict[str, Any]:
    """Point-in-time YUCLAW signal as it would have looked at the end of `date`
    (YYYY-MM-DD). Uses only data available on or before that date.

    Useful for evidence-trail reproducibility checks. Returns the same shape as
    yuclaw_signal plus a `replay_as_of` field.

    Research/education only — not investment advice."""
    try:
        return _stamp(_CLIENT.replay(ticker, date))
    except LookupError as e:
        return {"error": "not_found", "detail": str(e), "compliance": dict(COMPLIANCE)}
    except ValueError as e:
        return {"error": "bad_date", "detail": str(e), "compliance": dict(COMPLIANCE)}


@mcp.tool()
def yuclaw_backtest() -> dict[str, Any]:
    """In-sample backtest panel + out-of-sample forward-tracking ledger.

    Returns two tables (as records lists): `backtest` and `forward`. Each row
    carries return_1d / 5d / 20d, hit_1d / 5d / 20d, and excess returns vs SPY.

    Caveat: the in-sample panel was reconstructed via point-in-time replay
    with market components C1/C3/C4/C5/C7 running at 0.3 confidence (the
    upstream dashboard cache holds only the latest market snapshot). The
    in-sample numbers therefore primarily reflect the evidence layer
    (C6/C8/C9). See docs/methodology/backfill.md.

    Research/education only — not investment advice."""
    panels = _CLIENT.backtest()
    backfill_df = panels["backtest"]
    forward_df = panels["forward"]
    for df in (backfill_df, forward_df):
        if "signal_date" in df.columns:
            df["signal_date"] = df["signal_date"].astype(str)
    return {
        "backtest": backfill_df.where(backfill_df.notna(), None).to_dict(orient="records"),
        "forward":  forward_df.where(forward_df.notna(), None).to_dict(orient="records"),
        "compliance": dict(COMPLIANCE),
        "compliance_notice": COMPLIANCE_NOTICE,
    }


@mcp.tool()
def yuclaw_events(ticker: str, since: Optional[str] = None) -> dict[str, Any]:
    """Evidence events for `ticker` (SEC filings, insider trades, M&A, cascade
    children). `since` is an optional ISO date — only events with
    available_as_of >= since are returned.

    Each event row includes the source_url so it can be traced back to the SEC
    filing or other primary record.

    Research/education only — not investment advice."""
    df = _CLIENT.events(ticker, since=since)
    if "available_as_of" in df.columns:
        df["available_as_of"] = df["available_as_of"].astype(str)
    return {
        "ticker": ticker.upper(),
        "n": len(df),
        "events": df.where(df.notna(), None).to_dict(orient="records"),
        "compliance": dict(COMPLIANCE),
    }


@mcp.tool()
def yuclaw_universe() -> dict[str, Any]:
    """The list of tickers YUCLAW v3.0 tracks (equities + sector ETFs +
    broad ETFs + macro).

    Research/education only — not investment advice."""
    return {"universe": _CLIENT.universe(), "compliance": dict(COMPLIANCE)}


@mcp.tool()
def yuclaw_verify(ticker: str, date: str) -> dict[str, Any]:
    """Verified Research Ledger check for `ticker` on `date`.

    Looks up the ledger entry, recomputes the content_hash from the live
    database row, and reports VERIFIED / INTEGRITY_FAILURE / NOT_FOUND.
    Verifies record integrity and timing — not investment merit.

    Research/education only — not investment advice."""
    result = proof_verify(ticker, date)
    return {**result, "compliance": dict(COMPLIANCE)}


# ---------------------------------------------------------------------------
def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
