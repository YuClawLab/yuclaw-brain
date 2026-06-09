# Layer 0 — Evidence Extraction Worker (Day 2)

`yuclaw/v5/queue/worker.py`

The worker is the consumer side of the Day-1 Evidence Job Queue. It claims
`extract_filing` jobs, reads the real filing body, runs an extraction through
the local Llama 70B, and completes the job through the queue's state machine.
It is **scaffold proof-of-pipeline**, not the full v5 extraction.

## How a job flows

```
claim_next(worker_id, job_types=['extract_filing'], batch_size=1)   # FOR UPDATE SKIP LOCKED
        │  pending ──► claimed
        ▼
mark_running(job_id, worker_id)                                     # claimed ──► running
        ▼
_fetch_filing_text(accession_number)                               # READ-ONLY public.events_raw
        ▼
_extract_with_llama(text)   ── POST /api/generate (Ollama, format=json) ─► {event_type, summary, affected_ticker}
        ▼
mark_succeeded(job_id, result_token_id=uuid4())                    # running ──► succeeded
   (on any exception: mark_failed(job_id, error) ── queue handles retry/dead-letter)
```

- **Queue logic is reused** from `core.EvidenceJobQueue` — the worker never
  re-implements claim/transition/retry logic.
- **`public.*` is read-only.** `_fetch_filing_text` opens an explicit
  `SET SESSION READ ONLY` transaction as defence-in-depth. All writes go to
  `yuclaw_v5` via the queue.
- **Failure routing:** any exception in `process_job` → `mark_failed`, which
  increments `attempts` and either re-queues (`pending`) or dead-letters at
  `max_attempts`. The worker does not implement its own retry.

## Running it

```bash
# bounded run: process whatever is queued, then exit after N empty polls
python3 -m yuclaw.v5.queue.worker --worker-id w1 --max-jobs 5

# tests
python3 yuclaw/v5/queue/tests/smoke_worker_one_filing.py   # MANDATORY one-filing gate
python3 yuclaw/v5/queue/tests/batch_five_filings.py        # 5-filing batch
```

`run()` is **not a daemon**: after `max_empty_polls` consecutive empty claims it
exits cleanly. Day 2 runs it foreground/tmux for one session only — no cron, no
persistent process.

Config (env overrides): `YUCLAW_V5_OLLAMA_URL` (default `http://localhost:11434`),
`YUCLAW_V5_MODEL` (default `yuclaw-llm-70b:latest`), `YUCLAW_V5_LLAMA_TIMEOUT`
(default 300s), `YUCLAW_V5_DSN` (default `dbname=yuclaw_events`).

## Day-2 placeholders (to be replaced)

| Placeholder | Why | Replaced by |
|---|---|---|
| `result_token_id = uuid4()` | Layer 2 evidence tokens / tokens table don't exist yet | Layer 2 |
| `EXTRACTION_PROMPT` (minimal: event_type + 1-sentence summary + ticker, `format=json`, `num_predict=256`) | Day-2 scaffold to prove the pipeline | Layer 1 swarm specialists |
| Model tag `yuclaw-llm-70b:latest` | The live 70B on this box (renamed compliance tag from v3.0); there is **no** `llama3.1:70b` tag | stable, but note the tag |

## Real-data timing observed (2026-06-09, GB10, model warm)

One-filing smoke (Apple 8-K `0000320193-26-000011`, 4216 chars):

| phase | time |
|---|---|
| enqueue | 4.0 ms |
| claim | 5.0 ms |
| mark_running | 1.4 ms |
| **Llama extraction** | **14,148 ms** |
| mark_succeeded | 10.0 ms |
| total | 14,169 ms |

5-filing batch: 5/5 succeeded, 0 failed, 0 dead-letter. Per-filing Llama
**min 10.2s / max 19.0s / avg 15.2s**; wall-clock 76.3s for 5 jobs.

**Takeaway (the May-18 lesson, confirmed):** the queue is microseconds-to-low-ms;
**the Llama call is ~100% of wall-clock** (10–19s per real ~4000-char filing,
warm). The default 300s per-call timeout is comfortably generous. A first cold
call additionally pays a ~one-time model load (~tens of seconds / ~42 GB into
VRAM). Throughput planning for any future backfill must budget on Llama latency,
not the queue.
