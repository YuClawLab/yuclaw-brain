-- YUCLAW v5 Layer 1 Day 5A — corrected event-type layer (additive, isolated schema).
-- The v4 extractor mis-tags some events (e.g. a $5B credit facility tagged M_AND_A_ANNOUNCE;
-- earnings/financings dumped into OTHER_MATERIAL). This table holds a DETERMINISTIC,
-- SourceLock-backed re-classification. public.events is NEVER mutated; the original v4 tag is
-- kept alongside the corrected one for audit. A corrected tag is only written when a verbatim
-- signature phrase is found in the filing text (source_span) — no unsupported re-tags.
-- Apply with: psql -d yuclaw_events -f yuclaw/v5/extract/event_type_corrected.sql

CREATE SCHEMA IF NOT EXISTS yuclaw_v5;

CREATE TABLE IF NOT EXISTS yuclaw_v5.event_type_corrected (
  event_id            TEXT PRIMARY KEY,
  accession_number    TEXT,
  ticker              TEXT,
  v4_event_type       TEXT NOT NULL,        -- the original public.events tag (audit)
  corrected_event_type TEXT NOT NULL,       -- deterministic re-classification
  changed             BOOLEAN NOT NULL,     -- corrected != v4
  match_signature     TEXT,                 -- which rule fired
  source_span         TEXT,                 -- VERBATIM span from the filing (SourceLock)
  source_start        INT,
  method              TEXT NOT NULL DEFAULT 'rules',
  corrected_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
