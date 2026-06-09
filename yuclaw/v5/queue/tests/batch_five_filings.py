#!/usr/bin/env python3
"""Day-2 small batch: 5 distinct real EDGAR filings end-to-end through the
worker + queue. Runs ONLY after the one-filing smoke test passes.

Validates the claim loop, SKIP LOCKED behaviour under sequential real jobs, and
the retry/dead-letter path if any filing fails. Bounded to 5 — a full backfill
is a separate, deliberately-watched session.

READ-ONLY on public.events_raw ; writes only to schema yuclaw_v5 (via the queue).
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

from yuclaw.v5.queue.worker import JOB_TYPE, Worker

WORKER_ID = "batch_worker_5"
N = 5


def pick_filings(dsn: str, n: int) -> list[tuple[str, int]]:
    """READ-ONLY: n distinct real ~4000-char filings."""
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT accession_number, LENGTH(raw_text) FROM public.events_raw "
                "WHERE LENGTH(raw_text) BETWEEN 3500 AND 4500 "
                "AND accession_number IS NOT NULL "
                "ORDER BY raw_id LIMIT %s",
                (n,),
            )
            rows = cur.fetchall()
    finally:
        cn.close()
    return [(r[0], r[1]) for r in rows]


def main() -> int:
    w = Worker(worker_id=WORKER_ID)
    q = w.queue
    filings = pick_filings(w.dsn, N)
    if len(filings) < N:
        print(f"BATCH ABORT: only found {len(filings)} real filings (<{N})")
        return 1

    run_tag = uuid.uuid4().hex[:8]
    print(f"Enqueuing {len(filings)} filings (run {run_tag}):")
    for acc, ln in filings:
        jid = q.enqueue(
            JOB_TYPE, {"accession_number": acc},
            idempotency_key=f"batch5:{run_tag}:{acc}",
        )
        print(f"  enqueued {acc} ({ln} chars) -> {jid}")

    # Run the worker through them one at a time (exercises the claim loop).
    print("\nProcessing:")
    t_start = time.perf_counter()
    succeeded = failed = 0
    per_filing = []
    while True:
        jobs, results = w.run_once(batch_size=1)
        if not jobs:
            break
        for r in results:
            if "error" in r:
                failed += 1
                print(f"  FAIL  {r.get('job_id')}  {r['error']}")
                per_filing.append((r.get("accession_number"), "FAIL", None))
            else:
                succeeded += 1
                print(f"  OK    {r['accession_number']}  "
                      f"llama={r['llama_secs']:.2f}s  eval={r['eval_count']}  "
                      f"-> {r['extraction'].get('event_type')!r}")
                per_filing.append((r["accession_number"], "OK", r["llama_secs"]))
    total = time.perf_counter() - t_start

    stats = q.queue_stats()
    dead = q.list_dead_letter()

    print("\n=== BATCH RESULT ===")
    print(f"  succeeded={succeeded}  failed={failed}  dead_letter_total={stats['dead_letter']}")
    print(f"  wall-clock (claim+extract+complete, 5 jobs): {total:.2f}s")
    llamas = [s for _, st, s in per_filing if st == "OK" and s is not None]
    if llamas:
        print(f"  per-filing Llama: min={min(llamas):.2f}s max={max(llamas):.2f}s "
              f"avg={sum(llamas)/len(llamas):.2f}s")
    print(f"  queue_stats: {stats}")
    if dead:
        print("  dead-letter entries:")
        for d in dead:
            print(f"    {d['job_id']} attempts={d['attempts']} last_error={d['last_error']!r}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
