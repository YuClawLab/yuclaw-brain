#!/usr/bin/env python3
"""Negative verification: the Canada Resources evidence tier is NOT scored.

Ship gate for Phase 2 (and a standing invariant afterwards). Verifies that no
evidence-tier name appears in:
  1. signal_snapshots (composite scoring output — feeds everything downstream)
  2. the scoring universe gate itself (positive-gating sanity)
  3. the Lab replay export bundle (decile/ranking source of record)
  4. the forward-track cohort membership (via signal_snapshots, checked directly)

Exits 1 on any violation. Run:  python3 tools/verify_evidence_tier_boundary.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from v3.universe_tiers import evidence_tier_tickers, lab_universe, scoring_universe

DSN = "dbname=yuclaw_events"


def main() -> int:
    ev = evidence_tier_tickers()
    sc = scoring_universe()
    lab = lab_universe()
    fails = []

    # 2. gate sanity first — the invariant everything else rests on
    if ev & sc:
        fails.append(f"scoring_universe overlaps evidence tier: {sorted(ev & sc)}")
    if ev & lab:
        fails.append(f"lab_universe overlaps evidence tier: {sorted(ev & lab)}")

    # 1./4. signal_snapshots must contain zero evidence-tier rows
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT DISTINCT ticker FROM signal_snapshots WHERE ticker = ANY(%s)",
                        (sorted(ev),))
            rows = [r[0] for r in cur.fetchall()]
            if rows:
                fails.append(f"signal_snapshots contains evidence-tier tickers: {rows}")
            cur.execute("SELECT count(DISTINCT ticker) FROM signal_snapshots")
            n_snap = cur.fetchone()[0]

    # 3. Lab replay bundle (if present) must only carry scoring-universe tickers
    bundle = _REPO / "docs" / "replay" / "lab_replay_bundle.json"
    if bundle.exists():
        try:
            data = json.loads(bundle.read_text())
            found = set()

            def walk(x):
                if isinstance(x, dict):
                    t = x.get("ticker")
                    if isinstance(t, str):
                        found.add(t)
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(data)
            leak = found & ev
            if leak:
                fails.append(f"lab_replay_bundle.json contains evidence-tier tickers: {sorted(leak)}")
        except Exception as e:
            fails.append(f"could not parse lab replay bundle: {e}")

    print(f"evidence tier: {len(ev)} names | scoring universe: {len(sc)} | "
          f"lab universe: {len(lab)} | distinct tickers ever in signal_snapshots: {n_snap}")
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("OK: no evidence-tier name in signal_snapshots, scoring gate, lab gate, or replay bundle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
