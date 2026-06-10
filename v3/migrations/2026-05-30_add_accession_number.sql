-- Migration: add events_raw.accession_number + UNIQUE (dedup key for edgar_poll_v2)
-- Applied 2026-05-30 to the live yuclaw_events DB (280 pre-existing rows backfilled).
-- Idempotent-ish: re-running ADD COLUMN will error if already present; guard as needed.
-- Wrapped in a transaction with a verify-or-abort gate before the UNIQUE constraint.

BEGIN;

ALTER TABLE events_raw ADD COLUMN accession_number text;

-- Backfill from existing source_urls. Both URL shapes embed the 18-digit
-- accession folder: .../Archives/edgar/data/{cik}/{18digits}/...
-- Reformat NNNNNNNNNNNNNNNNNN -> NNNNNNNNNN-NN-NNNNNN.
UPDATE events_raw
SET accession_number =
      substring(s.acc18 from 1 for 10)||'-'||substring(s.acc18 from 11 for 2)||'-'||substring(s.acc18 from 13 for 6)
FROM (
  SELECT raw_id AS rid, (regexp_match(source_url, '/data/[0-9]+/([0-9]{18})/'))[1] AS acc18
  FROM events_raw
) s
WHERE events_raw.raw_id = s.rid AND s.acc18 IS NOT NULL;

-- Verify-or-abort: every row must have a canonical accession before adding UNIQUE.
DO $$
DECLARE bad int;
BEGIN
  SELECT count(*) INTO bad FROM events_raw
   WHERE accession_number IS NULL OR accession_number !~ '^[0-9]{10}-[0-9]{2}-[0-9]{6}$';
  IF bad > 0 THEN
    RAISE EXCEPTION 'ABORT: % rows have missing/invalid accession_number', bad;
  END IF;
END $$;

ALTER TABLE events_raw ADD CONSTRAINT events_raw_accession_key UNIQUE (accession_number);

COMMIT;

-- Result (2026-05-30): UPDATE 280, all valid, UNIQUE constraint added.
-- source_url UNIQUE is retained as a secondary guard.
