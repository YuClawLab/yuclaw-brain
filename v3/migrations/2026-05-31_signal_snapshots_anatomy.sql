-- Migration: persist component anatomy + composite_confidence on signal_snapshots (v4 Q5).
-- Replay fidelity over storage savings: store the per-component anatomy so a historical
-- ResearchResponse reconstructs exactly, instead of recomputing (which can drift if
-- component logic changes).
--
-- Nullable for now; existing rows stay NULL (faithful point-in-time anatomy cannot be
-- reconstructed for historical snapshots — see migration.md). A later v4.x can add
-- NOT NULL once every live snapshot carries it.
--
-- Transactional + reversible. Rollback: see the DOWN block at the bottom.

BEGIN;

ALTER TABLE signal_snapshots
    ADD COLUMN component_anatomy   jsonb,   -- {cid: {score, confidence, rationale, evidence_ids}}
    ADD COLUMN composite_confidence real;   -- v3 compose_at composite_confidence [0,1]

COMMENT ON COLUMN signal_snapshots.component_anatomy IS
    'v4: trimmed per-component anatomy (score/confidence/rationale/evidence_ids). '
    'Excludes internal details (impact weights, is_insider). NULL for pre-v4 rows.';
COMMENT ON COLUMN signal_snapshots.composite_confidence IS
    'v4: confidence-weighted composite confidence from compose_at. NULL for pre-v4 rows.';

COMMIT;

-- ---------------------------------------------------------------------------
-- DOWN (rollback), run manually if needed:
--   BEGIN;
--   ALTER TABLE signal_snapshots DROP COLUMN component_anatomy;
--   ALTER TABLE signal_snapshots DROP COLUMN composite_confidence;
--   COMMIT;
