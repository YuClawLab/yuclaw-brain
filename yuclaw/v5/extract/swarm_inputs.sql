-- YUCLAW v5 Layer 1 Day 3 — narrative inputs (isolated schema yuclaw_v5, db yuclaw_events)
-- The swarm's Day-2 grounding collapsed on 10-K/10-Q because events_raw.raw_text is the
-- iXBRL cover (taxonomy URLs), capped at 8000 chars, never reaching MD&A. This table holds
-- the re-fetched + extracted NARRATIVE prose (MD&A / Risk Factors / Business) so agents have
-- quotable source material. ADDITIVE ONLY — events_raw and all public.* are never mutated.
-- Apply with: psql -d yuclaw_events -f yuclaw/v5/extract/swarm_inputs.sql

CREATE SCHEMA IF NOT EXISTS yuclaw_v5;

CREATE TABLE IF NOT EXISTS yuclaw_v5.swarm_inputs (
  input_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  accession_number  TEXT NOT NULL,
  source_type       TEXT,
  source_url        TEXT,
  narrative_text    TEXT NOT NULL,
  narrative_section TEXT,            -- which anchor matched: mdna / risk_factors / business / fallback
  char_len          INT,
  alpha_ratio       REAL,           -- letters / total; prose ~0.7+, XBRL soup ~0.5
  http_count        INT,           -- residual taxonomy-URL count (should be ~0 after extraction)
  full_doc_len      INT,           -- stripped length of the whole primary document
  extracted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (accession_number)
);
