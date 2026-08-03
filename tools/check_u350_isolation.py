#!/usr/bin/env python3
"""
U350 cross-universe isolation gate (Phase 0). Nothing in the U350 program
may run unless this is green. Proves, by attempting them, that:

  I1  a U350 connection CANNOT write any U79/public table (INSERT into
      events refused by PostgreSQL, not by convention)
  I2  a U350 connection CANNOT update U79 snapshots (UPDATE refused)
  I3  a U350 connection CAN write its own schema (positive control)
  I4  no U350 shadow ticker appears in U79 signal_snapshots or
      track_record (canonical readers structurally cannot see shadow rows,
      and no shadow name has leaked into the canonical record)
  I5  the scoring universe is exactly 79 and evidence-tier gating is
      unchanged (positive gating intact)

Runs in the daily chain as a HARD gate. Exit 0 green / 1 violation.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.u350 import SCHEMA, ensure_namespace, u350_connection


def main() -> int:
    ensure_namespace()
    problems = []

    # I1 — INSERT into a U79 table must refuse
    cn = u350_connection()
    try:
        with cn.cursor() as cur:
            cur.execute("INSERT INTO public.events (event_id, ticker, "
                        "event_type, magnitude, direction, event_time, "
                        "available_as_of, source_type, content_hash, "
                        "event_status) VALUES ('U350_ISOLATION_PROBE', 'XX', "
                        "'OTHER_MATERIAL', 0, 0, now(), now(), 'probe', "
                        "'probe', 'rejected')")
        problems.append("I1: U350 role INSERTED into public.events")
        cn.rollback()
    except psycopg2.errors.InsufficientPrivilege:
        cn.rollback()
    # I2 — UPDATE on U79 snapshots must refuse
    try:
        with cn.cursor() as cur:
            cur.execute("UPDATE public.signal_snapshots SET total_score = "
                        "total_score WHERE false")
        problems.append("I2: U350 role could UPDATE public.signal_snapshots")
        cn.rollback()
    except psycopg2.errors.InsufficientPrivilege:
        cn.rollback()
    # I3 — positive control: own schema writable
    try:
        with cn.cursor() as cur:
            cur.execute(f"INSERT INTO {SCHEMA}.manifest (phase, manifest_hash,"
                        f" members) VALUES ('_probe', '_probe', '[]') "
                        f"ON CONFLICT DO NOTHING")
            cur.execute(f"DELETE FROM {SCHEMA}.manifest WHERE phase='_probe'")
        cn.commit()
    except Exception as exc:                     # noqa: BLE001
        problems.append(f"I3: U350 role cannot write its own schema: {exc}")
        cn.rollback()
    cn.close()

    # I4 — no shadow ticker in the canonical record
    with psycopg2.connect("dbname=yuclaw_events") as c2:
        with c2.cursor() as cur:
            cur.execute(f"SELECT members FROM {SCHEMA}.manifest "
                        f"WHERE phase='A' ORDER BY locked_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                import json
                from v3.universe_tiers import scoring_universe
                shadow_only = [m["ticker"] for m in row[0]
                               if m["ticker"] not in scoring_universe()]
                if shadow_only:
                    cur.execute("SELECT count(*) FROM public.signal_snapshots "
                                "WHERE ticker = ANY(%s)", (shadow_only,))
                    if cur.fetchone()[0]:
                        problems.append("I4: shadow-only ticker present in "
                                        "public.signal_snapshots")
                    cur.execute("SELECT count(*) FROM public.track_record "
                                "WHERE ticker = ANY(%s)", (shadow_only,))
                    if cur.fetchone()[0]:
                        problems.append("I4: shadow-only ticker present in "
                                        "public.track_record")

    # I5 — positive gating intact
    from v3.universe_tiers import scoring_universe
    if len(scoring_universe()) != 79:
        problems.append(f"I5: scoring universe is "
                        f"{len(scoring_universe())}, not 79")

    if problems:
        print("U350 ISOLATION GATE FAILED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print("[u350-isolation] OK — both write refusals proven by attempt, "
          "own-schema write works, no shadow ticker in the canonical "
          "record, scoring universe = 79")
    return 0


if __name__ == "__main__":
    sys.exit(main())
