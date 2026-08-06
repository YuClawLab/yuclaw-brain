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
    ticker: str, as_of: Optional[str] = None,
    include_score: bool = False, include_cascade: bool = False,
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
        include_cascade: default False — set True to attach the `cascade` supply-chain
            propagation tree (which upstream event reached this ticker, with public edge weights).

    Missing data returns a full status='no_data' envelope (with compliance), not an error.
    Research/education only — not investment advice."""
    resp = build_response(ticker, as_of=_parse_as_of(as_of),
                          include_score=include_score, include_cascade=include_cascade)
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
@mcp.tool()
def yuclaw_events(ticker: str, since: Optional[str] = None) -> dict[str, Any]:
    """Accepted evidence events for a ticker (typed classifications with
    verified excerpts; derived data only — never raw vendor price data).
    since: optional YYYY-MM-DD floor. v5.1 surface; friendly no-backend
    behavior: returns {error, hint} instead of raising."""
    try:
        from v3.cli.events import fetch_events
        rows = fetch_events(ticker, since)
        return {"ticker": ticker.upper(), "n": len(rows), "events": rows[:200],
                "note": "research classifications, not recommendations"}
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}",
                "hint": "this tool reads the local YUCLAW evidence store; "
                        "see README section 'connect the local backend'"}


@mcp.tool()
def yuclaw_lens(vertical: str, lens: str) -> dict[str, Any]:
    """Lens summary data as JSON — the same derived numbers the public lens
    pages render (posture + maturity). vertical: 'canada'; lens: XEG | ZEO |
    GDX | URNM. v5.1 surface; friendly no-backend behavior."""
    try:
        from v3.lab.etf_evidence import canada_event_maturity, canada_posture
        if vertical != "canada":
            return {"error": f"unknown vertical {vertical!r}",
                    "hint": "supported: canada"}
        return {"lens": lens, "posture": canada_posture(lens),
                "maturity": canada_event_maturity(lens),
                "note": "derived statistics only"}
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}",
                "hint": "this tool reads the local YUCLAW research backend"}



# ---------------------------------------------------------------------------
# v5.3 "Ground Truth" tools (MCP v2): evidence objects, anatomy, passport,
# snapshot verification, protocol lookup. All friendly-no-backend.
# ---------------------------------------------------------------------------
@mcp.tool()
def get_evidence(ticker: str, as_of: Optional[str] = None) -> dict[str, Any]:
    """EvidenceObjects for a ticker (frozen v1 schema: excerpt, accession,
    source_hash, available_as_of). as_of applies the point-in-time filter
    available_as_of <= as_of. Resolves offline via the bundled
    published-corpus snapshot when no research node is reachable — the
    response then carries a loud 'corpus' scope block (v5.3.3, same
    fallback as the CLI). Research classifications, never advice."""
    try:
        from v3.evidence import (BackendUnavailable, evidence_objects,
                                 in_universe)
        if not in_universe(ticker):
            return {"status": "NOT_IN_COVERAGE",
                    "note": f"{ticker.upper()} is outside the 79-name "
                            f"scoring universe"}
        corpus = None
        try:
            objs = evidence_objects(ticker, as_of=as_of, limit=100)
        except BackendUnavailable:
            from v3.evidence.snapshot import snapshot_corpus
            got = snapshot_corpus(ticker)
            if got is None:
                raise
            objs, corpus = got
            if as_of:
                objs = [o for o in objs
                        if o.get("available_as_of") and
                        o["available_as_of"] <= as_of]
        out = {"ticker": ticker.upper(), "as_of": as_of,
               "n": len(objs),
               "evidence_objects": [
                   {k: v for k, v in o.items() if not k.startswith("_")}
                   for o in objs],
               "note": "research classifications, not recommendations"}
        if corpus is not None:
            out["corpus"] = corpus
        return out
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}",
                "hint": "the same objects are served at "
                        "https://yuclaw.ca/why/{TICKER}.json"}


@mcp.tool()
def get_signal_anatomy(ticker: str) -> dict[str, Any]:
    """The full classification anatomy (label, score, threshold band,
    components, coverage terms, label history) — the why/{TICKER}.json
    document."""
    try:
        import json as _json
        from pathlib import Path as _P
        f = (_P(__file__).resolve().parents[2] / "docs" / "why" /
             f"{ticker.upper().replace('.', '-')}.json")
        if not f.parent.is_dir():
            # pip installs don't bundle docs/why — a missing DIRECTORY
            # must not read as "name not covered" (v5.3.3 false-denial
            # guard, same class as the passport semantics fix)
            return {"error": "anatomy documents are not bundled with "
                             "this install",
                    "hint": f"the same document is served at "
                            f"https://yuclaw.ca/why/{ticker.upper()}.json"}
        if not f.exists():
            return {"status": "NOT_IN_COVERAGE",
                    "note": f"no anatomy document for {ticker.upper()}"}
        return _json.loads(f.read_text())
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}",
                "hint": "served at https://yuclaw.ca/why/{TICKER}.json"}


@mcp.tool()
def check_claim(ticker: Optional[str] = None,
                event_type: Optional[str] = None,
                date_range: Optional[str] = None,
                accession: Optional[str] = None,
                text: Optional[str] = None) -> dict[str, Any]:
    """Evidence Passport: deterministic claim check. Statuses:
    SOURCE_MATCHED / PARTIAL_MATCH (>=1 matched object, some elements
    missed) / UNSUPPORTED (= not found in the corpus, never a truth
    verdict) / NOT_IN_COVERAGE / NOT_PARSEABLE. Resolves offline via the
    bundled published-corpus snapshot when no research node is reachable
    (the passport then carries a loud 'corpus' scope block)."""
    try:
        from v3.cli.check_claim import (CorpusUnavailable, _parse_text,
                                        passport)
        from v3.universe_tiers import scoring_universe
        uni = set(scoring_universe())
        try:
            if text:
                claim = _parse_text(text, uni)
                return passport(text, claim,
                                claim is not None and claim["ticker"] in uni)
            if not ticker:
                return {"error": "give ticker+event_type/accession, or text"}
            dr = tuple(date_range.split("..")) if date_range else None
            claim = {"ticker": ticker.upper(),
                     "type": event_type.upper() if event_type else None,
                     "accession": accession, "date_range": dr}
            import json as _json
            return passport(
                _json.dumps({k: v for k, v in claim.items() if v}),
                claim, claim["ticker"] in uni)
        except CorpusUnavailable as exc:
            return {"error": "corpus unavailable",
                    "hint": f"corpus matching needs a YUCLAW research "
                            f"node — but this evidence is publicly "
                            f"checkable at "
                            f"https://yuclaw.ca/why/{exc.ticker}.json "
                            f"(see 'evidence_objects'; the as-of recipe "
                            f"is in capabilities.json)"}
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}",
                "hint": "install locally: pip install yuclaw && "
                        "yuclaw check-claim --help"}


@mcp.tool()
def verify_snapshot(ticker: str, date: str) -> dict[str, Any]:
    """Ledger integrity check for a published snapshot (record integrity
    and timing — not investment merit). Offline path: fetch
    /ledger/{date}.json and recompute the root."""
    return yuclaw_verify(ticker, date)


@mcp.tool()
def get_protocol(protocol_id: str) -> dict[str, Any]:
    """A protocol payload from the hash-chained registry — the
    specification locked BEFORE its statistic was computed."""
    try:
        import json as _json
        from pathlib import Path as _P
        reg = (_P(__file__).resolve().parents[2] / "registry" /
               "protocols.jsonl")
        for line in reg.read_text().splitlines():
            e = _json.loads(line)
            if (e.get("kind") == "protocol" and
                    e["payload"].get("protocol_id") == protocol_id):
                return e["payload"]
        return {"error": f"protocol {protocol_id} not found",
                "hint": "list: https://yuclaw.ca/evidence_index.json "
                        "registry block"}
    except Exception as exc:                     # noqa: BLE001
        return {"error": "backend unavailable",
                "detail": f"{type(exc).__name__}: {str(exc)[:140]}"}


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
