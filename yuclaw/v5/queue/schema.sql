-- YUCLAW v5 Layer 0 — Evidence Job Queue schema
-- Isolated schema: yuclaw_v5 (NEVER public; v4 lives in public.*)
-- Target database: yuclaw_events (v4's existing Postgres database)
-- Apply with: psql -d yuclaw_events -f yuclaw/v5/queue/schema.sql
--
-- gen_random_uuid() is a core function in PostgreSQL 13+ (server here is 16.x),
-- so no extension is required.

CREATE SCHEMA IF NOT EXISTS yuclaw_v5;

CREATE TABLE IF NOT EXISTS yuclaw_v5.evidence_jobs (
  job_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type         TEXT NOT NULL,
  payload          JSONB NOT NULL,
  state            TEXT NOT NULL DEFAULT 'pending'
                   CHECK (state IN ('pending','claimed','running','succeeded','failed','dead_letter')),
  priority         INT NOT NULL DEFAULT 100,
  attempts         INT NOT NULL DEFAULT 0,
  max_attempts     INT NOT NULL DEFAULT 3,
  claimed_by       TEXT,
  claimed_at       TIMESTAMPTZ,
  available_as_of  TIMESTAMPTZ,
  succeeded_at     TIMESTAMPTZ,
  failed_at        TIMESTAMPTZ,
  result_token_id  UUID,
  parent_job_id    UUID,
  trace_id         TEXT,
  idempotency_key  TEXT UNIQUE,
  last_error       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hot path: claim_next scans pending jobs, highest priority first, FIFO within priority.
-- Partial index keeps it small (only pending rows) and matches the ORDER BY exactly.
CREATE INDEX IF NOT EXISTS idx_jobs_pending
  ON yuclaw_v5.evidence_jobs (state, priority DESC, created_at ASC)
  WHERE state = 'pending';

-- Operational: "what is worker X holding?" — only claimed rows are interesting.
CREATE INDEX IF NOT EXISTS idx_jobs_claimed_by
  ON yuclaw_v5.evidence_jobs (claimed_by)
  WHERE state = 'claimed';

-- Cascade/lineage lookups (child jobs of a parent).
CREATE INDEX IF NOT EXISTS idx_jobs_parent
  ON yuclaw_v5.evidence_jobs (parent_job_id)
  WHERE parent_job_id IS NOT NULL;

-- Dead-letter triage, newest failures first.
CREATE INDEX IF NOT EXISTS idx_jobs_dead_letter
  ON yuclaw_v5.evidence_jobs (failed_at DESC)
  WHERE state = 'dead_letter';
