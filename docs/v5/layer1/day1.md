# v5 Layer 1 — Day 1 writeup

Branch `v5-layer1`, based off `v5-layer0-foundation` @ 90f23392.

Goal for Day 1: stand up the agent **swarm** — Bull / Bear / Skeptic 8B debate
agents running concurrently, reconciled by a 70B Synthesis agent — driving one
real SEC filing end-to-end through the reused Layer 0 `EvidenceJobQueue`, and
prove it on a small batch. Design rationale (the C6 risk-gate evidence behind the
dual return/risk channel) is recorded in `design_inputs.md`.

## What was built

- `yuclaw/v5/swarm/agents.py` — `Bull/Bear/Skeptic` 8B agents + a 70B
  `SynthesisAgent`. Every agent emits structured JSON carrying **both** a
  `return_view` and a `risk_view` (risk channel first-class from Day 1, per
  `design_inputs.md` amendment 3). Tolerant validation fills gaps and records
  `schema_warnings` rather than throwing.
- `yuclaw/v5/swarm/orchestrator.py` — `SwarmOrchestrator.dispatch(accession)`:
  reads the filing READ-ONLY from `public.events_raw`, enqueues 3 `swarm_agent`
  jobs (idempotent on accession+role+version), runs them **concurrently** through
  the queue's multi-worker `SKIP LOCKED` claim path (3 threads → 3 parallel 8B
  calls), then enqueues + runs one `swarm_synthesis` (70B) job, and persists to
  `yuclaw_v5.swarm_outputs`. Writes only to schema `yuclaw_v5`.
- Tests: `swarm/tests/smoke_one_filing.py` (the hard gate) and
  `swarm/tests/batch_three_filings.py` (the watched small batch).

The Layer 0 queue is **reused, never reimplemented**. The only Layer 0 change is
one additive primitive — `EvidenceJobQueue.release()` (see "Bugs found", below).

## Hard gate — one-filing smoke (PASS)

Filing `0000097745-26-000018` (Thermo Fisher, ~6k chars) through the full path:

- Three agents produced **genuinely distinct** stances:
  bull=`positive`, bear=`negative`, skeptic=`mixed`; no empty `key_points`;
  zero schema warnings.
- **Concurrency proven**: agent wall-clock `57.9s` = `max(57.89, 45.49, 33.28)`,
  i.e. the three 8B calls truly overlapped (sum would be ~136s).
- Synthesis `112s` on a quiet box; persisted to `swarm_outputs`. GATE: PASS.

## Small batch — 3 distinct filings (PASS, 3/3)

`0000097745-26-000018`, `0001645590-26-000052`, `0000320193-26-000013`
(`batch_three_filings.py`, after the two fixes below):

| filing               | bull/bear/skeptic            | synth   | agent_wall | synth_secs | total   |
|----------------------|------------------------------|---------|-----------:|-----------:|--------:|
| 0000097745-26-000018 | positive/negative/mixed      | neutral |     35.1s  |    96.8s\* |  131.9s |
| 0001645590-26-000052 | positive/negative/neutral    | mixed   |     40.1s  |    89.3s   |  129.5s |
| 0000320193-26-000013 | positive/negative/mixed      | neutral |     37.1s  |    88.4s   |  125.5s |

\* first synthesis includes the 70B cold-load; the rest run warm. batch_wall
`387s`. All three persisted (unique on accession+prompt_version; filing 1
upserts over the smoke row).

## Bugs found by the batch (and fixed)

The first batch run failed 1/3 and surfaced two linked defects:

1. **Truncated agent JSON (root cause).** `num_predict=420` was too tight: when
   an 8B gets verbose in `evidence_cited`, the `format=json` grammar runs out of
   tokens mid-string and emits **invalid (truncated) JSON**, which `json.loads`
   rejects → the whole filing fails ("Unterminated string"). **Fix:** raise the
   agent token budget to `AGENT_NUM_PREDICT=768` (env-tunable). The smaller schema
   plus synthesis already proved 640 sufficient; 768 gives the agents ~2x headroom.

2. **Foreign-job handling corrupted neighbours (cascade).** When a filing failed,
   the queue's retry returned its agent job to `pending`. The *next* dispatch's
   worker then claimed that leftover job (different `trace_id`); the orchestrator
   responded by calling `mark_failed` on it — charging an attempt against a job
   that belonged to another dispatch and driving an innocent neighbour toward
   `dead_letter` — **and** aborting its own dispatch. One truncation thereby
   poisoned the following filing. **Fix:** on a foreign claim the orchestrator now
   `release()`s the job back to `pending` intact (new Layer 0 primitive; never
   charges an attempt) before failing loudly. Fully draining a contended/leftover
   queue across concurrent dispatches is deliberately **deferred** to later
   Layer-1 work (consistent with `design_inputs.md`, which scopes structural
   concurrency hardening as later-day).

After both fixes the 3-filing batch passes 3/3 with a clean queue
(9 `swarm_agent` + 3 `swarm_synthesis`, all `succeeded`, zero `dead_letter`).

## Operational note — the Day-1 freeze

Day-1's first attempt was interrupted by a GB10 unified-memory collision: a
concurrent **non-YUCLAW** `llama-server` workload starved Ollama and the 70B
synthesis hung; the box was power-cycled. Re-run on a quiet, exclusive box, the
synthesis completes in ~90–112s — well under the default 300s timeout. So the
freeze was a **memory-contention** failure, not a timeout-too-low one; no
permanent timeout change was needed. New rule baked into the swarm tests: a
preflight that refuses to run if any non-Ollama model server is present and
reports free-memory headroom before driving any Ollama work.

## Known limitations (for later Layer-1 days)

- **8B agents fabricate specific figures.** The v1 role prompts elicit invented
  dollar amounts and even contradictory facts (e.g. bull "debt decreased" vs bear
  "debt increased" on the same filing). Day-1 validates the *plumbing*
  (concurrency, differentiation, dual-channel schema, persistence), not numeric
  fidelity. Grounding/citation discipline is a prompt-iteration task for a later
  day.
- **Insider/material-event split** and **horizon-aware synthesis**
  (`design_inputs.md` amendments 1 & 2) remain scaffolded in prompts only.
- **Concurrent-dispatch robustness** beyond non-corrupting release (above).

## Cross-references

- Design inputs: `docs/v5/layer1/design_inputs.md`
- Layer 0 queue: `yuclaw/v5/queue/core.py` (`EvidenceJobQueue`, reused)
- Hard gate: `yuclaw/v5/swarm/tests/smoke_one_filing.py`
- Small batch: `yuclaw/v5/swarm/tests/batch_three_filings.py`
