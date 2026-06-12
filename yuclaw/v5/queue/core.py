"""YUCLAW v5 Layer 0 — Evidence Job Queue.

A durable, observable, multi-node-capable job queue built on PostgreSQL's
``SELECT ... FOR UPDATE SKIP LOCKED``. Every other v5 layer (ClawFactory)
depends on this foundation.

Isolation guarantees:
  * All state lives in the ``yuclaw_v5`` schema. Nothing in ``public.*`` (v4)
    is ever written by this module.
  * Target database is ``yuclaw_events`` (v4's existing Postgres database),
    but isolated by schema, not by database.

Concurrency model:
  * ``claim_next`` uses ``FOR UPDATE SKIP LOCKED`` so N workers across N nodes
    can poll the same queue without ever double-claiming a job.

All public methods accept an optional ``conn`` argument. When supplied, the
method participates in the caller's transaction and does NOT commit or return
the connection to the pool (the caller owns its lifecycle). When omitted, the
method borrows a connection from the pool, commits on success, rolls back on
error, and always returns the connection to the pool.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

DEFAULT_DSN = os.environ.get("YUCLAW_V5_DSN", "dbname=yuclaw_events")
SCHEMA = "yuclaw_v5"
TABLE = f"{SCHEMA}.evidence_jobs"

JOB_STATES = ("pending", "claimed", "running", "succeeded", "failed", "dead_letter")

# --------------------------------------------------------------------------
# Structured logging -> ~/.yuclaw/v5/queue.log
# --------------------------------------------------------------------------

_LOG_DIR = Path(os.path.expanduser("~/.yuclaw/v5"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_PATH = _LOG_DIR / "queue.log"

logger = logging.getLogger("yuclaw.v5.queue")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _handler = logging.FileHandler(_LOG_PATH)
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(_handler)
    logger.propagate = False


# --------------------------------------------------------------------------
# Queue
# --------------------------------------------------------------------------


class EvidenceJobQueue:
    """PostgreSQL-backed evidence job queue.

    Parameters
    ----------
    dsn:
        libpq connection string. Defaults to ``dbname=yuclaw_events`` (override
        via the ``YUCLAW_V5_DSN`` environment variable).
    minconn / maxconn:
        Bounds for the underlying ``ThreadedConnectionPool`` (defaults 2 / 10).
    """

    def __init__(
        self,
        dsn: str = DEFAULT_DSN,
        minconn: int = 2,
        maxconn: int = 10,
    ) -> None:
        self.dsn = dsn
        self._pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn=dsn)
        logger.info(
            "EvidenceJobQueue initialised dsn=%r pool=%d-%d", dsn, minconn, maxconn
        )

    # -- connection lifecycle ----------------------------------------------

    @contextmanager
    def _connection(self, conn: Optional[Any]) -> Iterator[Any]:
        """Yield a connection, managing commit/rollback/return when we own it.

        If ``conn`` is provided, we yield it untouched and leave commit/rollback
        and pool-return to the caller (transaction reuse). Otherwise we borrow
        one from the pool, commit on clean exit, roll back on exception, and
        always return it to the pool.
        """
        if conn is not None:
            yield conn
            return

        owned = self._pool.getconn()
        try:
            yield owned
            owned.commit()
        except Exception:
            owned.rollback()
            raise
        finally:
            self._pool.putconn(owned)

    @staticmethod
    def _dict_cursor(conn: Any):
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def close(self) -> None:
        """Close all pooled connections. Idempotent."""
        if self._pool and not self._pool.closed:
            self._pool.closeall()
            logger.info("EvidenceJobQueue pool closed")

    # -- enqueue -----------------------------------------------------------

    def enqueue(
        self,
        job_type: str,
        payload: dict,
        priority: int = 100,
        idempotency_key: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        available_as_of: Optional[Any] = None,
        trace_id: Optional[str] = None,
        max_attempts: int = 3,
        conn: Optional[Any] = None,
    ) -> str:
        """Insert a job and return its ``job_id`` (str UUID).

        Idempotent when ``idempotency_key`` is supplied: a second enqueue with
        the same key inserts nothing and returns the already-stored ``job_id``.
        """
        insert_sql = f"""
            INSERT INTO {TABLE}
                (job_type, payload, priority, idempotency_key,
                 parent_job_id, available_as_of, trace_id, max_attempts)
            VALUES (%s, %s, %s, %s, %s::uuid, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING job_id
        """
        params = (
            job_type,
            psycopg2.extras.Json(payload),
            priority,
            idempotency_key,
            parent_job_id,
            available_as_of,
            trace_id,
            max_attempts,
        )
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(insert_sql, params)
                row = cur.fetchone()
                if row is not None:
                    job_id = str(row[0])
                    logger.info(
                        "enqueue job_id=%s type=%s priority=%s idem=%s",
                        job_id, job_type, priority, idempotency_key,
                    )
                    return job_id
                # Conflict on idempotency_key: fetch the existing job_id.
                cur.execute(
                    f"SELECT job_id FROM {TABLE} WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                job_id = str(existing[0])
                logger.info(
                    "enqueue idempotent-hit job_id=%s idem=%s", job_id, idempotency_key
                )
                return job_id

    # -- claim -------------------------------------------------------------

    def claim_next(
        self,
        worker_id: str,
        job_types: Optional[list] = None,
        batch_size: int = 1,
        conn: Optional[Any] = None,
    ) -> list:
        """Atomically claim up to ``batch_size`` pending jobs.

        Uses ``FOR UPDATE SKIP LOCKED`` so concurrent workers never contend for
        the same row. Claimed jobs transition ``pending -> claimed`` with
        ``claimed_by``/``claimed_at`` set and ``available_as_of`` defaulted to
        ``now()`` if it was not provided at enqueue time.

        Returns a list of job dicts (possibly empty).
        """
        type_filter = ""
        select_params: list = []
        if job_types:
            type_filter = "AND job_type = ANY(%s)"
            select_params.append(list(job_types))
        select_params.append(batch_size)

        # Single statement: the CTE locks pending rows with SKIP LOCKED, the
        # UPDATE flips them to claimed. Atomic within one transaction.
        claim_sql = f"""
            WITH claimed AS (
                SELECT job_id
                FROM {TABLE}
                WHERE state = 'pending' {type_filter}
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE {TABLE} j
            SET state = 'claimed',
                claimed_by = %s,
                claimed_at = now(),
                available_as_of = COALESCE(j.available_as_of, now())
            FROM claimed
            WHERE j.job_id = claimed.job_id
            RETURNING j.*
        """
        params = tuple(select_params) + (worker_id,)
        with self._connection(conn) as c:
            with self._dict_cursor(c) as cur:
                cur.execute(claim_sql, params)
                rows = [dict(r) for r in cur.fetchall()]
        logger.info(
            "claim_next worker=%s requested=%d claimed=%d types=%s",
            worker_id, batch_size, len(rows), job_types,
        )
        return rows

    # -- state transitions -------------------------------------------------

    def mark_running(
        self, job_id: str, worker_id: str, conn: Optional[Any] = None
    ) -> bool:
        """Transition ``claimed -> running`` for a job held by ``worker_id``."""
        sql = f"""
            UPDATE {TABLE}
            SET state = 'running'
            WHERE job_id = %s::uuid
              AND state = 'claimed'
              AND claimed_by = %s
            RETURNING job_id
        """
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(sql, (job_id, worker_id))
                ok = cur.fetchone() is not None
        logger.info("mark_running job_id=%s worker=%s ok=%s", job_id, worker_id, ok)
        return ok

    def mark_succeeded(
        self,
        job_id: str,
        result_token_id: Optional[str] = None,
        conn: Optional[Any] = None,
    ) -> bool:
        """Transition a job to ``succeeded`` and stamp ``succeeded_at``."""
        sql = f"""
            UPDATE {TABLE}
            SET state = 'succeeded',
                succeeded_at = now(),
                result_token_id = %s::uuid
            WHERE job_id = %s::uuid
              AND state IN ('claimed', 'running')
            RETURNING job_id
        """
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(sql, (result_token_id, job_id))
                ok = cur.fetchone() is not None
        logger.info(
            "mark_succeeded job_id=%s token=%s ok=%s", job_id, result_token_id, ok
        )
        return ok

    def mark_failed(
        self, job_id: str, error_text: str, conn: Optional[Any] = None
    ) -> bool:
        """Record a failure.

        Increments ``attempts``. If the new attempt count reaches
        ``max_attempts`` the job moves to ``dead_letter``; otherwise it returns
        to ``pending`` (claim released) for retry.
        """
        sql = f"""
            UPDATE {TABLE}
            SET attempts = attempts + 1,
                last_error = %s,
                failed_at = now(),
                state = CASE
                    WHEN attempts + 1 >= max_attempts THEN 'dead_letter'
                    ELSE 'pending'
                END,
                claimed_by = CASE
                    WHEN attempts + 1 >= max_attempts THEN claimed_by
                    ELSE NULL
                END,
                claimed_at = CASE
                    WHEN attempts + 1 >= max_attempts THEN claimed_at
                    ELSE NULL
                END
            WHERE job_id = %s::uuid
              AND state IN ('claimed', 'running', 'pending')
            RETURNING state, attempts
        """
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(sql, (error_text, job_id))
                row = cur.fetchone()
                ok = row is not None
                new_state = row[0] if row else None
                attempts = row[1] if row else None
        logger.info(
            "mark_failed job_id=%s ok=%s new_state=%s attempts=%s",
            job_id, ok, new_state, attempts,
        )
        return ok

    def release(
        self, job_id: str, worker_id: str, conn: Optional[Any] = None
    ) -> bool:
        """Return a job a worker holds back to ``pending`` WITHOUT counting an
        attempt or recording an error.

        Use when a worker claims a job it should not process (e.g. a job that
        belongs to a different dispatch/owner) and wants to hand it back intact
        for its rightful claimant. Distinct from ``mark_failed``, which charges
        an attempt and drives toward ``dead_letter``.
        """
        sql = f"""
            UPDATE {TABLE}
            SET state = 'pending',
                claimed_by = NULL,
                claimed_at = NULL
            WHERE job_id = %s::uuid
              AND state IN ('claimed', 'running')
              AND claimed_by = %s
            RETURNING job_id
        """
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(sql, (job_id, worker_id))
                ok = cur.fetchone() is not None
        logger.info("release job_id=%s worker=%s ok=%s", job_id, worker_id, ok)
        return ok

    # -- reads -------------------------------------------------------------

    def get_job(self, job_id: str, conn: Optional[Any] = None) -> Optional[dict]:
        """Return the full job row as a dict, or ``None`` if not found."""
        with self._connection(conn) as c:
            with self._dict_cursor(c) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} WHERE job_id = %s::uuid", (job_id,)
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def list_dead_letter(self, limit: int = 100, conn: Optional[Any] = None) -> list:
        """Return dead-lettered jobs, most recent failure first."""
        with self._connection(conn) as c:
            with self._dict_cursor(c) as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {TABLE}
                    WHERE state = 'dead_letter'
                    ORDER BY failed_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = [dict(r) for r in cur.fetchall()]
        return rows

    def queue_stats(self, conn: Optional[Any] = None) -> dict:
        """Return a count per state. Every state key is present (zero-filled)."""
        stats = {state: 0 for state in JOB_STATES}
        with self._connection(conn) as c:
            with c.cursor() as cur:
                cur.execute(
                    f"SELECT state, count(*) FROM {TABLE} GROUP BY state"
                )
                for state, count in cur.fetchall():
                    stats[state] = count
        return stats


def new_token_id() -> str:
    """Convenience: generate a fresh UUID string (e.g. a result_token_id)."""
    return str(uuid.uuid4())
