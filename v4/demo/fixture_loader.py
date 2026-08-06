"""
v4/demo/fixture_loader.py — zero-backend fallback for the canonical demo signal.

When Postgres is unreachable, the demo and the demo-targeted commands
(`why`, `memo`, `share`, `verify`, `cascade`) for the canonical **AMD @ 2026-05-20**
signal are served from bundled JSON fixtures, so `pip install yuclaw && yuclaw demo`
runs end-to-end with NO local backend.

The fixtures are a frozen capture of the real signal. Crucially, `yuclaw verify`
recomputes the SAME `content_hash` committed to the public git-anchored ledger —
byte-identical — so the evidence-first proof holds offline exactly as it does live.

Design: a tiny object that quacks like a psycopg2 connection/cursor, answering
ONLY the handful of queries `build_response` / `build_cascade` / `verify` issue,
from the fixture rows. The live path is untouched — these fixtures are reached
only when a real `psycopg2.connect(...)` raises (no backend present).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_FX_DIR = Path(__file__).resolve().parent / "fixtures"

FIXTURE_TICKER = "AMD"
FIXTURE_DATE = "2026-05-20"

BACKEND_HINT = (
    "This signal needs a local YUCLAW backend (Postgres). Only the bundled demo "
    "signal — AMD @ 2026-05-20 — works offline.\n"
    "  • `yuclaw demo`                      the guided journey (no backend needed)\n"
    "  • `yuclaw why AMD --as-of 2026-05-20` the same signal, offline\n"
    "  • docs/v4/backend_setup.md           to connect live signals (all tickers/dates)\n"
    "  • https://yuclaw.ca/why/{TICKER}.json  the published classification + evidence\n"
    "                                       for any covered name — no backend needed"
)

# Fields stored as ISO strings in the JSON that must come back as datetime objects.
_DT_SNAP = ("signal_time", "available_as_of")
_DT_EVENT = ("available_as_of",)

_CACHE: dict[str, Any] = {}


def _parse_dt(s: Any) -> Any:
    return datetime.fromisoformat(s) if isinstance(s, str) else s


def _load() -> tuple[dict, list[dict], dict]:
    if not _CACHE:
        snap = json.loads((_FX_DIR / "snapshot.json").read_text())
        for k in _DT_SNAP:
            if snap.get(k):
                snap[k] = _parse_dt(snap[k])
        events = json.loads((_FX_DIR / "events.json").read_text())
        for e in events:
            for k in _DT_EVENT:
                if e.get(k):
                    e[k] = _parse_dt(e[k])
        ledger = json.loads((_FX_DIR / "ledger_entry.json").read_text())
        _CACHE["snap"], _CACHE["events"], _CACHE["ledger"] = snap, events, ledger
    return _CACHE["snap"], _CACHE["events"], _CACHE["ledger"]


def available() -> bool:
    """True iff the bundled fixtures are present (always true in a normal install)."""
    return (_FX_DIR / "snapshot.json").exists()


def matches_as_of(ticker: str, as_of: Optional[datetime]) -> bool:
    """True iff (ticker, as_of) is the canonical bundled signal (AMD on 2026-05-20)."""
    if not ticker or ticker.upper() != FIXTURE_TICKER or as_of is None:
        return False
    d = as_of.date().isoformat() if hasattr(as_of, "date") else str(as_of)
    return d == FIXTURE_DATE


def matches_date(ticker: str, date_str: str) -> bool:
    """Date-string variant (verify uses YYYY-MM-DD, not a datetime)."""
    return bool(ticker) and ticker.upper() == FIXTURE_TICKER and date_str == FIXTURE_DATE


# --------------------------------------------------------------------------- #
# minimal psycopg2-shaped shim
# --------------------------------------------------------------------------- #
class _FixtureCursor:
    """Answers the specific SELECTs build_response / build_cascade issue."""

    def __init__(self, snap: dict, events: list[dict]):
        self._snap = snap
        self._events = events
        self._rows: list[dict] = []

    def execute(self, sql: str, params: tuple = ()) -> None:
        s = " ".join(sql.split())
        p = tuple(params or ())
        if "signal_snapshots" in s:
            # both build_response and verify select the one canonical snapshot row
            self._rows = [dict(self._snap)]
        elif "FROM events" in s:
            if "parent_event_id IS NOT NULL" in s:                      # cascade leaves
                ticker, as_of = p[0], p[-1]
                self._rows = [dict(e) for e in self._events
                              if e.get("ticker") == ticker and e.get("parent_event_id")
                              and (e.get("cascade_depth") or 0) >= 1
                              and e.get("available_as_of") and e["available_as_of"] <= as_of]
            elif "event_id = ANY" in s:                                 # by id list
                ids = set(p[0] or [])
                self._rows = [dict(e) for e in self._events if e["event_id"] in ids]
            elif "event_id = %s" in s:                                  # single event (cascade walk)
                eid = p[0]
                as_of = p[1] if len(p) > 1 else None
                self._rows = [dict(e) for e in self._events
                              if e["event_id"] == eid
                              and (as_of is None or (e.get("available_as_of") and e["available_as_of"] <= as_of))]
            elif "event_type <> ALL" in s:                              # top-N non-insider
                ticker, insiders, n = p[0], set(p[1] or []), p[2]
                rows = [dict(e) for e in self._events
                        if e.get("ticker") == ticker and e.get("event_type") not in insiders]
                rows.sort(key=lambda e: (e.get("magnitude") or 0.0) * (e.get("llm_confidence") or 0.0),
                          reverse=True)
                self._rows = rows[:n]
            else:
                self._rows = []
        elif "SELECT 1" in s:
            self._rows = [{"?column?": 1}]
        else:
            self._rows = []

    def fetchone(self) -> Optional[dict]:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)

    def __enter__(self) -> "_FixtureCursor":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def close(self) -> None:
        pass


class FixtureConnection:
    """A read-only stand-in for a psycopg2 connection over the bundled fixtures."""

    is_fixture = True

    def __init__(self):
        snap, events, ledger = _load()
        self._snap, self._events, self.ledger = snap, events, ledger
        self.ledger_anchor_url = ledger.get("ledger_anchor_url")

    def cursor(self, cursor_factory: Any = None) -> _FixtureCursor:
        return _FixtureCursor(self._snap, self._events)

    def close(self) -> None:
        pass

    def __enter__(self) -> "FixtureConnection":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def fixture_conn_or_none(ticker: str, as_of: Optional[datetime]) -> Optional[FixtureConnection]:
    """Return a FixtureConnection iff (ticker, as_of) is the canonical signal and
    the fixtures are present; else None (caller should surface BACKEND_HINT)."""
    if available() and matches_as_of(ticker, as_of):
        return FixtureConnection()
    return None


# --- verify-side helpers (verify reads a snapshot row + the ledger file) --- #
def fixture_snapshot_row() -> dict:
    snap, _, _ = _load()
    return dict(snap)


def fixture_ledger_block_and_entry(date_str: str) -> tuple[Optional[dict], Optional[dict]]:
    _, _, ledger = _load()
    if ledger.get("date") != date_str:
        return None, None
    entry = ledger.get("entry")
    block = {"date": date_str, "entries": [entry] if entry else []}
    return block, entry


def fixture_commit_meta() -> Optional[dict]:
    _, _, ledger = _load()
    return ledger.get("commit")
