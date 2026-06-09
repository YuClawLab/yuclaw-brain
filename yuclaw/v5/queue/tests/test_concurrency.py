#!/usr/bin/env python3
"""Day-3A: TRUE PARALLEL multi-worker SKIP LOCKED test.

Day 2 proved sequential extraction. This proves the Layer-0 core invariant
under genuine concurrency: with M workers all calling claim_next against the
same queue simultaneously, every job is claimed EXACTLY ONCE — no double-claim,
no lost job, no deadlock.

Synthetic 'noop' jobs (no Llama). Each worker gets its OWN EvidenceJobQueue
(own connection pool) to faithfully simulate independent worker processes/nodes.
psycopg2 releases the GIL during the DB round-trip, so threads achieve real
concurrent SKIP LOCKED races.

Run: python3 yuclaw/v5/queue/tests/test_concurrency.py
"""

from __future__ import annotations

import sys
import threading
import time
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg2

from yuclaw.v5.queue.core import DEFAULT_DSN, EvidenceJobQueue

RUN = uuid.uuid4().hex[:8]          # namespace so we only touch our own jobs
N_JOBS = 60
WORKER_COUNTS = [2, 4, 8]
JOIN_TIMEOUT = 60.0                 # hard bound — a hang is a failure


def _job_type(wc: int) -> str:
    return f"noop_{RUN}_{wc}"


def _drain_worker(worker_id: str, job_type: str, claimed_out: list,
                  barrier: threading.Barrier) -> None:
    """Own queue/pool; claim+succeed one-at-a-time until drained."""
    q = EvidenceJobQueue(dsn=DEFAULT_DSN, minconn=1, maxconn=3)
    try:
        barrier.wait()  # all workers start together → maximal contention
        empty = 0
        while empty < 3:
            jobs = q.claim_next(worker_id, job_types=[job_type], batch_size=1)
            if not jobs:
                empty += 1
                time.sleep(0.02)
                continue
            empty = 0
            for job in jobs:
                claimed_out.append(str(job["job_id"]))
                q.mark_succeeded(str(job["job_id"]))
    finally:
        q.close()


def run_round(n_jobs: int, n_workers: int) -> dict:
    jt = _job_type(n_workers)
    q = EvidenceJobQueue(dsn=DEFAULT_DSN)
    enqueued = set()
    for i in range(n_jobs):
        jid = q.enqueue(jt, {"i": i}, idempotency_key=f"{jt}:{i}")
        enqueued.add(jid)

    per_worker: dict[str, list] = {f"w{n_workers}_{k}": [] for k in range(n_workers)}
    barrier = threading.Barrier(n_workers)
    threads = []
    t0 = time.perf_counter()
    for wid, lst in per_worker.items():
        t = threading.Thread(target=_drain_worker, args=(wid, jt, lst, barrier))
        threads.append(t)
        t.start()
    for t in threads:
        t.join(timeout=JOIN_TIMEOUT)
    elapsed = time.perf_counter() - t0

    hung = [t for t in threads if t.is_alive()]
    all_claimed = [jid for lst in per_worker.values() for jid in lst]
    distinct = set(all_claimed)
    dupes = len(all_claimed) - len(distinct)
    # state breakdown for THIS job_type (the queue's queue_stats is global)
    cn = psycopg2.connect(DEFAULT_DSN)
    try:
        with cn.cursor() as cur:
            cur.execute(
                "SELECT state, count(*) FROM yuclaw_v5.evidence_jobs "
                "WHERE job_type=%s GROUP BY state", (jt,))
            by_state = dict(cur.fetchall())
    finally:
        cn.close()
    q.close()

    return {
        "n_jobs": n_jobs,
        "n_workers": n_workers,
        "elapsed": elapsed,
        "hung_workers": len(hung),
        "total_claimed": len(all_claimed),
        "distinct_claimed": len(distinct),
        "double_claims": dupes,
        "missing": n_jobs - len(distinct),
        "by_state": by_state,
        "distribution": {wid: len(lst) for wid, lst in per_worker.items()},
        "claimed_set": distinct,
        "enqueued_set": enqueued,
    }


def assert_round(r: dict) -> list:
    failures = []
    if r["hung_workers"]:
        failures.append(f"{r['hung_workers']} worker(s) HUNG (deadlock?)")
    if r["double_claims"] != 0:
        failures.append(f"DOUBLE-CLAIM: {r['double_claims']} job(s) claimed >once")
    if r["missing"] != 0:
        failures.append(f"{r['missing']} job(s) never claimed (lost)")
    if r["total_claimed"] != r["n_jobs"]:
        failures.append(f"total_claimed {r['total_claimed']} != N {r['n_jobs']}")
    if r["claimed_set"] != r["enqueued_set"]:
        failures.append("claimed set != enqueued set")
    if r["by_state"].get("succeeded", 0) != r["n_jobs"]:
        failures.append(f"succeeded {r['by_state'].get('succeeded',0)} != N {r['n_jobs']}")
    stuck = r["by_state"].get("pending", 0) + r["by_state"].get("claimed", 0) + r["by_state"].get("running", 0)
    if stuck:
        failures.append(f"{stuck} job(s) stuck in pending/claimed/running")
    return failures


def main() -> int:
    print(f"Parallel SKIP LOCKED test (run {RUN}): {N_JOBS} jobs per round\n")
    overall_ok = True
    for wc in WORKER_COUNTS:
        r = run_round(N_JOBS, wc)
        fails = assert_round(r)
        status = "PASS" if not fails else "FAIL"
        print(f"--- {wc} workers --- [{status}]")
        print(f"  jobs={r['n_jobs']} total_claimed={r['total_claimed']} "
              f"distinct={r['distinct_claimed']} double_claims={r['double_claims']} "
              f"missing={r['missing']} hung={r['hung_workers']}")
        print(f"  per-worker claim distribution: {r['distribution']}")
        print(f"  final states: {r['by_state']}  elapsed={r['elapsed']:.3f}s")
        if fails:
            overall_ok = False
            for f in fails:
                print(f"  !!! {f}")
        print()
    print("RESULT:", "ALL ROUNDS PASS — no double-claims under concurrency"
          if overall_ok else "FAILURES DETECTED")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
