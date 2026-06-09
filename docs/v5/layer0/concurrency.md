# Layer 0 — Concurrency, Retry & Dead-Letter (Day 3A)

Day 3A hardens Layer 0 *before* any backfill: proving the queue is correct under
genuine parallelism and that the failure paths behave. Synthetic/fast jobs;
minutes, not hours.

Tests:
- `tests/test_concurrency.py` — parallel SKIP LOCKED (no Llama)
- `tests/test_retry_deadletter.py` — retry + dead-letter (no Llama)
- `tests/test_llama_concurrency.py` — real-Llama concurrency probe (only if Ollama up)

## 1. SKIP LOCKED proven under true parallelism ✅

60 synthetic `noop` jobs per round; M workers, each its **own**
`EvidenceJobQueue` (own connection pool) to simulate independent processes;
all started on a `threading.Barrier` for maximal contention; `batch_size=1` so
every claim is a separate race.

| workers | jobs | total claimed | distinct | **double-claims** | missing | hung | elapsed |
|--------:|-----:|--------------:|---------:|------------------:|--------:|-----:|--------:|
| 2 | 60 | 60 | 60 | **0** | 0 | 0 | 0.251s |
| 4 | 60 | 60 | 60 | **0** | 0 | 0 | 0.165s |
| 8 | 60 | 60 | 60 | **0** | 0 | 0 | 0.120s |

Per-worker distribution was even (e.g. 8 workers ≈ 7–8 jobs each), confirming
workers genuinely race and `FOR UPDATE SKIP LOCKED` hands each row to exactly
one. Every job ended `succeeded`; none stuck in pending/claimed/running.

**Guarantee proven:** with N workers polling the same queue concurrently, every
job is claimed exactly once — no double-claim, no lost job, no deadlock. This is
the core Layer-0 invariant the backfill depends on.

## 2. Retry + dead-letter semantics validated ✅ (13/13 checks)

`mark_failed` (the logic lives in `core.mark_failed`, the worker just calls it):
- failure under `max_attempts` → state back to **`pending`**, `attempts`
  incremented, claim released (`claimed_by`/`claimed_at` cleared) so any worker
  can retry;
- failure **at** `max_attempts` → **`dead_letter`** (no infinite retry);
- `last_error` and `failed_at` populated; `list_dead_letter()` returns the job
  with its `last_error`;
- transient failure then success → ends **`succeeded`** (recovery works).

End-to-end through the real `Worker`: a job with a bogus accession deterministically
fails inside `process_job` (no filing text) → `run_once` routes it to
`mark_failed` → after `max_attempts` it dead-letters, with the real
`WorkerError` as `last_error`. The worker is correctly wired to the queue's
failure handling. (No Llama needed for any of this.)

## 3. Real-Llama concurrency finding (Phase 4) — for backfill planning

2 workers, 3 real ~4000-char filings, `yuclaw-llm-70b:latest`, model pre-warmed.
**0 double-claims** under real load. Per-call wall-clock intervals (relative s):

```
worker_0   15.58s   [ 0.03 -> 15.62]
worker_1   30.52s   [ 0.06 -> 30.58]
worker_0   33.26s   [15.63 -> 48.89]
```

- The two initial calls **overlapped ~15.6s** → Ollama **does serve concurrent
  generate calls in parallel** here. (This updates the Day-2 assumption that
  `OLLAMA_NUM_PARALLEL=1` would force serialization — observed behaviour is
  concurrent; the setting was evidently raised, or the GB10 scheduler runs
  multiple runners.)
- **But it's sublinear.** Under 2-way concurrency each call ran ~**2× slower**
  (~30s vs ~15s solo) due to shared-GPU compute contention. Sum of Llama times
  79.4s vs wall-clock 49.0s → ≈**1.6× throughput** for 2 workers, **not 2×**.

**Backfill-planning takeaway:** more workers help throughput, but with strongly
diminishing returns — the single GB10 is the bottleneck, and per-call latency
rises as concurrency rises. A sensible backfill likely uses a small worker count
(≈2) and budgets on Llama latency (10–19s/filing solo, ~2× under contention),
not on queue capacity. The queue itself is not the constraint (Phase 1 proved it
handles 8 workers in ~0.1s for 60 jobs). True throughput scaling would require
sharding extraction across multiple model servers/GPUs.
