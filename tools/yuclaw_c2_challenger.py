#!/usr/bin/env python3
"""
C2 shadow challenger (v5.2 Part 3a) — REGISTRY-FIRST, STRUCTURALLY ISOLATED.

The live composite's C2 (volume confirmation) has been self-masked at
confidence 0.0 since v2.3.0 — it has never contributed; effective weights
are the renormalized eight. This module implements the docstring-intended
scorer as a SHADOW CHALLENGER:

    z = (volume / 20-trading-day average volume) - 1
    score = tanh(z * sign(close-to-close price move))

Isolation contract (self-tested): writes ONLY to the parallel
challenger_snapshots table; imports nothing from, and is imported by
nothing in, the live composite path (v3/signal/*). The live composite
structurally cannot see these rows. Promotion is a future, separately
registered question — protocol "C2 challenger evaluation v1" fixes the
evaluation BEFORE accrual starts: primary endpoint = shadow-C2 standalone
IC at k=5 on the forward window accruing from 2026-07-31; no promotion
decision may cite any other cell.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

DSN = "dbname=yuclaw_events"
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "C2 challenger evaluation v1"
PROTOCOL_PARAMS = {"k_primary": 5, "accrual_start": "2026-07-31",
                   "scorer": "tanh((vol/avg20 - 1) * sign(ret1d))"}

DDL = """CREATE TABLE IF NOT EXISTS challenger_snapshots (
    ticker text NOT NULL, snapshot_date date NOT NULL,
    challenger text NOT NULL DEFAULT 'c2_volume',
    score real NOT NULL, z real, ret1d_sign int,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, snapshot_date, challenger))"""


def register_first():
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Shadow C2 volume-confirmation scorer writing to "
                          "parallel challenger_snapshots only (structural "
                          "isolation self-tested); evaluation fixed before "
                          "accrual: standalone IC at k=5, forward from "
                          "2026-07-31."),
            primary_endpoint=("shadow-C2 standalone IC at k=5 on the "
                              "forward window accruing from 2026-07-31"),
            secondary_endpoints=["IC at k=1/k=20 (decay context)",
                                 "quantile monotonicity"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE accrual")
    return pid


def isolation_selftest():
    """The live composite path must have zero references to this module or
    its table — structural, greppable, falsifiable."""
    sig_dir = _REPO / "v3" / "signal"
    hits = []
    for py in sig_dir.rglob("*.py"):
        text = py.read_text(errors="replace")
        if "challenger" in text.lower():
            hits.append(str(py))
    assert not hits, f"ISOLATION BROKEN: composite path references challenger: {hits}"
    text = Path(__file__).read_text()
    needles = ("from " + "v3.signal", "import " + "v3.signal")
    assert not any(n in text for n in needles), \
        "ISOLATION BROKEN: challenger imports the composite path"
    print("[OK] isolation: composite path has zero challenger references; "
          "challenger imports nothing from v3/signal")


def write_snapshots(as_of: date | None = None) -> int:
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(
                """WITH ranked AS (
                     SELECT ticker, trade_date, close, volume,
                            AVG(volume) OVER (PARTITION BY ticker
                                ORDER BY trade_date
                                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) avg20,
                            LAG(close) OVER (PARTITION BY ticker
                                ORDER BY trade_date) prev_close,
                            ROW_NUMBER() OVER (PARTITION BY ticker
                                ORDER BY trade_date DESC) rn
                     FROM price_history WHERE volume IS NOT NULL)
                   SELECT ticker, trade_date, close, volume, avg20, prev_close
                   FROM ranked WHERE rn = 1 AND avg20 IS NOT NULL
                     AND prev_close IS NOT NULL AND prev_close <> 0""")
            rows = cur.fetchall()
            n = 0
            for tk, d, close, vol, avg20, prev in rows:
                if as_of and d != as_of:
                    continue
                z = float(vol) / float(avg20) - 1.0
                sign = 1 if float(close) >= float(prev) else -1
                score = math.tanh(z * sign)
                cur.execute(
                    """INSERT INTO challenger_snapshots
                       (ticker, snapshot_date, score, z, ret1d_sign)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (ticker, snapshot_date, challenger)
                       DO NOTHING""", (tk, d, score, z, sign))
                n += cur.rowcount
        cn.commit()
    return n


def main() -> int:
    isolation_selftest()
    register_first()
    n = write_snapshots()
    with psycopg2.connect(DSN) as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT count(*), max(snapshot_date) FROM challenger_snapshots")
            total, latest = cur.fetchone()
    print(f"[c2-challenger] wrote {n} new shadow snapshots "
          f"(table total {total}, latest {latest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
