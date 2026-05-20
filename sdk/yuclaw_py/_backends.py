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
    def backtest(self) -> dict[str, pd.DataFrame]: ...
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

    def backtest(self) -> dict[str, pd.DataFrame]:
        with self._conn() as conn:
            df = pd.read_sql("SELECT * FROM track_record ORDER BY signal_date", conn)
        backfill = df[df["is_backfill"] == True].reset_index(drop=True)
        forward = df[df["is_backfill"] == False].reset_index(drop=True)
        return {"backtest": backfill, "forward": forward}

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
    """REST API mode — ships in Day 11. Until then every method raises
    NotImplementedError with a clear pointer."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _stub(self, name: str):
        raise NotImplementedError(
            f"yuclaw_py.Client.{name}() over REST API ships in v3.0 Day 11. "
            f"For now use source='postgres' if you have the local pipeline, "
            f"or watch https://github.com/YuClawLab/yuclaw-brain for the "
            f"hosted endpoint going live."
        )

    def signal(self, ticker):                return self._stub("signal")
    def evidence(self, ticker, limit=5):     return self._stub("why")
    def replay(self, ticker, date):          return self._stub("replay")
    def backtest(self):                      return self._stub("backtest")
    def events(self, ticker, since=None):    return self._stub("events")
    def universe(self):                      return self._stub("universe")


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
