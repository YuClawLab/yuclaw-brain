# Layer 0 — Design Decision Log

Decisions made on Day 1 (2026-06-04). Cross-AI design (ChatGPT + Gemini) was
pre-validated; this log records the concrete choices made during implementation.

## D1 — Datastore: Postgres `SKIP LOCKED`, not NATS/Kafka

See README "Why Postgres SKIP LOCKED over NATS/Kafka". Summary: durability,
queryability, single operational system, and transactional enqueue-with-result
outweigh the push-vs-poll latency cost for evidence-volume workloads. A broker
can front this table later without changing the `EvidenceJobQueue` contract.

## D2 — Schema isolation by schema, not by database

v5 lives in a **new `yuclaw_v5` schema inside the existing `yuclaw_events`
database**, not a new database. This keeps v5 jobs transactionally close to v4
evidence (a future job can read v4 `public.*` and write `yuclaw_v5.*` in one
transaction) while still being cleanly namespaced and droppable. `public.*` is
never written by Layer 0.

## D3 — Database name correction (`yuclaw` → `yuclaw_events`)

The original spec referenced `psql -d yuclaw`. The live v4 database is actually
`yuclaw_events` (confirmed via v4's own DSN: `dbname=yuclaw_events` in
`v3/sources/edgar_poll.py` and `v3/extract/event_worker.py`). We use
`dbname=yuclaw_events`, overridable via the `YUCLAW_V5_DSN` env var.

## D4 — Smoke-test data source (`public.events` → `public.events_raw`)

The spec's smoke test referenced `public.events(filing_id, raw_text)` with a
~4000 char body. In the live schema:
- `public.events` has **no** `filing_id`/`raw_text`; its body column
  `raw_excerpt` is **capped at 400 chars** by a CHECK constraint.
- The full filing body lives in **`public.events_raw.raw_text`**, keyed by
  `accession_number` (and `raw_id`).

So the smoke test pulls a real ~4000 char filing from `public.events_raw`
(41 such rows exist in the 3500–4500 char band). The read is wrapped in a
`SET SESSION READ ONLY` transaction as defence-in-depth — the smoke test can
never write v4 data.

## D5 — Idempotency key composition

The queue treats `idempotency_key` as an **opaque caller-supplied unique
string**; it does not impose a format. Recommended convention for callers:

```
<job_type>:<natural_key>
e.g.  extract_filing:0000320193-26-000011
```

so re-enqueuing the same logical unit of work (same filing, same job type) is a
no-op. **First write wins** on payload: a conflicting enqueue returns the
existing `job_id` and does not overwrite the stored payload. Callers that need
per-attempt uniqueness (e.g. the smoke test) append a random suffix.

Rationale for first-write-wins: an idempotency key asserts "this job already
exists"; silently mutating its payload on a duplicate enqueue would violate that
assertion and could race with a worker already processing it.

## D6 — Priority semantics

`priority` is an `INT`, default `100`, **higher = sooner**. `claim_next` orders
`priority DESC, created_at ASC`, so within a priority tier jobs are strict FIFO
by enqueue time. There is no starvation protection at Layer 0 (a flood of high
priority jobs can delay low ones); if needed, that belongs in the scheduler that
*sets* priorities, not in the queue. Chose "higher = sooner" because it reads
naturally ("priority 900 beats priority 10") and lets callers leave room above
the default 100 without renumbering.

## D7 — Dead-letter threshold

A job dead-letters when `attempts >= max_attempts` (default `max_attempts = 3`,
i.e. 1 initial try + 2 retries). On a non-terminal failure the job returns to
`pending` with the claim **released** (`claimed_by`/`claimed_at` cleared) so any
worker can pick it up. On dead-letter the claim fields are **retained** for
forensics (which worker last held it). `max_attempts` is per-job (column), so
callers can override per job type.

## D8 — `available_as_of` set once, at first claim

`available_as_of` records the as-of time of the evidence. If the enqueuer knows
it (e.g. a filing's publish time) it is passed at enqueue and preserved. If not,
`claim_next` stamps it `COALESCE(available_as_of, now())` at first claim. This
gives every job a definite as-of time without forcing the producer to compute
one, while never overwriting a known value.

## D9 — Connection pool + transaction reuse

`ThreadedConnectionPool(min=2, max=10)` (per spec). Every method takes an
optional `conn` for transaction reuse: pass your own connection to make an
operation part of a larger transaction (e.g. enqueue child jobs atomically with
recording the parent's result). When `conn` is omitted the method
borrows/commits/returns automatically. This is the mechanism that lets job
fan-out be transactionally consistent.

## D10 — Development location: isolated git worktree

Per the production-isolation invariant, v5 Layer 0 was developed on branch
`v5-layer0-foundation` in a **separate git worktree** (`/home/zhangd2/yuclaw-v5`)
forked from `v3.0-evidence` — chosen over branching in place because the primary
`/home/zhangd2/yuclaw` checkout is on the auto-publishing `main` branch (not
`v3.0-evidence`, contrary to the task's assumption) and carries live `output/`
artifacts. A dedicated worktree leaves both the `main` and `v3.0-evidence`
checkouts untouched.
