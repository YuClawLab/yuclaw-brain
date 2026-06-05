# `EvidenceJobQueue` — API Reference

`yuclaw/v5/queue/core.py`

```python
from yuclaw.v5.queue.core import EvidenceJobQueue, new_token_id

q = EvidenceJobQueue()              # dsn defaults to "dbname=yuclaw_events"
                                    # (override via YUCLAW_V5_DSN env var)
```

## Connection model

The queue owns a `psycopg2.pool.ThreadedConnectionPool` (min 2, max 10 by
default). **Every public method accepts an optional `conn` argument:**

- `conn=None` (default): the method borrows a connection from the pool, commits
  on success, rolls back on error, and returns it to the pool.
- `conn=<connection>`: the method runs inside *your* transaction and does **not**
  commit or return the connection — you own its lifecycle. Use this to enqueue
  child jobs atomically with the work that produced them.

Call `q.close()` to close all pooled connections when shutting down.

## Methods

### `enqueue(job_type, payload, priority=100, idempotency_key=None, parent_job_id=None, available_as_of=None, trace_id=None, max_attempts=3, conn=None) -> str`

Insert a job; returns its `job_id` (UUID string).

- `payload` is any JSON-serialisable dict (stored as JSONB).
- If `idempotency_key` is given, enqueue is **idempotent**: a second call with
  the same key inserts nothing and returns the existing `job_id` (first write
  wins on payload).
- `available_as_of` is the as-of timestamp of the evidence. If omitted, it is
  stamped at claim time (see `claim_next`).

```python
job_id = q.enqueue(
    "extract_filing",
    {"accession_number": "0000320193-26-000011", "raw_text": "..."},
    priority=200,
    idempotency_key="extract_filing:0000320193-26-000011",
)
```

### `claim_next(worker_id, job_types=None, batch_size=1, conn=None) -> list[dict]`

Atomically claim up to `batch_size` pending jobs for `worker_id`.

- Uses `SELECT ... FOR UPDATE SKIP LOCKED`: concurrent workers never claim the
  same row.
- Ordering: `priority DESC, created_at ASC` (high priority first, FIFO within a
  priority).
- `job_types` (optional list) restricts which job types this worker will pull.
- On claim, each job goes `pending -> claimed`, with `claimed_by`, `claimed_at`,
  and `available_as_of = COALESCE(available_as_of, now())`.
- Returns a list of job dicts (empty if nothing available).

```python
for job in q.claim_next("worker-1", job_types=["extract_filing"], batch_size=4):
    process(job)
```

### `mark_running(job_id, worker_id, conn=None) -> bool`

Transition `claimed -> running` for a job held by `worker_id`. Returns `True` if
the row matched (right worker, state was `claimed`).

### `mark_succeeded(job_id, result_token_id=None, conn=None) -> bool`

Transition `claimed`/`running` -> `succeeded`, stamp `succeeded_at`, and store
`result_token_id` (the Layer-1 evidence token this job produced). Returns
`True` on success.

```python
from yuclaw.v5.queue.core import new_token_id
q.mark_succeeded(job_id, new_token_id())
```

### `mark_failed(job_id, error_text, conn=None) -> bool`

Record a failure. Increments `attempts`, stores `last_error` and `failed_at`.

- If `attempts >= max_attempts`: job moves to **`dead_letter`** (claim retained
  for forensics).
- Otherwise: job returns to **`pending`** with the claim released
  (`claimed_by`/`claimed_at` cleared) so any worker can retry.

Returns `True` if a row was updated.

### `get_job(job_id, conn=None) -> dict | None`

Return the full job row as a dict, or `None` if not found.

### `list_dead_letter(limit=100, conn=None) -> list[dict]`

Return dead-lettered jobs, most recent `failed_at` first.

### `queue_stats(conn=None) -> dict`

Return a count per state. **All six state keys are always present** (zero-filled):

```python
{"pending": 12, "claimed": 3, "running": 1,
 "succeeded": 480, "failed": 0, "dead_letter": 2}
```

## Atomic parent + child enqueue (transaction reuse)

```python
conn = q._pool.getconn()
try:
    parent = q.enqueue("scan_company", {"cik": "320193"}, conn=conn)
    q.enqueue("extract_filing", {...}, parent_job_id=parent, conn=conn)
    conn.commit()          # parent and child commit together
except Exception:
    conn.rollback()
    raise
finally:
    q._pool.putconn(conn)
```

## Logging

All operations log to `~/.yuclaw/v5/queue.log` via the `yuclaw.v5.queue` logger
(INFO level, one line per operation with job_id, type, worker, outcome).
