"""
v4/auth/keys.py — API key management + request metering (Postgres-backed).

The full secret is shown exactly once at creation and NEVER stored — only its
SHA-256 hash is kept, so a database leak does not expose usable keys. Metering is
REST-only; nothing here is invoked by the CLI/MCP/in-process SDK paths.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

DSN = "dbname=yuclaw_events"

# Quotas (UTC day).
FREE_TIER_DAILY = 100        # per authenticated key
ANON_TIER_DAILY = 20         # per IP for unauthenticated traffic


@dataclass(frozen=True)
class APIKey:
    key_id: str
    owner_email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _conn(dsn: str):
    return psycopg2.connect(dsn)


# --------------------------------------------------------------------------- #
# lifecycle
# --------------------------------------------------------------------------- #
def create_api_key(owner_email: Optional[str] = None, notes: Optional[str] = None,
                   *, dsn: str = DSN) -> tuple[str, str]:
    """Create a key. Returns (key_id, secret_full). The secret is shown ONCE."""
    key_id = "key_" + secrets.token_hex(8)
    secret_full = "yks_" + secrets.token_urlsafe(32)
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO api_keys (key_id, key_hash, owner_email, notes) VALUES (%s, %s, %s, %s)",
            (key_id, _hash(secret_full), owner_email, notes),
        )
        c.commit()
    return key_id, secret_full


def validate_api_key(secret_full: str, *, dsn: str = DSN) -> Optional[APIKey]:
    """Return the APIKey for a valid, active, unexpired secret; else None."""
    if not secret_full:
        return None
    with _conn(dsn) as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT key_id, owner_email, notes, created_at, expires_at, is_active
               FROM api_keys
               WHERE key_hash = %s AND is_active = true
                 AND (expires_at IS NULL OR expires_at > now())""",
            (_hash(secret_full),),
        )
        row = cur.fetchone()
    return APIKey(**row) if row else None


def revoke_api_key(key_id: str, *, dsn: str = DSN) -> bool:
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute("UPDATE api_keys SET is_active = false WHERE key_id = %s", (key_id,))
        c.commit()
        return cur.rowcount > 0


def list_keys(*, dsn: str = DSN) -> list[APIKey]:
    with _conn(dsn) as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT key_id, owner_email, notes, created_at, expires_at, is_active "
            "FROM api_keys ORDER BY created_at DESC"
        )
        return [APIKey(**r) for r in cur.fetchall()]


# --------------------------------------------------------------------------- #
# metering
# --------------------------------------------------------------------------- #
def log_request(key_id: Optional[str], client_ip: Optional[str], endpoint: str,
                ticker: Optional[str], status_code: int, *, dsn: str = DSN) -> None:
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO request_logs (key_id, client_ip, endpoint, ticker, status_code) "
            "VALUES (%s, %s, %s, %s, %s)",
            (key_id, client_ip, endpoint, ticker, status_code),
        )
        c.commit()


def get_daily_count(key_id: str, *, dsn: str = DSN) -> int:
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM request_logs WHERE key_id = %s "
            "AND date_trunc('day', ts AT TIME ZONE 'UTC') = date_trunc('day', now() AT TIME ZONE 'UTC')",
            (key_id,),
        )
        return cur.fetchone()[0]


def get_ip_daily_count(client_ip: str, *, dsn: str = DSN) -> int:
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM request_logs WHERE key_id IS NULL AND client_ip = %s "
            "AND date_trunc('day', ts AT TIME ZONE 'UTC') = date_trunc('day', now() AT TIME ZONE 'UTC')",
            (client_ip,),
        )
        return cur.fetchone()[0]


def usage(key_id: str, days: int = 7, *, dsn: str = DSN) -> dict:
    """Per-day request counts for the last `days` (CLI / /v1/keys/usage)."""
    with _conn(dsn) as c, c.cursor() as cur:
        cur.execute(
            """SELECT to_char(date_trunc('day', ts AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS day, count(*)
               FROM request_logs
               WHERE key_id = %s AND ts >= now() - (%s || ' days')::interval
               GROUP BY 1 ORDER BY 1 DESC""",
            (key_id, days),
        )
        by_day = {r[0]: r[1] for r in cur.fetchall()}
    return {"key_id": key_id, "daily_today": get_daily_count(key_id, dsn=dsn),
            "daily_limit": FREE_TIER_DAILY, "by_day": by_day}


__all__ = [
    "APIKey", "DSN", "FREE_TIER_DAILY", "ANON_TIER_DAILY",
    "create_api_key", "validate_api_key", "revoke_api_key", "list_keys",
    "log_request", "get_daily_count", "get_ip_daily_count", "usage",
]
