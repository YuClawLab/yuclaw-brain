-- YUCLAW v5 Layer 1 — swarm_outputs (isolated schema yuclaw_v5, db yuclaw_events)
-- Created ad hoc on Day 1; formalised here. Day 2 adds the grounding columns.
-- Apply with: psql -d yuclaw_events -f yuclaw/v5/swarm/swarm_outputs.sql

CREATE SCHEMA IF NOT EXISTS yuclaw_v5;

CREATE TABLE IF NOT EXISTS yuclaw_v5.swarm_outputs (
  swarm_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  accession_number  TEXT NOT NULL,
  prompt_version    TEXT NOT NULL,
  bull_output       JSONB NOT NULL,
  bear_output       JSONB NOT NULL,
  skeptic_output    JSONB NOT NULL,
  synthesis_output  JSONB NOT NULL,
  timings           JSONB NOT NULL,
  model_tags        JSONB NOT NULL,
  agent_job_ids     JSONB,
  synth_job_id      UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (accession_number, prompt_version)
);

-- Day 2 (grounding & citation discipline): per-agent grounding rollup, and the
-- proto evidence token (accession + the union of verified verbatim spans).
ALTER TABLE yuclaw_v5.swarm_outputs ADD COLUMN IF NOT EXISTS grounding_summary JSONB;
ALTER TABLE yuclaw_v5.swarm_outputs ADD COLUMN IF NOT EXISTS citation_ledger   JSONB;
