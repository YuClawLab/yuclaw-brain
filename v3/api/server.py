"""
v3.0 REST API — FastAPI app mirroring the yuclaw-py SDK surface.

Routes:
    GET /health
    GET /universe
    GET /signal/{ticker}
    GET /why/{ticker}
    GET /replay/{ticker}?date=YYYY-MM-DD
    GET /events/{ticker}?since=YYYY-MM-DD
    GET /backtest

Query logic is delegated to the SDK's PostgresBackend so the API and the
SDK can never diverge on what "signal" means. The API wraps responses
with the locked compliance dict + the locked not-advice footer string.
Unknown-ticker LookupError → clean 404, never a 500 traceback.

Run locally:
    python3 -m uvicorn v3.api.server:app --host 0.0.0.0 --port 8088
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Reuse the SDK's query backend so API + SDK agree by construction.
from yuclaw_py._backends import PostgresBackend
from yuclaw_py._client import _validate_label
from yuclaw_py._compliance import COMPLIANCE
from v4.api.schema import COMPLIANCE_NOTICE  # canonical not-advice wording (Day 9)

# v4 unified contract — the single assembler + schema (Day 2) + memo (Day 3).
from v4.api.builder import build_response
from v4.api.schema import ResearchResponse
from v4.memo.generator import MemoOutput, generate_memo

# v4 auth + metering (Day 8) — REST-only.
from v4.auth import keys as authkeys
from v4.auth.dependency import (
    MeteringMiddleware,
    SignalHTTPError,
    metered_identity,
    require_api_key,
)

_log = logging.getLogger("yuclaw.api")

API_VERSION = "3.0.0"
DSN = "dbname=yuclaw_events"

app = FastAPI(
    title="YUCLAW API",
    version=API_VERSION,
    description=COMPLIANCE_NOTICE,  # canonical (Day 9 single source of truth)
)

# CORS: allow the dashboard origin (github pages), the SDK from anywhere,
# and the local dev console. Wide-open for v3.0 since responses contain no
# private data and the methods are GET-only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)
# Day 8: log metered requests after the handler (REST-only).
app.add_middleware(MeteringMiddleware)


@app.exception_handler(SignalHTTPError)
async def _signal_http_error(request: Request, exc: SignalHTTPError) -> JSONResponse:
    """Render auth/quota denials with their prepared body (compliance-bearing for signal paths)."""
    return JSONResponse(status_code=exc.status_code, content=exc.content, headers=exc.headers)


def _backend() -> PostgresBackend:
    """One backend per request — psycopg2 connections inside the backend
    are short-lived (open/close per call), so no shared-state risk."""
    return PostgresBackend(dsn=DSN)


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    """Add locked compliance dict + footer to any signal-bearing response."""
    if "label" in payload:
        _validate_label(payload["label"])
    out = dict(payload)
    out["compliance"] = dict(COMPLIANCE)
    out["compliance_notice"] = COMPLIANCE_NOTICE
    return out


# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, Any]:
    import psycopg2
    db_ok = False
    try:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            db_ok = cur.fetchone()[0] == 1
    except Exception as e:
        _log.warning("health DB probe failed: %s", e)
    # Day 9 (Q2): metadata endpoint — NO compliance block (reserved for signal data).
    return {"status": "ok" if db_ok else "degraded",
            "db_ok": db_ok,
            "version": API_VERSION}


@app.get("/universe")
def universe() -> dict[str, Any]:
    # Metadata — NO compliance block (Q2).
    return {"universe": _backend().universe()}


def _deprecate(response: Response, successor: str) -> None:
    """RFC 8594 deprecation signaling on a legacy v3 route."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{successor}>; rel="successor-version"'


@app.get("/signal/{ticker}", deprecated=True)
def signal(ticker: str, response: Response) -> dict[str, Any]:
    _deprecate(response, f"/v1/signal/{ticker.upper()}")
    try:
        return _stamp(_backend().signal(ticker))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/why/{ticker}", deprecated=True)
def why(ticker: str, response: Response, n_evidence: int = Query(5, ge=1, le=20)) -> dict[str, Any]:
    _deprecate(response, f"/v1/why/{ticker.upper()}")
    try:
        sig = _backend().signal(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    evidence = _backend().evidence(ticker, limit=n_evidence)
    return _stamp({**sig, "evidence": evidence})


# --------------------------------------------------------------------------- #
# v4 unified contract (Day 2). Both return the single ResearchResponse.
# Q2: score is gated OFF by default for REST; opt in with ?include_score=true.
# --------------------------------------------------------------------------- #
def _parse_as_of(as_of: Optional[str]) -> Optional[datetime]:
    if not as_of:
        return None
    # Bare date → end of that day (captures that day's intraday snapshot), matching
    # the CLI and `yuclaw verify <date>`.
    if len(as_of) == 10 and as_of.count("-") == 2:
        as_of = f"{as_of}T23:59:59-06:00"
    try:
        dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"as_of must be ISO-8601: {as_of!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# Day 8: signal endpoints are metered (anonymous tier allowed; key for full quota).
@app.get("/v1/signal/{ticker}", response_model=ResearchResponse)
def v1_signal(ticker: str, include_score: bool = Query(False),
              _id: Optional[str] = Depends(metered_identity)) -> ResearchResponse:
    # Q1: missing data returns a status='no_data' envelope (200), never a bare 404.
    return build_response(ticker, include_score=include_score)


@app.get("/v1/why/{ticker}", response_model=ResearchResponse)
def v1_why(
    ticker: str,
    n_evidence: int = Query(10, ge=1, le=50),
    include_score: bool = Query(False),
    include_cascade: bool = Query(False, description="Day 6: attach the supply-chain cascade tree"),
    as_of: Optional[str] = Query(None, description="ISO-8601 instant for point-in-time replay"),
    _id: Optional[str] = Depends(metered_identity),
) -> ResearchResponse:
    return build_response(ticker, as_of=_parse_as_of(as_of), include_score=include_score,
                          include_cascade=include_cascade, n_evidence=n_evidence)


@app.get("/v1/cascade/{ticker}")
def v1_cascade(
    ticker: str,
    depth: int = Query(3, ge=1, le=3, description="Max hops 1..3 (locked decay)"),
    as_of: Optional[str] = Query(None, description="ISO-8601 instant for point-in-time"),
    _id: Optional[str] = Depends(metered_identity),
) -> dict[str, Any]:
    """Supply-chain cascade tree that propagated into `ticker`. `cascade: null` if none.
    Edge weights are the public supply_chain.py graph. Research only — not advice."""
    from v4.api.cascade_builder import build_cascade
    node = build_cascade(ticker, as_of=_parse_as_of(as_of), depth=depth)
    return {"ticker": ticker.upper(),
            "cascade": (node.model_dump(mode="json") if node else None),
            "compliance": dict(COMPLIANCE)}


@app.get("/v1/memo/{ticker}", response_model=MemoOutput)
def v1_memo(
    ticker: str,
    n_evidence: int = Query(20, ge=1, le=50, description="Memo default 20 (Q2)"),
    include_score: bool = Query(False),
    as_of: Optional[str] = Query(None, description="ISO-8601 instant for point-in-time replay"),
    _id: Optional[str] = Depends(metered_identity),
) -> MemoOutput:
    # Wrapper object: Markdown memo + the full ResearchResponse (compliance inside it).
    # no_data is handled inside generate_memo → always a complete, compliant envelope.
    return generate_memo(ticker, as_of=_parse_as_of(as_of),
                         include_score=include_score, n_evidence=n_evidence)


@app.get("/v1/verify/{ticker}")
def v1_verify(ticker: str, date: str = Query(..., description="YYYY-MM-DD"),
              _id: Optional[str] = Depends(metered_identity)) -> dict[str, Any]:
    """Verified Research Ledger integrity check (metered). Research only — not advice."""
    from v3.proof.verify import verify as proof_verify
    return {**proof_verify(ticker, date), "compliance": dict(COMPLIANCE)}


# --- Always-free, no-auth metadata (Q4) ---
@app.get("/v1/universe")
def v1_universe() -> dict[str, Any]:
    return {"universe": _backend().universe()}


@app.get("/v1/openapi.json")
def v1_openapi() -> dict[str, Any]:
    return app.openapi()


# --- Account endpoints (Q5: NO compliance — pure account info) ---
@app.get("/v1/keys/info")
def v1_keys_info(key: authkeys.APIKey = Depends(require_api_key)) -> dict[str, Any]:
    return {"key_id": key.key_id, "owner_email": key.owner_email,
            "created_at": key.created_at.isoformat(), "is_active": key.is_active,
            "daily_limit": authkeys.FREE_TIER_DAILY}


@app.get("/v1/keys/usage")
def v1_keys_usage(days: int = Query(7, ge=1, le=90),
                  key: authkeys.APIKey = Depends(require_api_key)) -> dict[str, Any]:
    return authkeys.usage(key.key_id, days=days)


@app.get("/replay/{ticker}")
def replay(ticker: str, date: str = Query(..., description="YYYY-MM-DD")) -> dict[str, Any]:
    try:
        return _stamp(_backend().replay(ticker, date))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/events/{ticker}")
def events(ticker: str, since: Optional[str] = None) -> dict[str, Any]:
    df = _backend().events(ticker, since=since)
    # Convert pandas dtypes that JSON can't natively serialize. Cast dates to
    # ISO strings, numerics to float, NaN -> None.
    if "available_as_of" in df.columns:
        df = df.copy()
        df["available_as_of"] = df["available_as_of"].astype(str)
    rows = df.where(df.notna(), None).to_dict(orient="records")
    return {"ticker": ticker.upper(),
            "n": len(rows),
            "events": rows,
            "compliance": dict(COMPLIANCE)}


@app.get("/validation")
def validation() -> dict[str, Any]:
    """In-Sample Event Validation + Forward Tracking Ledger.

    Hit rates in either panel must be presented with their `n` (count)
    by any consumer of this response — never headline a percentage alone.
    """
    panels = _backend().validation()
    out: dict[str, Any] = {}
    for panel_name, df in panels.items():
        if "signal_date" in df.columns:
            df = df.copy()
            df["signal_date"] = df["signal_date"].astype(str)
        out[panel_name] = df.where(df.notna(), None).to_dict(orient="records")
    out["compliance"] = dict(COMPLIANCE)
    out["compliance_notice"] = COMPLIANCE_NOTICE
    return out
