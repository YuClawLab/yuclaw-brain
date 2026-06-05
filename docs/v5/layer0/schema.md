# Schema Reference — `yuclaw_v5.evidence_jobs`

Source: `yuclaw/v5/queue/schema.sql`
Database: `yuclaw_events` · Schema: `yuclaw_v5` (isolated from v4's `public`).

## Table

| Column            | Type          | Notes |
|-------------------|---------------|-------|
| `job_id`          | `UUID` PK     | `DEFAULT gen_random_uuid()` (core fn, PG13+). |
| `job_type`        | `TEXT NOT NULL` | Logical kind, e.g. `extract_filing`. Workers filter on this. |
| `payload`         | `JSONB NOT NULL` | Arbitrary job input. |
| `state`           | `TEXT NOT NULL` | `CHECK` in (`pending`,`claimed`,`running`,`succeeded`,`failed`,`dead_letter`). Default `pending`. |
| `priority`        | `INT NOT NULL` | Default `100`. Higher = sooner. |
| `attempts`        | `INT NOT NULL` | Default `0`. Incremented by `mark_failed`. |
| `max_attempts`    | `INT NOT NULL` | Default `3`. Threshold to dead-letter. |
| `claimed_by`      | `TEXT`        | Worker id holding the job. |
| `claimed_at`      | `TIMESTAMPTZ` | When claimed. |
| `available_as_of` | `TIMESTAMPTZ` | Evidence as-of time; `COALESCE`d to `now()` at claim. |
| `succeeded_at`    | `TIMESTAMPTZ` | Set by `mark_succeeded`. |
| `failed_at`       | `TIMESTAMPTZ` | Set by `mark_failed` (last failure). |
| `result_token_id` | `UUID`        | Layer-1 evidence token produced by the job. |
| `parent_job_id`   | `UUID`        | Lineage: parent that spawned this job. |
| `trace_id`        | `TEXT`        | Distributed-trace correlation id. |
| `idempotency_key` | `TEXT UNIQUE` | Dedupe key for idempotent enqueue. |
| `last_error`      | `TEXT`        | Most recent failure message. |
| `created_at`      | `TIMESTAMPTZ NOT NULL` | `DEFAULT now()`. FIFO tiebreak. |

## Indexes & rationale

| Index | Definition | Why |
|-------|------------|-----|
| `evidence_jobs_pkey` | PK on `job_id` | Point lookups (`get_job`, all state transitions). |
| `evidence_jobs_idempotency_key_key` | `UNIQUE (idempotency_key)` | Enforces idempotent enqueue; backs `ON CONFLICT`. |
| `idx_jobs_pending` | `(state, priority DESC, created_at ASC) WHERE state='pending'` | The hot path. Exactly matches `claim_next`'s `WHERE state='pending' ORDER BY priority DESC, created_at ASC`. Partial → tiny (only pending rows), so claims stay fast even with millions of finished jobs. |
| `idx_jobs_claimed_by` | `(claimed_by) WHERE state='claimed'` | "What is worker X holding?" — operational/recovery queries. Partial keeps it to live claims. |
| `idx_jobs_parent` | `(parent_job_id) WHERE parent_job_id IS NOT NULL` | Lineage walks (children of a job). |
| `idx_jobs_dead_letter` | `(failed_at DESC) WHERE state='dead_letter'` | Dead-letter triage newest-first; backs `list_dead_letter`. |

Partial indexes are used throughout so each index only covers the rows that
query actually targets — important because the table is append-mostly and the
vast majority of rows eventually settle in `succeeded`.

## State machine

```
                         enqueue
                            |
                            v
                       +---------+
              +------>  | pending |
              |         +---------+
              |              |
              | mark_failed  | claim_next            (FOR UPDATE SKIP LOCKED;
              | (attempts <  |                         available_as_of stamped)
              |  max)        v
              |         +---------+
              |         | claimed |
              |         +---------+
              |          |       \
              |  mark_   |        \ mark_succeeded
              |  running |         \
              |          v          v
              |     +---------+  +-----------+
              +-----|         |  | succeeded |  (terminal, result_token_id set)
              | fail| running |  +-----------+
              | <max+---------+
              |          |
              |          | mark_succeeded -> succeeded
              |          |
              |          | mark_failed (attempts >= max)
              |          v
              |     +-------------+
              +---->| dead_letter |  (terminal; triage via list_dead_letter)
   mark_failed      +-------------+
   (attempts>=max)
```

Notes:
- `mark_failed` from `claimed` or `running`: increments `attempts`; back to
  `pending` (claim released) if under `max_attempts`, else `dead_letter`.
- `succeeded` and `dead_letter` are terminal.
- `available_as_of` is set once, at first claim, if not supplied at enqueue.
