"""
Backend implementations behind the public Client surface.

Two modes:
  - PostgresBackend: direct read of yuclaw_events. Needs the v3.0 pipeline
    running locally (the typical YUCLAW operator setup).
  - ApiBackend: REST API mode. Ships in Day 11 when the hosted endpoint
    goes live; for now it raises NotImplementedError with a useful pointer
    so a user adopting the SDK against API mode gets a clean message
    rather than a silent failure.

Backends return plain dicts / DataFrames. The Client layer wraps results
with compliance fields and validates labels.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date as _date, datetime, timezone
from typing import Any, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

# Components in display order (matches Day 4 signal_snapshots columns).
COMPONENT_COLS = {
    "c1": "c1_price_momentum",
    "c2": "c2_volume_confirm",
    "c3": "c3_sector_velocity",
    "c4": "c4_macro_regime",
    "c5": "c5_oil_rates_fx",
    "c6": "c6_event_impact",
    "c7": "c7_peer_correlation",
    "c8": "c8_cascade_effect",
    "c9": "c9_model_trust",
}


class Backend(ABC):
    @abstractmethod
    def signal(self, ticker: str) -> dict[str, Any]: ...
    @abstractmethod
    def evidence(self, ticker: str, limit: int = 5) -> list[dict[str, Any]]: ...
    @abstractmethod
    def replay(self, ticker: str, date: str) -> dict[str, Any]: ...
    @abstractmethod
    def validation(self) -> dict[str, pd.DataFrame]: ...
    @abstractmethod
    def events(self, ticker: str, since: Optional[str] = None) -> pd.DataFrame: ...
    @abstractmethod
    def universe(self) -> list[str]: ...


# ---------------------------------------------------------------------------
class PostgresBackend(Backend):
    def __init__(self, dsn: str = "dbname=yuclaw_events"):
        self.dsn = dsn

    def _conn(self):
        return psycopg2.connect(self.dsn)

    # ------------------------------------------------------------------
    def _snapshot_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        components = {cid: float(row[col]) if row[col] is not None else None
                      for cid, col in COMPONENT_COLS.items()}
        return {
            "ticker": row["ticker"],
            "label": row["signal_label"],
            "score": float(row["total_score"]),
            "signal_time": row["signal_time"].isoformat(),
            "is_backfill": bool(row["is_backfill"]),
            "components": components,
        }

    # ------------------------------------------------------------------
    def signal(self, ticker: str) -> dict[str, Any]:
        with self._conn() as conn, \
             conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM signal_snapshots
                   WHERE ticker = %s AND is_backfill = false
                   ORDER BY signal_time DESC LIMIT 1""",
                (ticker.upper(),),
            )
            row = cur.fetchone()
        if row is None:
            raise LookupError(
                f"no live snapshot for {ticker.upper()} — "
                f"run `python3 -m v3.signal.snapshot_writer` to materialize one"
            )
        return self._snapshot_row_to_dict(dict(row))

    def evidence(self, ticker: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._conn() as conn, \
             conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT event_id, event_type, direction, magnitude,
                          available_as_of, raw_excerpt, source_url,
                          llm_confidence, cascade_depth
                   FROM events
                   WHERE ticker = %s AND event_status = 'accepted'
                   ORDER BY magnitude * llm_confidence DESC
                   LIMIT %s""",
                (ticker.upper(), limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["available_as_of"] = r["available_as_of"].isoformat()
            r["magnitude"] = float(r["magnitude"])
            r["llm_confidence"] = float(r["llm_confidence"] or 0.0)
        return rows

    def replay(self, ticker: str, date: str) -> dict[str, Any]:
        """Return the snapshot for `ticker` whose signal_time is <= `date`
        (the most recent at-or-before that date). Raise if none."""
        try:
            d = datetime.strptime(date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError as e:
            raise ValueError(f"date must be YYYY-MM-DD: {date!r}") from e
        with self._conn() as conn, \
             conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM signal_snapshots
                   WHERE ticker = %s AND signal_time <= %s
                   ORDER BY signal_time DESC LIMIT 1""",
                (ticker.upper(), d),
            )
            row = cur.fetchone()
        if row is None:
            raise LookupError(
                f"no snapshot for {ticker.upper()} at or before {date} — "
                f"materialize one with `python3 -m v3.cli replay {ticker.upper()} --date {date}`"
            )
        out = self._snapshot_row_to_dict(dict(row))
        out["replay_as_of"] = date
        return out

    def validation(self) -> dict[str, pd.DataFrame]:
        with self._conn() as conn:
            df = pd.read_sql("SELECT * FROM track_record ORDER BY signal_date", conn)
        in_sample = df[df["is_backfill"] == True].reset_index(drop=True)
        forward = df[df["is_backfill"] == False].reset_index(drop=True)
        return {"in_sample": in_sample, "forward": forward}

    def events(self, ticker: str, since: Optional[str] = None) -> pd.DataFrame:
        sql = (
            "SELECT event_id, ticker, event_type, magnitude, direction, "
            "available_as_of, llm_confidence, source_type, source_url, "
            "raw_excerpt, cascade_depth "
            "FROM events WHERE ticker = %(t)s AND event_status = 'accepted' "
        )
        params: dict[str, Any] = {"t": ticker.upper()}
        if since:
            sql += "AND available_as_of >= %(s)s "
            params["s"] = since
        sql += "ORDER BY available_as_of DESC"
        with self._conn() as conn:
            return pd.read_sql(sql, conn, params=params)

    def universe(self) -> list[str]:
        # Encoded once so the SDK does not depend on the v3 tree layout —
        # this matches v3/universe.json (Day 7 state). When the universe
        # changes a new SDK version is published.
        return _UNIVERSE


# ---------------------------------------------------------------------------
class ApiBackend(Backend):
    """REST API mode — HTTP calls to a YUCLAW server.

    Mirrors the PostgresBackend contract: returns dicts / DataFrames in
    the exact same shape so the Client layer doesn't need to branch on
    `source`. JSON arrays for tabular endpoints are rehydrated to
    pandas DataFrames on this side.
    """

    DEFAULT_TIMEOUT = 30.0  # seconds — generous so backtest/events don't time out

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        import requests
        r = requests.get(
            f"{self.base_url}{path}",
            params=params or {},
            timeout=self.DEFAULT_TIMEOUT,
        )
        if r.status_code == 404:
            # Surface as LookupError so the Client layer can format it like
            # the postgres path does, instead of leaking HTTP semantics.
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise LookupError(detail)
        r.raise_for_status()
        return r.json()

    def signal(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/signal/{ticker.upper()}")

    def evidence(self, ticker: str, limit: int = 5) -> list[dict[str, Any]]:
        data = self._get(f"/why/{ticker.upper()}", params={"n_evidence": limit})
        return data.get("evidence") or []

    def replay(self, ticker: str, date: str) -> dict[str, Any]:
        return self._get(f"/replay/{ticker.upper()}", params={"date": date})

    def validation(self) -> dict[str, pd.DataFrame]:
        data = self._get("/validation")
        return {
            "in_sample": pd.DataFrame(data.get("in_sample") or []),
            "forward":   pd.DataFrame(data.get("forward")   or []),
        }

    def events(self, ticker: str, since: Optional[str] = None) -> pd.DataFrame:
        params: dict[str, Any] = {}
        if since:
            params["since"] = since
        data = self._get(f"/events/{ticker.upper()}", params=params)
        return pd.DataFrame(data.get("events") or [])

    def universe(self) -> list[str]:
        data = self._get("/universe")
        return list(data.get("universe") or [])


# ---------------------------------------------------------------------------
# Static copy of the v3.0 universe (post-Day-7).
_UNIVERSE: list[str] = sorted([
    # equities
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD", "INTC",
    "MRVL", "MU", "ARM", "RKLB", "LUNR", "HPE", "AMAT", "LRCX", "CRCL", "DELL",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "AXP", "V", "MA", "PYPL",
    "UNH", "JNJ", "PFE", "MRK", "ABBV", "LLY", "TMO", "DHR", "ABT", "BMY",
    "XOM", "CVX", "COP", "SLB", "PSX",
    "PG", "KO", "PEP", "WMT", "COST",
    # sector ETFs
    "XLK", "XLF", "XLE", "XLV", "XLU", "XLI", "XLY", "XLP", "XLB", "XLRE",
    "XLC", "SMH", "KRE", "IBB", "XBI",
    # broad ETFs
    "SPY", "QQQ", "IWM", "DIA", "MDY",
    # macro
    "TLT", "IEF", "GLD", "SLV", "UUP", "FXI", "EEM", "VIXY", "VXX", "TAIL",
])
