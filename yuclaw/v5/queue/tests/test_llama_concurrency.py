#!/usr/bin/env python3
"""Day-3A Phase 4 (optional): real-Llama concurrency sanity.

ONLY runs if Ollama is already up (caller checks; this also guards). Enqueues 3
real filings, runs 2 concurrent workers using yuclaw-llm-70b:latest, and answers
the backfill-planning question: do concurrent Llama calls run in PARALLEL or do
they SERIALIZE at the Ollama layer (OLLAMA_NUM_PARALLEL was 1 in Day-2 logs)?

It records each /api/generate call's wall-clock [start,end] interval and checks
whether intervals overlap. Also asserts no double-claim of the same filing.

READ-ONLY on public.events_raw. Cleans up its 3 jobs (by id) afterward.
Does NOT change Ollama config or lifecycle (a warm-up generate is normal usage).
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
import requests

from yuclaw.v5.queue.core import DEFAULT_DSN, EvidenceJobQueue
from yuclaw.v5.queue.worker import JOB_TYPE, MODEL, OLLAMA_URL, Worker

RUN = uuid.uuid4().hex[:8]
N = 3
N_WORKERS = 2
_calls = []          # (worker_id, accession, t_start, t_end, secs)
_lock = threading.Lock()
_t0 = None           # shared monotonic origin


def pick_filings(dsn, n):
    cn = psycopg2.connect(dsn)
    try:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT accession_number FROM public.events_raw "
                "WHERE LENGTH(raw_text) BETWEEN 3500 AND 4500 AND accession_number IS NOT NULL "
                "ORDER BY raw_id LIMIT %s", (n,))
            return [r[0] for r in cur.fetchall()]
    finally:
        cn.close()


def instrumented_worker(worker_id, claimed_out):
    """A Worker whose Llama call records its absolute [start,end] interval."""
    w = Worker(worker_id=worker_id)
    orig = w._extract_with_llama

    def timed(text):
        s = time.perf_counter() - _t0
        try:
            parsed, secs, ev = orig(text)
            return parsed, secs, ev
        finally:
            e = time.perf_counter() - _t0
            with _lock:
                _calls.append((worker_id, e - s, s, e))

    w._extract_with_llama = timed

    empty = 0
    while empty < 3:
        jobs = w.queue.claim_next(worker_id, job_types=[JOB_TYPE], batch_size=1)
        if not jobs:
            empty += 1
            time.sleep(0.05)
            continue
        empty = 0
        for job in jobs:
            claimed_out.append(str(job["job_id"]))
            try:
                w.process_job(job)
            except Exception as ex:  # noqa: BLE001
                w.queue.mark_failed(str(job["job_id"]), f"{type(ex).__name__}: {ex}")
    w.queue.close()


def main() -> int:
    global _t0
    # guard: only run if Ollama responds
    try:
        if requests.get(f"{OLLAMA_URL}/api/tags", timeout=8).status_code != 200:
            print("Ollama not up — SKIP Phase 4")
            return 0
    except Exception:
        print("Ollama not reachable — SKIP Phase 4")
        return 0

    print(f"Llama concurrency probe (run {RUN}) model={MODEL} workers={N_WORKERS} filings={N}")
    # warm-up so we measure steady-state concurrency, not one-time model load
    print("  warming up model (isolates serialize/parallel from load time)...")
    requests.post(f"{OLLAMA_URL}/api/generate",
                  json={"model": MODEL, "prompt": "ok", "stream": False,
                        "options": {"num_predict": 4}}, timeout=240)

    q = EvidenceJobQueue()
    accs = pick_filings(DEFAULT_DSN, N)
    job_ids = []
    for a in accs:
        jid = q.enqueue(JOB_TYPE, {"accession_number": a},
                        idempotency_key=f"llamacc_{RUN}:{a}")
        job_ids.append(jid)
    print(f"  enqueued {len(job_ids)} real filings: {accs}")

    _t0 = time.perf_counter()
    per_worker = {f"llw_{RUN}_{k}": [] for k in range(N_WORKERS)}
    threads = [threading.Thread(target=instrumented_worker, args=(wid, lst))
               for wid, lst in per_worker.items()]
    wall0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)
    wall = time.perf_counter() - wall0

    # double-claim check
    all_claimed = [j for lst in per_worker.values() for j in lst]
    dupes = len(all_claimed) - len(set(all_claimed))

    # overlap analysis
    calls = sorted(_calls, key=lambda c: c[2])  # by start
    max_overlap = 0.0
    for i in range(1, len(calls)):
        prev_end = max(c[3] for c in calls[:i])
        ov = prev_end - calls[i][2]
        max_overlap = max(max_overlap, ov)
    serialized = max_overlap < 0.5  # <0.5s overlap => effectively serial
    sum_llama = sum(c[1] for c in calls)

    print("\n  per-call intervals (worker, secs, start->end relative):")
    for wid, secs, s, e in calls:
        print(f"    {wid}  {secs:6.2f}s   [{s:6.2f} -> {e:6.2f}]")
    print(f"\n  double_claims={dupes} (must be 0)")
    print(f"  sum of Llama call times = {sum_llama:.2f}s ; wall-clock for all = {wall:.2f}s")
    print(f"  max inter-call overlap = {max_overlap:.2f}s")
    print(f"  => Llama calls {'SERIALIZED' if serialized else 'ran in PARALLEL'} "
          f"(wall {'≈ sum → serial' if serialized else '< sum → parallel'})")
    print("\n  BACKFILL PLANNING NOTE:")
    if serialized:
        print("    Concurrent workers do NOT increase Llama throughput — the model")
        print("    server serializes generate calls (OLLAMA_NUM_PARALLEL=1). More")
        print("    workers help only if extraction is later sharded across model")
        print("    servers/GPUs or NUM_PARALLEL is raised. Queue concurrency is")
        print("    proven (Phase 2) but throughput is gated by the single model.")
    else:
        print("    Concurrent Llama calls overlapped — the model server is serving")
        print("    requests in parallel; more workers can raise throughput.")

    # cleanup our 3 jobs by id (job_type is 'extract_filing'; protect real jobs)
    cn = psycopg2.connect(DEFAULT_DSN)
    try:
        with cn, cn.cursor() as cur:
            for jid in job_ids:
                cur.execute("DELETE FROM yuclaw_v5.evidence_jobs WHERE job_id=%s::uuid", (jid,))
        print(f"\n  cleanup: deleted {len(job_ids)} probe job(s)")
    finally:
        cn.close()
    q.close()

    return 1 if dupes else 0


if __name__ == "__main__":
    sys.exit(main())
