"""Unit tests for the v5 Evidence Job Queue (yuclaw_v5 schema, live Postgres).

Isolation strategy: every test tags its jobs with a process-unique ``job_type``
prefix (``RUN``) and, where relevant, idempotency keys under that prefix. The
session-scoped ``q`` fixture deletes every row created under this RUN on
teardown, so concurrent/repeated test runs never collide and never touch
pre-existing rows. Each test also filters ``claim_next`` by its own job_type,
so a test only ever sees the jobs it created.
"""

from __future__ import annotations

import threading
import uuid

import psycopg2
import pytest

from yuclaw.v5.queue.core import EvidenceJobQueue, new_token_id

# Process-unique prefix so parallel/repeated runs never collide.
RUN = "test_" + uuid.uuid4().hex[:10]


def jt(name: str) -> str:
    """Build a RUN-scoped job_type."""
    return f"{RUN}_{name}"


def idem(name: str) -> str:
    """Build a RUN-scoped idempotency key."""
    return f"{RUN}:{name}:{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="session")
def q():
    queue = EvidenceJobQueue()
    yield queue
    # Teardown: remove everything this run created, then close the pool.
    cn = psycopg2.connect(queue.dsn)
    try:
        with cn, cn.cursor() as cur:
            cur.execute(
                "DELETE FROM yuclaw_v5.evidence_jobs WHERE job_type LIKE %s",
                (RUN + "%",),
            )
    finally:
        cn.close()
    queue.close()


def test_enqueue_returns_job_id(q):
    job_id = q.enqueue(jt("enqueue_basic"), {"k": "v"})
    assert job_id
    # Valid UUID string.
    assert uuid.UUID(job_id)
    row = q.get_job(job_id)
    assert row["state"] == "pending"
    assert row["payload"] == {"k": "v"}
    assert row["priority"] == 100
    assert row["attempts"] == 0


def test_enqueue_idempotent(q):
    key = idem("idem")
    first = q.enqueue(jt("idem"), {"n": 1}, idempotency_key=key)
    second = q.enqueue(jt("idem"), {"n": 2}, idempotency_key=key)
    assert first == second
    # Exactly one row exists for that key.
    stats_before_type = q.queue_stats()  # smoke that stats still works
    assert stats_before_type is not None
    cn = psycopg2.connect(q.dsn)
    try:
        with cn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM yuclaw_v5.evidence_jobs WHERE idempotency_key=%s",
                (key,),
            )
            assert cur.fetchone()[0] == 1
            # First write wins: payload stays {"n": 1}.
            cur.execute(
                "SELECT payload FROM yuclaw_v5.evidence_jobs WHERE idempotency_key=%s",
                (key,),
            )
            assert cur.fetchone()[0] == {"n": 1}
    finally:
        cn.close()


def test_claim_next_basic(q):
    job_id = q.enqueue(jt("claim_basic"), {"doc": 1})
    claimed = q.claim_next("worker-A", job_types=[jt("claim_basic")])
    assert len(claimed) == 1
    job = claimed[0]
    assert str(job["job_id"]) == job_id
    assert job["state"] == "claimed"
    assert job["claimed_by"] == "worker-A"
    assert job["claimed_at"] is not None
    # No more pending jobs of this type.
    assert q.claim_next("worker-A", job_types=[jt("claim_basic")]) == []


def test_claim_next_skip_locked(q):
    """Two workers polling concurrently must never double-claim a job."""
    n_jobs = 6
    job_type = jt("skip_locked")
    enqueued = {q.enqueue(job_type, {"i": i}) for i in range(n_jobs)}

    results: dict[str, list] = {"w1": [], "w2": []}
    start = threading.Barrier(2)

    def grab(label):
        start.wait()
        # Each worker repeatedly claims one job until the queue is drained.
        while True:
            got = q.claim_next(f"worker-{label}", job_types=[job_type], batch_size=1)
            if not got:
                break
            results[label].append(str(got[0]["job_id"]))

    t1 = threading.Thread(target=grab, args=("w1",))
    t2 = threading.Thread(target=grab, args=("w2",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    all_claimed = results["w1"] + results["w2"]
    # No duplicates across workers, and every enqueued job claimed exactly once.
    assert len(all_claimed) == n_jobs
    assert set(all_claimed) == enqueued
    assert len(set(all_claimed)) == n_jobs


def test_claim_next_priority_order(q):
    job_type = jt("priority")
    # Enqueue low priority FIRST, high priority SECOND — order must be by
    # priority DESC, not insertion order.
    low = q.enqueue(job_type, {"p": "low"}, priority=10)
    high = q.enqueue(job_type, {"p": "high"}, priority=900)
    first = q.claim_next("worker-P", job_types=[job_type], batch_size=1)
    assert str(first[0]["job_id"]) == high
    second = q.claim_next("worker-P", job_types=[job_type], batch_size=1)
    assert str(second[0]["job_id"]) == low


def test_mark_succeeded(q):
    job_id = q.enqueue(jt("succeed"), {"x": 1})
    q.claim_next("worker-S", job_types=[jt("succeed")])
    token = new_token_id()
    assert q.mark_succeeded(job_id, token) is True
    row = q.get_job(job_id)
    assert row["state"] == "succeeded"
    assert row["succeeded_at"] is not None
    assert str(row["result_token_id"]) == token


def test_mark_failed_retries(q):
    job_type = jt("fail")
    job_id = q.enqueue(job_type, {"y": 1}, max_attempts=2)

    # Attempt 1 -> still under max_attempts -> back to pending, claim released.
    q.claim_next("worker-F", job_types=[job_type])
    assert q.mark_failed(job_id, "boom #1") is True
    row = q.get_job(job_id)
    assert row["state"] == "pending"
    assert row["attempts"] == 1
    assert row["claimed_by"] is None
    assert row["last_error"] == "boom #1"

    # Attempt 2 -> reaches max_attempts -> dead_letter.
    q.claim_next("worker-F", job_types=[job_type])
    assert q.mark_failed(job_id, "boom #2") is True
    row = q.get_job(job_id)
    assert row["state"] == "dead_letter"
    assert row["attempts"] == 2
    assert row["last_error"] == "boom #2"
    assert row["failed_at"] is not None

    # And it shows up in the dead-letter list.
    dl_ids = {str(r["job_id"]) for r in q.list_dead_letter()}
    assert job_id in dl_ids


def test_release_returns_job_intact(q):
    """release() hands a claimed job back to pending WITHOUT charging an attempt
    (unlike mark_failed), and only the holding worker may release it."""
    job_type = jt("release")
    job_id = q.enqueue(job_type, {"z": 1})
    claimed = q.claim_next("worker-R1", job_types=[job_type])
    assert claimed and claimed[0]["claimed_by"] == "worker-R1"

    # A different worker cannot release someone else's job.
    assert q.release(job_id, "worker-OTHER") is False
    assert q.get_job(job_id)["state"] == "claimed"

    # The holder releases it: back to pending, no attempt charged, no error.
    assert q.release(job_id, "worker-R1") is True
    row = q.get_job(job_id)
    assert row["state"] == "pending"
    assert row["attempts"] == 0          # NOT incremented (cf. mark_failed)
    assert row["claimed_by"] is None
    assert row["claimed_at"] is None
    assert row["last_error"] is None

    # And it is immediately re-claimable by anyone.
    reclaimed = q.claim_next("worker-R2", job_types=[job_type])
    assert reclaimed and str(reclaimed[0]["job_id"]) == job_id


def test_available_as_of_recorded_at_claim_time(q):
    job_type = jt("avail")
    # Case 1: no available_as_of at enqueue -> stamped at claim time.
    j1 = q.enqueue(job_type, {"a": 1})
    assert q.get_job(j1)["available_as_of"] is None
    claimed1 = q.claim_next("worker-AV", job_types=[job_type], batch_size=1)
    assert claimed1[0]["available_as_of"] is not None
    # The stamped value equals claimed_at (COALESCE(NULL, now())).
    assert claimed1[0]["available_as_of"] == claimed1[0]["claimed_at"]

    # Case 2: explicit available_as_of at enqueue -> preserved through claim.
    import datetime as _dt
    explicit = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)
    j2 = q.enqueue(job_type, {"a": 2}, available_as_of=explicit)
    claimed2 = q.claim_next("worker-AV", job_types=[job_type], batch_size=1)
    assert claimed2[0]["available_as_of"] == explicit


def test_parent_child_relationship(q):
    parent_id = q.enqueue(jt("parent"), {"role": "parent"})
    child_id = q.enqueue(jt("child"), {"role": "child"}, parent_job_id=parent_id)
    child = q.get_job(child_id)
    assert str(child["parent_job_id"]) == parent_id
    # Lookup children of the parent via the indexed column.
    cn = psycopg2.connect(q.dsn)
    try:
        with cn.cursor() as cur:
            cur.execute(
                "SELECT job_id FROM yuclaw_v5.evidence_jobs WHERE parent_job_id=%s::uuid",
                (parent_id,),
            )
            kids = {str(r[0]) for r in cur.fetchall()}
    finally:
        cn.close()
    assert child_id in kids


def test_queue_stats(q):
    stats = q.queue_stats()
    # Every state key present, all non-negative ints.
    assert set(stats.keys()) == {
        "pending", "claimed", "running", "succeeded", "failed", "dead_letter",
    }
    assert all(isinstance(v, int) and v >= 0 for v in stats.values())
