#!/usr/bin/env python3
"""
U350 cross-universe isolation gate (Phase 0; gate 4 "u350 isolation proven by attempted writes"). Nothing in the U350
program may run unless this is green. 8.0.1 repair: verification is separated from provisioning — this check INSPECTS
the existing configuration and fails closed on drift; it never creates a role, a schema or a table and never grants or
revokes (provisioning lives in v3.u350.ensure_namespace, for disposable test nodes or a deliberate administrative step).

  I0  the configuration is exactly the registered one (read-only inspection, before any DML): database name, role
      attributes, schema owner, table structures and the manifest's primary key, no user trigger on the probe table,
      effective privileges — no write privilege on ANY public table, SELECT on all, USAGE without CREATE on public,
      INSERT/DELETE/SELECT on u350.manifest; drift or an unexpected privilege is REPORTED, never repaired
  I1  a U350 connection CANNOT write any U79/public table (INSERT into events refused by PostgreSQL, not by convention)
  I2  a U350 connection CANNOT update U79 snapshots (UPDATE refused)
  I3  a U350 connection CAN write its own schema (positive control): ONE row with this run's unique identity
      (phase `_probe_<run id>`, manifest_hash `<run id>`; unique by primary key) inserted and exactly that row deleted
      in the same transaction, affected row counts checked, every pre-existing row — other probe rows included —
      untouched; any deviation rolls back
  I4  no U350 shadow ticker appears in U79 signal_snapshots or track_record (canonical readers structurally cannot see
      shadow rows, and no shadow name has leaked into the canonical record)
  I5  the scoring universe is exactly 79 and evidence-tier gating is unchanged (positive gating intact)

I1 and I2 attempt writes as the U350 role and must be refused with InsufficientPrivilege; an unexpected success (or any
other error class, e.g. a read-only session) FAILS the gate and is rolled back. Committed effect of a green run: the
I3 row inserted and deleted (net zero rows); a rolled-back attempt still consumes a transaction id, writes WAL and
increments pg_stat n_tup_ins for the attempted table, and I3 leaves one dead tuple for vacuum — nothing else (the
probe tables carry no user trigger, sequence or identity column; verified by I0 for the probe table).

Runs in the daily chain as a HARD gate. Exit 0 green / 1 violation, drift or unreachable database (no traceback).
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.u350 import DSN, ROLE, SCHEMA, ProbeFailure, inspect_isolation, positive_control, u350_connection

TAG = "[u350-isolation]"


def _attempt(cn, label, sql, problems):
    """One refused-write attempt under the active U350 role. Only InsufficientPrivilege is the expected outcome."""
    try:
        with cn.cursor() as cur:
            cur.execute(sql)
        problems.append(f"{label}: the U350 role could execute a write on a public table — isolation broken (rolled back)")
        cn.rollback()
    except psycopg2.errors.InsufficientPrivilege:
        cn.rollback()
    except Exception as exc:                          # noqa: BLE001 — a different error class is not a proof of refusal
        cn.rollback()
        problems.append(f"{label}: unexpected error class {type(exc).__name__} instead of InsufficientPrivilege — not a refusal proof: {str(exc).strip()[:160]}")


def main() -> int:
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}-pid{os.getpid()}"
    problems = []

    # I0 — inspect, never provision
    try:
        cn0 = psycopg2.connect(DSN)
    except psycopg2.OperationalError as exc:
        print(f"{TAG} FAILED: research database unreachable ({str(exc).strip().splitlines()[0][:160]}); nothing was attempted")
        return 1
    cn0.set_session(readonly=True)
    insp = inspect_isolation(cn0)
    cn0.close()
    if insp["findings"]:
        print(f"{TAG} FAILED at I0 — configuration differs from the registered one; nothing was created, granted, revoked or written:")
        for f in insp["findings"]:
            print(f"  · {f}")
        return 1

    # I1 / I2 — refused writes as the U350 role (session-scoped SET ROLE)
    cn = u350_connection()
    with cn.cursor() as cur:
        cur.execute("SELECT current_user")
        who = cur.fetchone()[0]
    if who != ROLE:
        cn.close()
        print(f"{TAG} FAILED: the probe connection runs as {who}, not {ROLE}; nothing was attempted")
        return 1
    _attempt(cn, "I1", "INSERT INTO public.events (event_id, ticker, event_type, magnitude, direction, event_time, available_as_of, "
                       f"source_type, content_hash, event_status) VALUES ('U350_ISOLATION_PROBE_{run_id}', 'XX', 'OTHER_MATERIAL', 0, 0, "
                       "now(), now(), 'probe', 'probe', 'rejected')", problems)
    _attempt(cn, "I2", "UPDATE public.signal_snapshots SET total_score = total_score WHERE false", problems)

    # I3 — positive control with this run's own identity
    pc = None
    try:
        pc = positive_control(cn, run_id)
    except ProbeFailure as exc:
        problems.append(f"I3: {exc}")
    cn.close()

    # I4 — no shadow ticker in the canonical record (read-only)
    with psycopg2.connect(DSN) as c2:
        c2.set_session(readonly=True)
        with c2.cursor() as cur:
            cur.execute(f"SELECT members FROM {SCHEMA}.manifest WHERE phase='A' ORDER BY locked_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                from v3.universe_tiers import scoring_universe
                shadow_only = [m["ticker"] for m in row[0] if m["ticker"] not in scoring_universe()]
                if shadow_only:
                    cur.execute("SELECT count(*) FROM public.signal_snapshots WHERE ticker = ANY(%s)", (shadow_only,))
                    if cur.fetchone()[0]:
                        problems.append("I4: shadow-only ticker present in public.signal_snapshots")
                    cur.execute("SELECT count(*) FROM public.track_record WHERE ticker = ANY(%s)", (shadow_only,))
                    if cur.fetchone()[0]:
                        problems.append("I4: shadow-only ticker present in public.track_record")

    # I5 — positive gating intact
    from v3.universe_tiers import scoring_universe
    if len(scoring_universe()) != 79:
        problems.append(f"I5: scoring universe is {len(scoring_universe())}, not 79")

    if problems:
        print(f"{TAG} U350 ISOLATION GATE FAILED (run {run_id}):")
        for p in problems:
            print(f"  · {p}")
        return 1
    f = insp["facts"]
    print(f"{TAG} OK — configuration inspected, not changed ({f['public_tables']} public tables, none writable by {ROLE}; "
          f"{SCHEMA}.manifest key {'+'.join(f['manifest_primary_key'])}); both write refusals proven by attempt; own-schema write works "
          f"(run {run_id}: row {pc['phase']}/{pc['manifest_hash']} inserted {pc['inserted']} and deleted {pc['deleted']} in one transaction, "
          f"{pc['other_probe_rows_before']} other probe row(s) untouched); no shadow ticker in the canonical record; scoring universe = 79")
    return 0


if __name__ == "__main__":
    sys.exit(main())
