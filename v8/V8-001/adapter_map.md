# V8-001 §5 — v7 adapter map for the source-to-export workbench

Baseline: v7.0.1 (`696d871e`). Inventory method: read-only search of `v3/`, `v4/`, `tools/`, `schemas/`, `tests/` on the
integration branch; every MISSING entry names the search that came back empty. A mocked screen is not an integration.

| Step | v7 adapter target (reuse) | Status | What is genuinely missing |
|---|---|---|---|
| 1 Source | `schemas/EvidenceObject.v1.json`; `v3/evidence/snapshot.py:snapshot_corpus` (accession_number, filing_date, available_as_of, source_hash); receipts `artifact_binding {artifact_type, sha256, size_bytes}` | ADAPT | no source URL field; no document-level source record on the receipt path (`grep url\|accession v3/receipts/*.py` → 0) |
| 2 Typed claim | `v3/cli/check_claim.py:passport` (`{ticker, type∈16 event types, date_range, accession}`, `support_limits`) | MISSING | no numeric range / currency / fiscal period / basis / availability schema anywhere (`grep currency\|fiscal_period\|range_low\|guidance_range **/*.py` → one comment); check_claim states "no numeric-magnitude checking" |
| 3 Comparison | `v3/receipts/challenge.py:verify_revision`, `scoreboard.history(a, b)` | MISSING | comparison is artifact byte-identity only; no value-vs-value or range-vs-range comparator |
| 4 Calculation | `v3/receipts/counting.py:counts/classify/movement` | MISSING | count/window deltas only; no interval containment, midpoint delta or unit/basis compatibility primitive (`grep in_range\|out_of_range` → 0) |
| 5 History | `Store.import_submission` `supersedes{digest, reason}` + `Store.history`; `ChallengeStore.history`; `registry` hash chain (`tools/yuclaw_protocol_registry.py`) | ADAPT | correction semantics exist for receipts/challenges, not claims; no claim-level REVISED / WITHDRAWN / CORRECTED_SOURCE events |
| 6 Adjudication | `Store.designate_reviewer/authorize/add_review`; `challenge.evaluate/dispose`; `v3/receipts/credentials.py` token handling; `DecisionStore.record` | ADAPT | no CLI `designate`; reviews bind receipt digests, not claim content; no adjudication vocabulary for IN_RANGE / OUT_OF_RANGE / PENDING_OUTCOME / WITHDRAWN_BEFORE_OUTCOME / INCOMPATIBLE_BASIS / UNIT_MISMATCH |
| 7 Reproducible export | `v3/receipts/packet.py:build/verify` (yuclaw-verification-packet/1), `export.project_many`, `scoreboard.canonical_bytes`, `decision.export` | ADAPT | `PERMITTED` is a hard-coded 10-path list; no commitment/comparison artifact is packable; `docs/receipts/` holds only scoreboard + target manifest |

## Persistence contracts to define (missing)
- `commitments.jsonl` append-only store next to the receipts store (same `open("a")` + 0600 + digest-chained records; `E_PUBLIC_TREE` boundary via `v3/receipts/storage.py:resolve_store_root`).
- Claim record identity = `contracts.digest(canonical_json)`; revision/withdrawal/correction records reference the superseded digest, never rewrite it.
- Export = a packet extension: one additional PERMITTED artifact class (`commitments/<claim_id>.json`, public fields only, publication policy + denylist sweep applied as for receipts).

## UI routes (missing entirely)
- `v3/api/server.py` exposes GET routes only (`grep @app.post\|@app.put v3/` → 0); `tools/check_no_forms.py` forbids `<form>` / `<input name>` / uploads in `docs/**/*.html`.
- A browser-driven workbench therefore needs a NEW local surface (a local server outside `docs/`, or a static generator like `v3/web/render_*.py` for read-only steps). Seven visible steps through the browser is the acceptance rule; nothing here counts yet.

## Flags named by the order
`COM`, `PRC`, `SHD`, `EVO` (disabled by default), `CTL`, `RES` (outside 8.0.0): recorded verbatim. Their definitions live in the
scope package, which is absent on this host; no feature-flag registry with these identifiers exists in v7. No product tab is added.
