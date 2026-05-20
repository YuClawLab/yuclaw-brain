"""
Client — the single public entry point.

The Client wraps the chosen backend and is responsible for:
  - validating user inputs (ticker shape, date strings)
  - stitching evidence into the `why` payload
  - stamping every signal-bearing return with the locked `compliance` dict
  - asserting that labels in returns are inside PUBLIC_LABELS
"""
from __future__ import annotations

from typing import Any, Optional

from yuclaw_py._backends import ApiBackend, Backend, PostgresBackend
from yuclaw_py._compliance import COMPLIANCE, PUBLIC_LABELS


def _validate_label(label: str) -> str:
    if label not in PUBLIC_LABELS:
        # Hard assertion — the SDK should never leak an internal-only label.
        raise AssertionError(
            f"backend returned a non-public label {label!r}. "
            f"This is a bug — please file at https://github.com/YuClawLab/yuclaw-brain/issues"
        )
    return label


def _with_compliance(payload: dict[str, Any]) -> dict[str, Any]:
    if "label" in payload:
        _validate_label(payload["label"])
    payload = dict(payload)
    payload["compliance"] = dict(COMPLIANCE)
    return payload


class Client:
    """Read-only client over a YUCLAW data backend.

    Parameters
    ----------
    source : "postgres" | "api"
        Backend kind. `postgres` reads the local yuclaw_events DB; `api`
        will call the hosted REST endpoint (Day 11+).
    dsn : str, optional
        psycopg2 DSN for postgres mode. Defaults to ``"dbname=yuclaw_events"``.
    base_url : str, optional
        Required for api mode. Ignored otherwise.

    Examples
    --------
    >>> import yuclaw_py
    >>> client = yuclaw_py.Client()
    >>> sig = client.signal("NVDA")
    >>> sig["label"], sig["score"]   # doctest: +SKIP
    ('HOLD', 0.312)
    """

    def __init__(
        self,
        source: str = "postgres",
        dsn: str = "dbname=yuclaw_events",
        base_url: Optional[str] = None,
    ) -> None:
        if source == "postgres":
            self._backend: Backend = PostgresBackend(dsn=dsn)
        elif source == "api":
            if not base_url:
                raise ValueError("source='api' requires base_url")
            self._backend = ApiBackend(base_url=base_url)
        else:
            raise ValueError(f"source must be 'postgres' or 'api', got {source!r}")
        self.source = source

    # ------------------------------------------------------------------
    def signal(self, ticker: str) -> dict[str, Any]:
        """Latest live composite signal for `ticker`.

        Returns a dict with: ticker, label, score, signal_time,
        components (9-key dict, c1..c9), is_backfill, compliance.
        """
        return _with_compliance(self._backend.signal(ticker))

    def why(self, ticker: str, n_evidence: int = 5) -> dict[str, Any]:
        """Signal + the top-N evidence events that justify it."""
        sig = self._backend.signal(ticker)
        evidence = self._backend.evidence(ticker, limit=n_evidence)
        return _with_compliance({**sig, "evidence": evidence})

    def replay(self, ticker: str, date: str) -> dict[str, Any]:
        """Point-in-time composite signal as it would have looked at `date`.

        Reads the most recent snapshot for `ticker` with signal_time <= date.
        Materialize one first with
            ``python3 -m v3.cli replay TICKER --date YYYY-MM-DD``
        if the SDK reports the date is unavailable.
        """
        return _with_compliance(self._backend.replay(ticker, date))

    def backtest(self) -> dict[str, Any]:
        """Two-panel backtest + forward-tracking report.

        Returns ``{"backtest": DataFrame, "forward": DataFrame, "compliance": ...}``.
        Each DataFrame is a snapshot of `track_record`. See ``docs/methodology/backfill.md``
        for in-sample reconstruction caveats.
        """
        panels = self._backend.backtest()
        return {**panels, "compliance": dict(COMPLIANCE)}

    def events(self, ticker: str, since: Optional[str] = None):
        """Evidence events for `ticker` as a pandas DataFrame.

        Parameters
        ----------
        since : optional ISO date string (YYYY-MM-DD); inclusive lower bound on
            ``available_as_of``.
        """
        return self._backend.events(ticker, since=since)

    def universe(self) -> list[str]:
        """Static list of tickers covered by the v3.0 release."""
        return list(self._backend.universe())
