#!/usr/bin/env python3
"""Day-3A: retry + dead-letter path validation.

Day 2 had 0 failures, so these paths were never exercised. This proves:
  1. mark_failed under max_attempts -> back to 'pending', attempts incremented,
     claim released.
  2. mark_failed AT max_attempts -> 'dead_letter' (no infinite retry).
  3. list_dead_letter() returns the job with last_error populated.
  4. transient failure then success -> ends 'succeeded'.
  5. END-TO-END via the real Worker: a job that deterministically fails inside
     Worker.process_job (bogus accession -> no filing text) is routed through
     mark_failed by run_once, and dead-letters at max_attempts.

The retry/dead-letter LOGIC lives in core.mark_failed; tests 1-4 hit it
directly (authoritative + deterministic). Test 5 proves the worker is wired to
it. No Llama needed. All test jobs are namespaced by RUN and cleaned up.

Run: python3 yuclaw/v5/queue/tests/test_retry_deadletter.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg2

from yuclaw.v5.queue.core import DEFAULT_DSN, EvidenceJobQueue
from yuclaw.v5.queue.worker import JOB_TYPE, Worker

RUN = uuid.uuid4().hex[:8]
results = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def test_retry_then_deadletter(q: EvidenceJobQueue) -> None:
    print("\n[1+2+3] retry -> pending (xN), then dead_letter at max_attempts, last_error set")
    jt = f"faildl_{RUN}"
    job_id = q.enqueue(jt, {"k": "v"}, max_attempts=3, idempotency_key=f"{jt}:dl")

    # attempt 1
    q.claim_next("retry_w", job_types=[jt])
    q.mark_failed(job_id, "boom-1")
    r = q.get_job(job_id)
    check("attempt1 -> pending", r["state"] == "pending" and r["attempts"] == 1, f"state={r['state']} attempts={r['attempts']}")
    check("attempt1 claim released", r["claimed_by"] is None, f"claimed_by={r['claimed_by']}")

    # attempt 2
    q.claim_next("retry_w", job_types=[jt])
    q.mark_failed(job_id, "boom-2")
    r = q.get_job(job_id)
    check("attempt2 -> pending", r["state"] == "pending" and r["attempts"] == 2, f"state={r['state']} attempts={r['attempts']}")

    # attempt 3 -> reaches max_attempts -> dead_letter
    q.claim_next("retry_w", job_types=[jt])
    q.mark_failed(job_id, "boom-3-final")
    r = q.get_job(job_id)
    check("attempt3 -> dead_letter (no infinite retry)", r["state"] == "dead_letter" and r["attempts"] == 3, f"state={r['state']} attempts={r['attempts']}")
    check("last_error populated", r["last_error"] == "boom-3-final", f"last_error={r['last_error']!r}")
    check("failed_at set", r["failed_at"] is not None)

    dl_ids = {str(d["job_id"]): d for d in q.list_dead_letter()}
    check("list_dead_letter returns it", job_id in dl_ids)
    if job_id in dl_ids:
        check("list_dead_letter carries last_error", dl_ids[job_id]["last_error"] == "boom-3-final")


def test_transient_recovery(q: EvidenceJobQueue) -> None:
    print("\n[4] transient failure then success -> ends 'succeeded'")
    jt = f"transient_{RUN}"
    job_id = q.enqueue(jt, {"k": "v"}, max_attempts=3, idempotency_key=f"{jt}:t")
    q.claim_next("retry_w", job_types=[jt])
    q.mark_failed(job_id, "transient-blip")
    r = q.get_job(job_id)
    check("after 1 fail -> pending (retryable)", r["state"] == "pending" and r["attempts"] == 1)
    q.claim_next("retry_w", job_types=[jt])
    q.mark_succeeded(job_id, str(uuid.uuid4()))
    r = q.get_job(job_id)
    check("retry succeeds -> succeeded", r["state"] == "succeeded", f"state={r['state']}")


def test_worker_end_to_end_deadletter(q: EvidenceJobQueue) -> int:
    """Real Worker: deterministic failure (bogus accession) -> mark_failed -> dead_letter.
    Returns the job_id so the caller can clean it up (it's job_type='extract_filing')."""
    print("\n[5] END-TO-END via Worker.run_once: bogus accession -> dead_letter at max_attempts")
    w = Worker(worker_id="retry_worker_e2e")
    bogus = f"BOGUS-{RUN}-does-not-exist"
    job_id = w.queue.enqueue(
        JOB_TYPE, {"accession_number": bogus}, max_attempts=2,
        idempotency_key=f"e2e_dl_{RUN}",
    )
    # run_once claims + process_job raises (no filing text) + run_once -> mark_failed
    w.run_once(batch_size=1)
    r = w.queue.get_job(job_id)
    check("worker fail #1 -> pending", r["state"] == "pending" and r["attempts"] == 1, f"state={r['state']} attempts={r['attempts']}")
    w.run_once(batch_size=1)
    r = w.queue.get_job(job_id)
    check("worker fail #2 (==max) -> dead_letter", r["state"] == "dead_letter" and r["attempts"] == 2, f"state={r['state']} attempts={r['attempts']}")
    check("worker last_error is the real failure reason", "no filing text" in (r["last_error"] or ""), f"last_error={r['last_error']!r}")
    w.close() if hasattr(w, "close") else w.queue.close()
    return job_id


def cleanup(extra_job_ids: list) -> None:
    cn = psycopg2.connect(DEFAULT_DSN)
    try:
        with cn, cn.cursor() as cur:
            cur.execute("DELETE FROM yuclaw_v5.evidence_jobs WHERE job_type LIKE %s", (f"%_{RUN}",))
            n1 = cur.rowcount
            n2 = 0
            for jid in extra_job_ids:
                cur.execute("DELETE FROM yuclaw_v5.evidence_jobs WHERE job_id=%s::uuid", (jid,))
                n2 += cur.rowcount
        print(f"\ncleanup: deleted {n1} namespaced + {n2} worker-test job(s)")
    finally:
        cn.close()


def main() -> int:
    print(f"Retry + dead-letter validation (run {RUN})")
    q = EvidenceJobQueue()
    extra = []
    try:
        test_retry_then_deadletter(q)
        test_transient_recovery(q)
        extra.append(test_worker_end_to_end_deadletter(q))
    finally:
        cleanup(extra)
        q.close()
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\nRESULT: {len(results)-n_fail}/{len(results)} checks pass"
          + ("" if n_fail == 0 else f" — {n_fail} FAILED"))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
