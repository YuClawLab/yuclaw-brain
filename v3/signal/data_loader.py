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
# v4.2 — LIVE state from Postgres price_history (replaces the frozen
# dashboard_state.json for all price-derived fields). The frozen JSON's writers
# (refresh_dashboard.sh / price_verifier.py) are unscheduled; price_history is
# now refreshed daily (cron/price_history_daily.sh). Macro regime is FROZEN with
# explicit staleness disclosure: its only upstream is the dead v2.3 macro engine
# (a Finnhub path we must not touch), and it cannot be price-derived without
# changing C4's math. This is a plumbing/source migration — component math is
# unchanged (C1 still parses mom_1m, C3 still z-scores change_pct, C4 still maps
# the regime label).
# ---------------------------------------------------------------------------
MOM_LOOKBACK_TD = 22  # trading days for 1-month momentum (calibrated to v2.3 mom_1m)

# Sector ETFs C3 compares; recomputed 1-day change from price_history.
_SECTOR_ETFS = {"XLK", "XLF", "XLE", "XLV", "XLU", "XLI", "XLY",
                "XLP", "XLB", "XLRE", "XLC", "SMH", "KRE", "IBB", "XBI"}

C4_FREEZE_DISCLOSURE = (
    "C4 macro-regime input temporarily frozen as of 2026-05-18 with staleness "
    "disclosure, pending macro engine restoration."
)


def _frozen_macro_regime() -> dict[str, Any]:
    """Last-known macro regime, FROZEN with disclosure. C4/C5's only upstream is
    the dead v2.3 macro engine (Finnhub path, no-touch); regime cannot be
    price-derived without changing C4's math, so we pass through the last-known
    value (read-only) and flag it stale. Reporting/healthcheck reads the flag."""
    try:
        s = json.loads(V2_STATE_PATH.read_text())
        r = dict(s.get("regime") or {})
    except Exception:
        r = {}
    r["_frozen"] = True
    r["_frozen_disclosure"] = C4_FREEZE_DISCLOSURE
    return r


def build_live_state(as_of: datetime, conn: Optional[Any] = None) -> dict[str, Any]:
    """Construct the v2-state-shaped dict from LIVE price_history.

    Point-in-time: only trade_date <= as_of is used (safe for replay + parity).
    Produces the same fields the components consume — signals[].price,
    signals[].reasoning 'mom_1m=...%', sector.rotation[].change_pct — recomputed
    from fresh closes, plus the frozen macro regime. Component math is untouched.

    FAILS LOUD: if price_history has no rows as of `as_of`, raises rather than
    silently serving stale data (the whole point of this migration).
    """
    as_of_date = as_of.date() if hasattr(as_of, "date") else as_of
    own = conn is None
    if own:
        conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ticker, trade_date, close FROM price_history "
                "WHERE trade_date <= %s AND close IS NOT NULL "
                "ORDER BY ticker, trade_date",
                (as_of_date,),
            )
            rows = cur.fetchall()
    finally:
        if own:
            conn.close()

    if not rows:
        raise RuntimeError(
            f"price_history has no rows as of {as_of_date} — refusing to serve "
            f"stale signal inputs (fail-loud; check cron/price_history_daily.sh)")

    closes: dict[str, list[tuple[Any, float]]] = {}
    for tk, d, c in rows:
        closes.setdefault(tk, []).append((d, float(c)))

    signals: list[dict[str, Any]] = []
    rotation: list[dict[str, Any]] = []
    for tk, series in closes.items():
        latest_close = series[-1][1]
        mom_1m = None
        if len(series) > MOM_LOOKBACK_TD:
            ref_close = series[-1 - MOM_LOOKBACK_TD][1]
            if ref_close:
                mom_1m = latest_close / ref_close - 1.0
        reasoning = [f"mom_1m={mom_1m*100:+.2f}%"] if mom_1m is not None else []
        signals.append({"ticker": tk, "price": latest_close, "reasoning": reasoning})
        if tk in _SECTOR_ETFS and len(series) >= 2 and series[-2][1]:
            change_pct = (series[-1][1] / series[-2][1] - 1.0) * 100.0
            rotation.append({"etf": tk, "change_pct": round(change_pct, 4)})

    return {
        "signals": signals,
        "sector": {"rotation": rotation},
        "regime": _frozen_macro_regime(),
        "_source": "live:price_history",
        "_as_of": str(as_of_date),
        "_freshness_max_date": str(max(d for s in closes.values() for d, _ in s)),
    }


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
