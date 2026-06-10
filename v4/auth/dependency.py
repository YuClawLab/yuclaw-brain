"""
v4/auth/dependency.py — FastAPI auth + quota + metering for the REST layer.

REST-ONLY: nothing here runs for CLI / MCP-stdio / in-process build_response.

- metered_identity : signal endpoints. Optional Bearer key (anonymous tier allowed).
                     401 (compliance-bearing) on an INVALID key; 429 (ResearchResponse
                     rate_limited envelope, compliance present) when the daily quota is hit.
                     Stamps request.state.meter so the middleware logs the call.
- require_api_key  : /v1/keys/* account endpoints. Strict — 401 (NO compliance: account op).
- MeteringMiddleware : after the handler, logs metered calls to request_logs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, Request
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from yuclaw_py._compliance import COMPLIANCE
from v4.api.schema import ResearchResponse
from v4.auth import keys as K


class SignalHTTPError(Exception):
    """Carries a ready JSON body + status + headers; rendered by an app exception handler."""
    def __init__(self, status_code: int, content: dict, headers: Optional[dict] = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def _seconds_to_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((nxt - now).total_seconds())


def metered_identity(request: Request, authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Auth (optional) + quota for signal endpoints. Returns key_id or None (anonymous)."""
    ip = _client_ip(request)
    ticker = request.path_params.get("ticker", "?")
    token = _bearer(authorization)

    key_id: Optional[str] = None
    if token:
        key = K.validate_api_key(token)
        if key is None:
            # Denied signal request → compliance PRESENT (architectural-safety).
            raise SignalHTTPError(401, {
                "status": "unauthorized",
                "error": "invalid_api_key",
                "detail": "The provided API key is invalid, expired, or revoked.",
                "compliance": dict(COMPLIANCE),
            })
        key_id = key.key_id
        count, limit = K.get_daily_count(key_id), K.FREE_TIER_DAILY
    else:
        count, limit = K.get_ip_daily_count(ip), K.ANON_TIER_DAILY

    if count >= limit:
        retry = _seconds_to_utc_midnight()
        env = ResearchResponse.rate_limited(ticker, retry_after=retry).model_dump(mode="json")
        raise SignalHTTPError(429, env, headers={"Retry-After": str(retry)})

    # Only metered (served) requests are logged; denials above are not.
    request.state.meter = {"key_id": key_id, "client_ip": (None if key_id else ip), "ticker": ticker}
    return key_id


def require_api_key(request: Request, authorization: Optional[str] = Header(None)) -> K.APIKey:
    """Strict auth for /v1/keys/* account endpoints. Account op → NO compliance (Q5)."""
    token = _bearer(authorization)
    key = K.validate_api_key(token) if token else None
    if key is None:
        raise SignalHTTPError(401, {"error": "invalid_api_key",
                                    "detail": "A valid Authorization: Bearer <key> is required."})
    return key


class MeteringMiddleware(BaseHTTPMiddleware):
    """Logs each metered request after the handler (sync insert in a threadpool)."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        meter = getattr(request.state, "meter", None)
        if meter:
            await run_in_threadpool(
                K.log_request, meter["key_id"], meter["client_ip"],
                request.url.path, meter["ticker"], response.status_code,
            )
        return response


__all__ = ["SignalHTTPError", "metered_identity", "require_api_key", "MeteringMiddleware"]
