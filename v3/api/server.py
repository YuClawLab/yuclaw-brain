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
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Reuse the SDK's query backend so API + SDK agree by construction.
from yuclaw_py._backends import PostgresBackend
from yuclaw_py._client import _validate_label
from yuclaw_py._compliance import COMPLIANCE, COMPLIANCE_NOTICE

_log = logging.getLogger("yuclaw.api")

API_VERSION = "3.0.0"
DSN = "dbname=yuclaw_events"

app = FastAPI(
    title="YUCLAW API",
    version=API_VERSION,
    description=(
        "Research / education only. Not investment advice. "
        "Signal labels are research classifications, not buy/sell recommendations. "
        "YUCLAW is not a registered investment adviser."
    ),
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
    return {"status": "ok" if db_ok else "degraded",
            "db_ok": db_ok,
            "version": API_VERSION,
            "compliance": dict(COMPLIANCE)}


@app.get("/universe")
def universe() -> dict[str, Any]:
    return {"universe": _backend().universe(),
            "compliance": dict(COMPLIANCE)}


@app.get("/signal/{ticker}")
def signal(ticker: str) -> dict[str, Any]:
    try:
        return _stamp(_backend().signal(ticker))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/why/{ticker}")
def why(ticker: str, n_evidence: int = Query(5, ge=1, le=20)) -> dict[str, Any]:
    try:
        sig = _backend().signal(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    evidence = _backend().evidence(ticker, limit=n_evidence)
    return _stamp({**sig, "evidence": evidence})


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
