# YUCLAW v5 — Layer 0: Evidence Job Queue

Layer 0 is the durable, observable, multi-node-capable job queue that every
other v5 (ClawFactory) layer depends on. It is the foundation: if Layer 0 is
not correct and fast, nothing above it can be trusted.

This is the **v5 Layer 0 development branch** (`v5-layer0-foundation`),
developed in an isolated git worktree off `v3.0-evidence`. It does **not** touch
v4.0.1 production paths.

## What this layer provides

A single Postgres-backed queue table (`yuclaw_v5.evidence_jobs`) and a Python
interface (`EvidenceJobQueue`) with:

- **Idempotent enqueue** — safe to enqueue the same logical job twice.
- **Atomic multi-worker claim** — `FOR UPDATE SKIP LOCKED`, no double-claim.
- **Priority + FIFO ordering** — high priority first, oldest first within a tier.
- **Retry with dead-lettering** — failures retry up to `max_attempts`, then
  move to `dead_letter` for triage.
- **Lineage** — `parent_job_id` links cascade/child jobs.
- **Observability** — `queue_stats()`, `list_dead_letter()`, and structured
  logging to `~/.yuclaw/v5/queue.log`.

## Isolation guarantees (Day 1 invariants)

1. All state lives in the **`yuclaw_v5`** schema inside the existing
   `yuclaw_events` database. Nothing in `public.*` (v4) is ever written.
2. The only contact with v4 data is a **read-only** `SELECT` in the real-data
   smoke test against `public.events_raw`.
3. No crontab / systemd changes. No new tmux sessions (workers come later).
4. Branch-only: not merged to `main` or `v3.0-evidence`.

## Why Postgres `SKIP LOCKED` over NATS / Kafka

We deliberately chose "boring Postgres" for Layer 0 rather than a dedicated
broker. Rationale:

- **Durability for free.** Jobs, state, retries, results, and lineage are all
  rows in a transactional store. A crash never loses or duplicates a job; the
  claim and the state transition happen in one transaction.
- **`FOR UPDATE SKIP LOCKED` is exactly a work queue.** Multiple workers across
  multiple nodes poll the same table; each grabs a disjoint set of rows with no
  coordination, no double-delivery, and no external lock service.
- **One datastore, not two.** v4 already runs Postgres (`yuclaw_events`). Adding
  Kafka/NATS would mean a second system to operate, monitor, and keep
  consistent with the evidence rows — and would force a two-phase write between
  "queue" and "database of record." With Postgres the queue *is* the database of
  record.
- **Queryable & observable.** "How many jobs are pending? what's dead-lettered?
  what are this worker's claims?" are plain SQL, indexed (see `schema.md`). A
  broker would need a separate metrics path.
- **Transactional enqueue with the producing work.** A job that itself produces
  child jobs can enqueue them in the *same* transaction that records its result
  (pass `conn=`), so children never appear without the parent's commit.
- **Throughput is not the constraint.** Layer 0 carries evidence-extraction jobs
  (filings, news), not millions/sec of telemetry. Postgres SKIP LOCKED handles
  this volume with millisecond latency (see the smoke-test timings). When a real
  throughput ceiling appears, a broker can sit *in front of* this table without
  changing the contract.

Trade-off accepted: workers **poll** rather than receive push. Polling latency
is bounded by the poll interval; for evidence jobs that is fine. If sub-second
push fan-out is ever needed, Postgres `LISTEN/NOTIFY` can wake pollers without
adding a broker.

## Files

```
yuclaw/v5/queue/
  schema.sql                 -- yuclaw_v5 schema + evidence_jobs table + indexes
  core.py                    -- EvidenceJobQueue (the public interface)
  tests/
    test_core.py             -- pytest unit suite (10 tests, live schema)
    smoke_real_filing.py     -- real-data end-to-end smoke test
docs/v5/layer0/
  README.md                  -- this file
  api.md                     -- EvidenceJobQueue method reference + examples
  schema.md                  -- table/index/state-machine reference
  decisions.md               -- design decision log
```

## Running

```bash
# Apply schema (idempotent)
psql -d yuclaw_events -f yuclaw/v5/queue/schema.sql

# Unit tests
python -m pytest yuclaw/v5/queue/tests/test_core.py -v

# Real-data smoke test
python yuclaw/v5/queue/tests/smoke_real_filing.py
```
