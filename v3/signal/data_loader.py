"""
Data loader — bridge between v3.0 signal framework and existing v2.3.0 state.

v2.3.0 publishes a single canonical artifact at
    docs/data/dashboard_state.json
that the running cron refreshes every 30 minutes. Rather than rebuild momentum,
RSI, sector velocity, and macro regime in v3.0 on Day 3, we read them out of
this file. v3.0 adds the events evidence layer on top.

Future Day 4+ work: replace this with direct reads from Postgres tables
(prices, signals, regime_history) once v2.3.0 emits those alongside the JSON.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.sources.edgar_poll import DB_DSN

# v2.3.0 lives at ~/yuclaw (cron writes here). v3.0 worktree is ~/yuclaw-v3.
# The dashboard refresher commits docs/data/dashboard_state.json on `main`.
V2_STATE_PATH = Path(
    os.environ.get(
        "YUCLAW_DASHBOARD_STATE",
        "/home/zhangd2/yuclaw/docs/data/dashboard_state.json",
    )
)

# Window over which events count toward C6. Events older than this contribute
# nothing — the recency decay handles freshness inside the window.
EVENT_LOOKBACK_DAYS = 30

# Components that read v2.3.0 dashboard_state.json (C1/C3/C4/C5/C7) only see
# the *latest* snapshot — no history. For replay calls where as_of is
# materially older than the dashboard mtime, those components can't deliver
# true point-in-time data. We treat as_of > 24h before "now" as historical
# and downgrade their confidence in compose_at().
HISTORICAL_CUTOFF_SECONDS = 24 * 3600


def is_historical(as_of: datetime) -> bool:
    """True iff `as_of` is far enough in the past that dashboard-derived
    components can no longer claim point-in-time accuracy."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - as_of).total_seconds()
    return delta > HISTORICAL_CUTOFF_SECONDS


# ---------------------------------------------------------------------------
# v2.3.0 dashboard_state.json
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _load_v2_cached(mtime_key: float) -> dict[str, Any]:
    """Cached parse — mtime_key is the file mtime, so editing the file
    invalidates the cache automatically."""
    return json.loads(V2_STATE_PATH.read_text())


def load_v2_state() -> dict[str, Any]:
    """Read docs/data/dashboard_state.json. Cached on mtime — safe to call
    once per component invocation."""
    if not V2_STATE_PATH.exists():
        raise FileNotFoundError(f"v2.3.0 dashboard state missing: {V2_STATE_PATH}")
    mtime = V2_STATE_PATH.stat().st_mtime
    return _load_v2_cached(mtime)


def _signal_row(state: dict[str, Any], ticker: str) -> Optional[dict[str, Any]]:
    for r in state.get("signals", []) or []:
        if (r.get("ticker") or "").upper() == ticker.upper():
            return r
    return None


def get_price(state: dict[str, Any], ticker: str) -> Optional[float]:
    """Latest dashboard-verified price for `ticker`. None if missing."""
    row = _signal_row(state, ticker)
    if row is None:
        return None
    p = row.get("price")
    try:
        return float(p) if p is not None else None
    except (TypeError, ValueError):
        return None


# 1-month momentum is published in the reasoning text as e.g. "mom_1m=+57.90%".
# We parse rather than recompute because v2.3.0 owns the price history and we
# don't want to maintain two copies of that math.
_MOM_1M_RE = re.compile(r"mom_1m=([+-]?\d+(?:\.\d+)?)%")


def get_mom_1m(state: dict[str, Any], ticker: str) -> Optional[float]:
    """Parse mom_1m=±X.XX% out of the reasoning array. Returns fraction
    (e.g. +0.1020 for +10.20%) or None if not present."""
    row = _signal_row(state, ticker)
    if row is None:
        return None
    reasoning = row.get("reasoning") or []
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    for line in reasoning:
        m = _MOM_1M_RE.search(str(line))
        if m:
            try:
                return float(m.group(1)) / 100.0
            except ValueError:
                return None
    return None


def get_macro_regime(state: dict[str, Any]) -> dict[str, Any]:
    """Return {'regime', 'confidence', 'indicators'} from v2.3.0 state."""
    r = state.get("regime") or {}
    return {
        "regime": (r.get("regime") or "NEUTRAL"),
        "confidence": float(r.get("confidence") or 0.0),
        "indicators": r.get("indicators") or {},
    }


def get_sector_velocity(state: dict[str, Any], etf: str) -> Optional[dict[str, Any]]:
    """Look up one sector-ETF row from sector.rotation. Returns the row dict
    or None."""
    rot = (state.get("sector") or {}).get("rotation") or []
    for r in rot:
        if (r.get("etf") or "").upper() == etf.upper():
            return r
    return None


# ---------------------------------------------------------------------------
# v3.0 events table
# ---------------------------------------------------------------------------
def fetch_events(ticker: str, as_of: datetime, lookback_days: int = EVENT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Pull accepted events for `ticker` in the lookback window, ordered
    newest-first. `as_of` is treated as the point-in-time horizon —
    events with available_as_of > as_of are excluded (no look-ahead).
    """
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT event_id, ticker, event_type, magnitude, direction,
                          available_as_of, llm_confidence, source_type,
                          raw_excerpt
                   FROM events
                   WHERE ticker = %s
                     AND event_status = 'accepted'
                     AND available_as_of <= %s
                     AND available_as_of >= %s - (%s || ' days')::interval
                   ORDER BY available_as_of DESC""",
                (ticker.upper(), as_of, as_of, str(lookback_days)),
            )
            return list(cur.fetchall())
    finally:
        conn.close()
