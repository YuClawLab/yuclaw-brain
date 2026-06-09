# Layer 0 — Day 3B Backfill (281 filings)

First real backfill: the 281 unprocessed `public.events_raw` filings extracted
end-to-end through the queue + 2 workers + local Llama 70B, on 2026-06-09.
Runner: `yuclaw/v5/queue/run_backfill.py`.

## Result

| metric | value |
|---|---|
| Enqueued (idempotent) | 281 (281 rows == 281 keys == 281 enqueued) |
| **Succeeded** | **281 / 281 (100%)** |
| Dead-lettered | **0** |
| Failed attempts | **0** |
| Workers | 2 (`yuclaw-llm-70b:latest`) |
| Canary (first 11) | 11/11 succeeded, gate PASS |
| Full run (remaining 270) | 270/270 succeeded, 4123s (68.7 min) |
| Final `queue_stats` | `{pending:0, claimed:0, running:0, succeeded:287, failed:0, dead_letter:0}` |
| Stuck jobs (claimed+running) | 0 — queue fully drained |

(287 succeeded = 6 Day-2 jobs + 281 backfill.)

## Canary gate (the May-18 safeguard)

Ran 2 workers, paused after the first ~10 filings. Gate (≥7/10 succeed, per-filing
<45s, no crash): **11/11 succeeded, avg 34.2s, max 38.3s, no crash → PASS.** The
canary caught the real timing up front: ~34s/filing under 2-way concurrency on
the full corpus, not the 15–22s scoping estimate.

## Actual vs estimated timing

| | scoping estimate | actual |
|---|---|---|
| per-filing Llama (2 workers) | 15–22s | **30.4s avg** (15.7–41.6s) |
| effective wall/filing | ~9.4s | **~15.3s** (4123s / 270) |
| full-run wall-clock | 45–60 min | **68.7 min** |

The estimate was optimistic. Two compounding reasons, both identified before the
full run committed:
1. **Larger inputs** — corpus median 6,386 chars (worker caps at 6,000) vs the
   ~4,000-char filings Day-3A timed at 15s.
2. **GPU contention** — Day-3A's ~2× slowdown under 2-way concurrency on the
   single GB10.

Checkpoint avg_llama held steady at ~31s the whole run (no degradation/thermal
drift over 68 min). The rolling 25% dead-letter guard never tripped (0 failures).

## Dead-letter analysis

**None.** Zero filings failed — the corpus is uniform, well-formed, mid-sized
(118–8,000 chars, no long tail), and the proven extraction path handled every
one on the first attempt. The retry/dead-letter machinery (validated in 3A) was
therefore not exercised by real data here, which is the desired outcome.

## Extraction quality (3-sample eyeball)

The Day-2 worker does **not persist** extraction content yet (`result_token_id`
is a uuid4 placeholder; output is logged as keys only — to be persisted when
Layer 1/2 land). Samples below are re-extractions for a quality check:

- `8-K` AAPL → `earnings` — "Apple reports financial results for its second
  fiscal quarter ended March 28, 2026."
- `10-Q` AAPL → `debt` — "Apple's debt obligations include notes due in 2026,
  2027, 2029, and 2042."
- `10-K` ABBV → `debt` — "AbbVie issued senior notes due in various years."

Coherent, correct tickers, sensible summaries. The 10-Q/10-K classifying as
`debt` reflects the **minimal single-event scaffold prompt** + 8,000-char excerpt
truncation (the visible excerpt was debt-heavy) — a known Day-2 limitation, to be
replaced by Layer 1 swarm specialists.

## Resumability

The whole run is idempotent (`idempotency_key = backfill:<accession>`):
re-running enqueue creates no duplicates, and only unprocessed filings (no
succeeded job for the accession) are picked up. A partial/aborted run can be
re-launched safely. Proven at scale in the Day-3B scoping pass.

## Backfill-planning takeaway (for future, larger corpora)

- Throughput is **~15s/filing effective at 2 workers** on this GB10 for
  ~6,000-char filings — budget on this, not the optimistic 9.4s.
- 2 workers is the practical max on one GB10 (3A: sublinear, GPU-bound).
- A corpus of N filings ≈ **N × 15s** wall-clock at 2 workers (e.g. 1,000
  filings ≈ ~4.2 hr → an overnight job, not a session).
- The queue is never the bottleneck (8 workers drained 60 synthetic jobs in
  0.1s in 3A); the single model server is.
