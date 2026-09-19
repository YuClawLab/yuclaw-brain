# YUCLAW workbench — data dictionary and dataset card

What the workbench stores, what a dataset row and an export contain, and how they may and may not be read.
Research and education only. Not investment advice.

## Dataset card

- **What it is.** A narrow commitments-and-outcomes dataset derived from one local workspace: one row per frozen claim
  (an issuer's stated revenue target range for one fiscal period), with its revisions, corrections, withdrawal, disclosed
  outcome, computed result, reviewer labels, research notes, source references and rights. Schema
  `yuclaw-commitment-dataset/1`.
- **Coverage.** Exactly the claims registered in the workspace — not an issuer universe, not a sample. The packaged
  fixtures are fictional demonstrations. A real-source row observed after its outcome was public is labelled
  RETROSPECTIVE. No eligible real issuer corpus ships with 8.0.0; an empty workspace has empty coverage.
- **Annotation rules.** Every value is entered by the operator from an exact registered passage. Amounts are exact
  decimals in units (never floats); scale as stated is kept beside them. A comparison is computed only when metric,
  currency, unit, accounting basis and fiscal period are identical; otherwise the result is an explicit unresolved code.
  The resolution rule is `RANGE_CONTAINS_ACTUAL` (both bounds inclusive; no tolerance).
- **Corrections.** Nothing is edited in place. A revision, a corrected source, a withdrawal, a superseding outcome, a
  correcting note and a further adjudication are new events; earlier ones remain. Earlier exported snapshots stay
  reproducible; the dataset page names what changed since the last exported snapshot.
- **Quality estimates.** Not available. No inter-annotator agreement, extraction accuracy or coverage estimate has been
  measured. Reviewer labels are attribution, not authenticated identity or independent review.
- **Source restrictions.** `SEC_PUBLIC_FILING` and `FICTIONAL` excerpts may be included in an export.
  `COMPANY_PRESS_RELEASE` and `UNKNOWN` excerpts are withheld: only the reference and the passage digest are exported.
  A digest binds bytes; it does not establish who published them.
- **Prohibited interpretations.** Not a forecast-skill measure, not evidence that revised guidance is more accurate than
  original guidance, not a trading signal, not investment advice, not a validated dataset product, not prospective
  evidence. Original-range and revised-range results are separate and are never combined.

## Events (the journal)

Each line of the workspace log is one event: `seq`, `kind`, `claim_id`, `op_id` (operation identifier: a retry with the
same content is the same event; different content under the same identifier is refused), `payload`, `actor`,
`prev_hash`, `event_hash`, and three times kept apart:

| Time | Meaning |
|---|---|
| `source_available_as_of` | when the cited source became public (EDGAR acceptance time for a filing); drives every as-of view |
| `observed_at` | when this workspace first saw the source (an ingestion's retrieval time, or the registration time) |
| `recorded_at` | the local time of the action itself |

Kinds: `SOURCE_REGISTERED`, `CLAIM_FROZEN`, `CLAIM_REVISED`, `SOURCE_CORRECTED`, `CLAIM_WITHDRAWN`, `OUTCOME_RECORDED`,
`ADJUDICATION_RECORDED`, `RESEARCH_NOTE_RECORDED`, `SCI_REPLAY_RECORDED`, `EXPORT_BUILT`, `PACKET_VERIFIED`, `RECOVERY`,
`SOURCE_AVAILABILITY_CORRECTED`.

**Unreliable or unknown timestamps.** An unknown availability time is never guessed and cannot be registered as
available. An as-of view at cutoff T shows an event only if its source was available at or before T; an as-of view is a
reconstruction from availability times, and is labelled RETROSPECTIVE when every source was first observed after the
latest one became public. All times are UTC (`YYYY-MM-DDTHH:MM:SSZ`); an input with another offset is refused rather
than converted. A registered source is never edited: the same passage registered again is the same source (its first
observation stands), and a differing record under the same identity is refused. A claim that cited the wrong passage is
corrected by a CORRECTED_SOURCE amendment citing a separately registered source; the earlier version stays in the history.

**Correcting a wrong availability time (`SOURCE_AVAILABILITY_CORRECTED`).** A workspace-level event linked to the
registration it refers to; it edits nothing. Payload: `correction_id` (AC1, AC2, …), `source_id`, `accession`,
`source_hash`, `registration_event` (hash of the SOURCE_REGISTERED event), `registered_available_as_of`,
`prior_available_as_of` and `prior_event` (the value it replaces and the event that carried it: the registration, or
the previous correction), `corrected_available_as_of`, `direction` (EARLIER / LATER), `reason`, `evidence_ref` (text;
never fetched), `actor` with `actor_kind` and the attribution sentence (a label, not authenticated identity),
`effect_rule`, and `changes_source` / `changes_claim`, both always false. Its own `source_available_as_of` is null: a
correction has no availability of its own and is placed by `recorded_at`, which the server stamps.

| Time on a corrected source | Where it lives | Ever changed? |
|---|---|---|
| asserted availability, as registered | the SOURCE_REGISTERED event and every claim version citing it | never |
| asserted availability, as corrected | the SOURCE_AVAILABILITY_CORRECTED chain | by a further linked correction only |
| observation by this workspace | `observed_at` of the registration | never |
| recording of the correction | `recorded_at` of the correction event (server clock) | never |

Historical-view rule `EFFECTIVE_FROM_RECORDED_AT/1`: an as-of view whose cutoff is at or after a correction's
`recorded_at` cuts every event citing the source by the corrected availability. A view at an earlier cutoff keeps the
value the record held then and lists the correction as a later correction with what it would change. A later
correction is never presented as known at the cutoff and never makes a source known earlier than the record held it.

Recomputation sits beside the record. `results`, the dataset row's `status`, `computed`, `withdrawal` and `outcome`
fields, and every adjudication stay as recorded. When — and only when — a cited source was corrected, a claim export
gains `source_availability` (`schema` yuclaw-source-availability/1: the rule and its semantics, each source's
registration, corrections and effective availability, the `corrected_view` with the recomputed result and
retrospective status, the full `corrected_results`, and `review` / `needs_review`), and its dataset row gains
`availability_corrections` plus a coverage gap. Review codes: `RESULT_CHANGES`, `RETROSPECTIVE_STATUS_RETAINED` (a
correction never upgrades a retrospective record), `RETROSPECTIVE_UNDER_CORRECTION`, `ADJUDICATION_PREDATES_CORRECTION`,
`AVAILABILITY_AFTER_OBSERVATION`. An adjudication recorded after a correction also carries
`availability_corrected_view` (what the reviewer was shown); the label rule is unchanged. The verifier checks each
correction's links (registration, replaced value, order, no availability of its own) and re-derives the block from the
packed events; an export without a correction has no such block and the bytes it had before, so earlier exports verify
under the schema they recorded. Prohibited interpretation: a corrected availability is an attributed assertion with an
evidence reference, not a verified publisher clock, and never evidence that anything was known earlier.

## Source

`source_id` = `<accession>:<first 16 hex of source_hash>`. Fields: `kind` (filing, press_release, transcript, other),
`form`, `accession` (EDGAR accession, or `PREFIX:publisher:id`), `url`, `filed_at`, `available_as_of`, `excerpt` (the
exact passage, stored and shown as inert text), `source_hash` (SHA-256 of the excerpt bytes), `rights`, `fictional`.

## Claim version (schema `yuclaw-commitment-claim/1`)

`claim_id`, `issuer` {`name`, `ticker`, `cik`}, `metric`, `statement`, `range` {`low`, `high`} in units, `unit`,
`currency` (ISO 4217), `scale_as_stated`, `basis` (GAAP, IFRS, non-GAAP, non-GAAP adjusted, other-stated),
`fiscal_period` {`label`, `type` FY/H/Q/M, `start`, `end`}, `resolution_rule`, `stated_at`, `source`, `fictional`,
`_digest` (SHA-256 of the canonical claim). Versions: `V1` FROZEN, then `R<n>` REVISED or CORRECTED_SOURCE; a withdrawal
is an event, not a version. Every version names the digest it supersedes.

## Outcome (schema `yuclaw-commitment-outcome/1`)

`actual` in units, `unit`, `currency`, `basis`, `metric`, `fiscal_period`, `comparable` (the recorder's declaration — the
calculator re-checks every field regardless), `source`.

## Computed results

`IN_RANGE`, `OUT_OF_RANGE`; unresolved: `PENDING_OUTCOME`, `WITHDRAWN_BEFORE_OUTCOME`, `INCOMPATIBLE_BASIS`,
`UNIT_MISMATCH`, `PERIOD_MISMATCH`, `METRIC_MISMATCH`, `NOT_COMPARABLE_DECLARED`, `UNSUPPORTED_RULE`.
Formula: contains = low ≤ actual ≤ high; midpoint = (low + high) / 2 (exact); delta_vs_midpoint = actual − midpoint;
distance_outside = actual − violated bound (0 inside). Version comparison: `COMPARABLE` with deltas and direction, or
`INCOMPARABLE` with every reason and no delta.

## Dataset row (`/dataset.json`, dataset snapshot export)

`claim_id`, `issuer`, `metric`, `fiscal_period`, `identifiers` (versions, original and current digests), `status`
(`fictional`, `retrospective` and its reason, `eligibility` note and its actor), `original_target`, `revisions`,
`source_corrections`, `withdrawal`, `outcome`, `computed` (result, per-range results, comparison, direction),
`reviewer` (`labels`, `disagreement`), `unresolved_reasons`, `research_notes` (counts, by category, latest),
`sources` (references, availability precision, observation time, rights, whether the excerpt is included),
`rights` (`withheld_excerpts`), `calculation` (rule, formula, limits), `versions`, `coverage_gaps`, `row_digest`.
The snapshot digest covers the workspace identifier, rows, counts, gaps, known omissions and method — never a generation
time; the same records in the same workspace always give the same digest.

## Exports

A claim export and a dataset snapshot export are zip packets with a manifest, canonical JSON content, per-member digests
and verification instructions. The canonical research digest excludes the export identifier and build time. A verifier
(the **Verify an export** page in a fresh workspace, or `python -m v8.workbench verify-export <zip>`: exit 0 SUCCESS,
1 MISMATCH, 3 UNSUPPORTED) reads the archive in memory within fixed bounds, refuses unsafe member names, re-derives every
digest and recomputes every result, note, dataset row and scientific record. A research export is not a publication
(publication eligibility is shown separately and is NOT ELIGIBLE) and not a backup.
