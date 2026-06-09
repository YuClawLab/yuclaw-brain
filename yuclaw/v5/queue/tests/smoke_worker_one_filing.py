#!/usr/bin/env python3
"""Day-2 MANDATORY real-data smoke test: ONE real filing end-to-end through the
worker + queue + local Llama 70B.

Per the May-18 rule: real ~4000-char EDGAR filings behave differently from
synthetic fixtures, so the worker MUST prove itself on one real filing before
any batch. HARD GATE: if the Llama extraction times out, errors, or returns
empty, this exits non-zero and the caller must NOT run the batch.

It drives the Worker's own methods step-by-step so every phase is timed:
enqueue -> claim -> mark_running -> fetch(public.events_raw, read-only) ->
Llama extraction -> mark_succeeded, asserting each state transition.

READ-ONLY on public.* ; writes only to schema yuclaw_v5 (via the queue).
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg2

from yuclaw.v5.queue.core import DEFAULT_DSN
from yuclaw.v5.queue.worker import JOB_TYPE, Worker

WORKER_ID = "smoke_worker_one"
PREFERRED_ACCESSION = "0000320193-26-000011"  # Apple 8-K used in Day-1 smoke


def pick_real_filing(dsn: str) -> tuple[str, int]:
    """READ-ONLY: a real ~4000-char filing. Prefer the Day-1 Apple 8-K."""
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT accession_number, LENGTH(raw_text) FROM public.events_raw "
                "WHERE accession_number = %s AND raw_text IS NOT NULL",
                (PREFERRED_ACCESSION,),
            )
            row = cur.fetchone()
            if row:
                return row[0], row[1]
            cur.execute(
                "SELECT accession_number, LENGTH(raw_text) FROM public.events_raw "
                "WHERE LENGTH(raw_text) BETWEEN 3500 AND 4500 "
                "ORDER BY raw_id LIMIT 1"
            )
            row = cur.fetchone()
    finally:
        cn.close()
    if not row:
        print("SMOKE FAILED: no real ~4000-char filing found in public.events_raw")
        sys.exit(1)
    return row[0], row[1]


def main() -> int:
    w = Worker(worker_id=WORKER_ID)
    q = w.queue
    acc, body_len = pick_real_filing(w.dsn)
    print(f"Real filing: accession={acc} body_len={body_len} chars")

    idem = f"smoke1:{acc}:{uuid.uuid4().hex[:8]}"
    t = {}

    # 1. enqueue
    t0 = time.perf_counter()
    job_id = q.enqueue(JOB_TYPE, {"accession_number": acc}, idempotency_key=idem)
    t["enqueue"] = time.perf_counter() - t0
    assert q.get_job(job_id)["state"] == "pending", "job not pending after enqueue"

    # 2. claim
    t0 = time.perf_counter()
    claimed = q.claim_next(WORKER_ID, job_types=[JOB_TYPE], batch_size=1)
    t["claim"] = time.perf_counter() - t0
    assert claimed and str(claimed[0]["job_id"]) == job_id, "claim did not return our job"
    assert claimed[0]["state"] == "claimed", "job not in 'claimed' after claim"

    # 3. mark_running
    t0 = time.perf_counter()
    assert q.mark_running(job_id, WORKER_ID) is True
    t["mark_running"] = time.perf_counter() - t0
    assert q.get_job(job_id)["state"] == "running", "job not in 'running'"

    # 4. fetch real body (read-only) + Llama extraction  <-- the HARD GATE
    text = w._fetch_filing_text(acc)
    assert text, f"no raw_text for accession={acc}"
    try:
        t0 = time.perf_counter()
        extraction, llama_secs, eval_count = w._extract_with_llama(text)
        t["llama_extraction"] = time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        q.mark_failed(job_id, f"{type(e).__name__}: {e}")
        print(f"\nSMOKE FAILED at Llama extraction: {type(e).__name__}: {e}")
        print("  -> do NOT run the batch. (This is the May-18 failure mode.)")
        return 1
    if not extraction:
        q.mark_failed(job_id, "empty extraction")
        print("\nSMOKE FAILED: Llama returned an empty extraction")
        return 1

    # 5. mark_succeeded
    token_id = str(uuid.uuid4())  # Day-2 placeholder for the Layer-2 token
    t0 = time.perf_counter()
    assert q.mark_succeeded(job_id, result_token_id=token_id) is True
    t["mark_succeeded"] = time.perf_counter() - t0

    # 6. verify final persisted state
    row = q.get_job(job_id)
    ok = (
        row["state"] == "succeeded"
        and str(row["result_token_id"]) == token_id
        and row["succeeded_at"] is not None
        and row["claimed_at"] is not None
        and row["available_as_of"] is not None
    )

    total = sum(t.values())
    print("\nState transitions: pending -> claimed -> running -> succeeded  "
          f"[final state={row['state']}]")
    print("\nLlama extraction output:")
    print(f"  {extraction}")
    print(f"  eval_count={eval_count} tokens")
    print("\nTiming per phase:")
    for phase in ("enqueue", "claim", "mark_running", "llama_extraction", "mark_succeeded"):
        secs = t[phase]
        flag = "  <-- dominant" if phase == "llama_extraction" else ""
        print(f"  {phase:<18} {secs*1000:9.2f} ms{flag}")
    print(f"  {'TOTAL':<18} {total*1000:9.2f} ms")

    if not ok:
        print(f"\nSMOKE FAILED: final state/fields wrong: {row['state']}")
        return 1

    print(f"\nfiling: {acc}  job_id: {job_id}  token: {token_id}")
    print("\nREAL WORKER SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
