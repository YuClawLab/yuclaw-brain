#!/usr/bin/env python3
"""Real-data smoke test for the v5 Evidence Job Queue (per the v3.0 May-19 rule).

Synthetic tests are not enough. This drives ONE real, production-shaped EDGAR
filing through the full queue lifecycle and times each phase.

Data source (READ-ONLY): public.events_raw in the yuclaw_events database.

  NOTE on schema: the v5 spec referenced ``public.events(filing_id, raw_text)``.
  In the live v4 database the full filing body actually lives in
  ``public.events_raw`` -- ``public.events`` only keeps a <=400 char
  ``raw_excerpt``. We therefore pull the ~4000 char body from
  ``public.events_raw`` (accession_number as the filing identifier, raw_text as
  the body). This script never writes to public.* -- only the SELECT below
  touches v4, and it is read-only.

The job itself is created in the isolated yuclaw_v5 schema and cleaned up at the
end, so the smoke test leaves no residue in either schema.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

# Make the repo root importable when run as a standalone script
# (../../../.. from this file == the worktree root containing the yuclaw pkg).
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg2
import psycopg2.extras

from yuclaw.v5.queue.core import EvidenceJobQueue

SLOW_PHASE_SECONDS = 5.0
JOB_TYPE = "extract_filing_v5_smoke"
WORKER = "smoke_test_worker"


def fetch_real_filing(dsn: str) -> dict:
    """READ-ONLY: pull one ~4000 char real filing from public.events_raw."""
    cn = psycopg2.connect(dsn)
    try:
        # Defensive: explicitly read-only transaction so this can never write v4.
        cn.set_session(readonly=True)
        with cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT raw_id, accession_number, source_type, raw_text
                FROM public.events_raw
                WHERE LENGTH(raw_text) BETWEEN 3500 AND 4500
                ORDER BY raw_id
                LIMIT 1
                """
            )
            row = cur.fetchone()
    finally:
        cn.close()
    if row is None:
        print("SMOKE TEST FAILED: no real filing with 3500-4500 char body found.")
        sys.exit(1)
    return dict(row)


def main() -> int:
    q = EvidenceJobQueue()
    dsn = q.dsn

    filing = fetch_real_filing(dsn)
    filing_id = filing["accession_number"] or f"raw_id:{filing['raw_id']}"
    body = filing["raw_text"]
    print(f"Real filing: accession={filing_id} "
          f"source={filing['source_type']} body_len={len(body)} chars")

    payload = {
        "filing_id": filing_id,
        "accession_number": filing["accession_number"],
        "source_type": filing["source_type"],
        "raw_text": body,
    }
    # Idempotency key unique to this smoke run.
    idem_key = f"smoke:{JOB_TYPE}:{filing_id}:{uuid.uuid4().hex[:8]}"

    timings: dict[str, float] = {}

    # --- enqueue ---
    t0 = time.perf_counter()
    job_id = q.enqueue(JOB_TYPE, payload, priority=100, idempotency_key=idem_key)
    timings["enqueue"] = time.perf_counter() - t0

    # --- claim ---
    t0 = time.perf_counter()
    claimed = q.claim_next(WORKER, job_types=[JOB_TYPE], batch_size=1)
    timings["claim"] = time.perf_counter() - t0

    # --- mark_succeeded ---
    result_token_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    succeeded_ok = q.mark_succeeded(job_id, result_token_id)
    timings["mark_succeeded"] = time.perf_counter() - t0

    # --- read back & assert ---
    t0 = time.perf_counter()
    row = q.get_job(job_id)
    timings["read_back"] = time.perf_counter() - t0

    failures = []
    if not claimed or str(claimed[0]["job_id"]) != job_id:
        failures.append("claim did not return the enqueued job")
    if claimed and claimed[0]["claimed_by"] != WORKER:
        failures.append(f"claimed_by != {WORKER}")
    if claimed and claimed[0]["available_as_of"] is None:
        failures.append("available_as_of not recorded at claim time")
    if not succeeded_ok:
        failures.append("mark_succeeded returned False")
    if row["state"] != "succeeded":
        failures.append(f"final state is {row['state']}, expected succeeded")
    for ts_col in ("claimed_at", "available_as_of", "succeeded_at", "created_at"):
        if row[ts_col] is None:
            failures.append(f"timestamp {ts_col} is NULL")
    if str(row["result_token_id"]) != result_token_id:
        failures.append("result_token_id mismatch")

    # --- cleanup (remove the smoke job from yuclaw_v5) ---
    cn = psycopg2.connect(dsn)
    try:
        with cn, cn.cursor() as cur:
            cur.execute(
                "DELETE FROM yuclaw_v5.evidence_jobs WHERE job_id = %s::uuid",
                (job_id,),
            )
    finally:
        cn.close()
    q.close()

    # --- report ---
    print("\nTiming per phase:")
    slow = []
    for phase, secs in timings.items():
        flag = ""
        if secs > SLOW_PHASE_SECONDS:
            flag = "  <-- SLOW (>5s, Layer 0 should be FAST)"
            slow.append(phase)
        print(f"  {phase:<16} {secs*1000:8.2f} ms{flag}")

    if failures:
        print("\nREAL SMOKE TEST FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"\nfiling_id used: {filing_id}")
    print(f"job_id: {job_id}")
    print(f"result_token_id: {result_token_id}")
    if slow:
        print(f"WARNING: slow phases (>{SLOW_PHASE_SECONDS}s): {', '.join(slow)}")
    print("\nREAL SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
