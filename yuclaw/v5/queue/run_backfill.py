#!/usr/bin/env python3
"""YUCLAW v5 Layer 0 Day 3B — backfill runner.

Drains `extract_filing` jobs with N concurrent workers (default 2) using the
proven Day-2 Worker path (real Llama extraction). Supports:
  * --canary K : stop after K jobs reach a terminal state, for the early gate.
  * checkpoint logging every --checkpoint-every jobs to
    ~/.yuclaw/v5/backfill_progress.log (tail -f to watch).
  * rolling dead-letter guard: abort if cumulative attempt-failure rate exceeds
    --max-fail-rate after a minimum sample (systemic-failure circuit breaker).

Reuses Worker.run_once (claim -> process_job -> mark_failed on exception); the
queue handles retry/dead-letter. public.* is read-only; writes go to yuclaw_v5.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from yuclaw.v5.queue.core import EvidenceJobQueue
from yuclaw.v5.queue.worker import JOB_TYPE, Worker

PROGRESS_LOG = Path("~/.yuclaw/v5/backfill_progress.log").expanduser()


class Shared:
    def __init__(self, total: int, checkpoint_every: int, canary_n, max_fail_rate: float):
        self.lock = threading.Lock()
        self.total = total
        self.checkpoint_every = checkpoint_every
        self.canary_n = canary_n
        self.max_fail_rate = max_fail_rate
        self.stop = threading.Event()
        self.attempts = 0          # extraction attempts (incl. retries)
        self.succeeded = 0         # distinct jobs that succeeded
        self.fail_attempts = 0     # failed attempts (exceptions)
        self.timings = []          # llama secs of successful attempts
        self.terminal = 0          # succeeded + (counted at end for dead_letter)
        self.t0 = time.perf_counter()
        self.aborted = False
        self.abort_reason = ""
        self.samples = []          # (accession, status, secs) for canary/report

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
        with open(PROGRESS_LOG, "a") as f:
            f.write(line + "\n")

    def record(self, results: list) -> None:
        """Called under no lock by worker; acquires lock internally."""
        with self.lock:
            for r in results:
                self.attempts += 1
                if "error" in r:
                    self.fail_attempts += 1
                    self.samples.append((r.get("accession_number"), "FAIL", None))
                else:
                    self.succeeded += 1
                    self.timings.append(r["llama_secs"])
                    self.samples.append((r["accession_number"], "OK", r["llama_secs"]))
                done = self.succeeded
                # checkpoint
                if done and done % self.checkpoint_every == 0:
                    self._checkpoint()
                # rolling guard (after a minimum sample)
                if self.attempts >= 20:
                    rate = self.fail_attempts / self.attempts
                    if rate > self.max_fail_rate:
                        self.aborted = True
                        self.abort_reason = (
                            f"attempt-failure rate {rate:.0%} > {self.max_fail_rate:.0%} "
                            f"after {self.attempts} attempts — systemic; aborting")
                        self.log("GUARD ABORT: " + self.abort_reason)
                        self.stop.set()
                # canary stop
                if self.canary_n and (self.succeeded + self.fail_attempts) >= self.canary_n:
                    self.stop.set()

    def _checkpoint(self) -> None:
        el = time.perf_counter() - self.t0
        avg = (sum(self.timings) / len(self.timings)) if self.timings else 0
        remaining = self.total - self.succeeded
        eff = el / self.succeeded if self.succeeded else 0
        est_rem = remaining * eff
        self.log(
            f"checkpoint: succeeded={self.succeeded}/{self.total} "
            f"fail_attempts={self.fail_attempts} elapsed={el:.0f}s "
            f"avg_llama={avg:.1f}s est_remaining={est_rem:.0f}s")


def worker_loop(worker_id: str, shared: Shared) -> None:
    w = Worker(worker_id=worker_id)
    empty = 0
    try:
        while not shared.stop.is_set():
            jobs, results = w.run_once(batch_size=1)
            if not jobs:
                empty += 1
                if empty >= 3:
                    break
                time.sleep(0.2)
                continue
            empty = 0
            shared.record(results)
    finally:
        w.queue.close()


def run(workers: int, total: int, checkpoint_every: int, canary_n, max_fail_rate: float) -> Shared:
    shared = Shared(total, checkpoint_every, canary_n, max_fail_rate)
    mode = f"canary({canary_n})" if canary_n else "full"
    shared.log(f"=== backfill {mode} start: {workers} workers, total~{total} ===")
    threads = [threading.Thread(target=worker_loop, args=(f"bf_w{k}", shared))
               for k in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    el = time.perf_counter() - shared.t0
    shared.log(f"=== {mode} end: succeeded={shared.succeeded} fail_attempts={shared.fail_attempts} "
               f"elapsed={el:.0f}s aborted={shared.aborted} ===")
    return shared


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v5 Layer 0 backfill runner")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--canary", type=int, default=None, help="stop after K terminal jobs")
    p.add_argument("--checkpoint-every", type=int, default=25)
    p.add_argument("--max-fail-rate", type=float, default=0.25)
    args = p.parse_args(argv)

    q = EvidenceJobQueue()
    pending = q.queue_stats()["pending"]
    q.close()

    shared = run(args.workers, pending, args.checkpoint_every, args.canary, args.max_fail_rate)

    el = time.perf_counter() - shared.t0
    avg = (sum(shared.timings) / len(shared.timings)) if shared.timings else 0
    print(f"MODE={'canary' if args.canary else 'full'} workers={args.workers}")
    print(f"succeeded={shared.succeeded} fail_attempts={shared.fail_attempts} "
          f"attempts={shared.attempts}")
    print(f"elapsed={el:.1f}s avg_llama={avg:.1f}s")
    if shared.timings:
        print(f"per-filing llama: min={min(shared.timings):.1f}s max={max(shared.timings):.1f}s")
    if shared.aborted:
        print(f"ABORTED: {shared.abort_reason}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
