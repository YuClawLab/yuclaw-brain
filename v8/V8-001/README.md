# V8-001 — return package index (local implementation and evidence only)

Recorded 2026-09-15T07:02:22+00:00. Branch `codex/v8-integration` (worktree `~/yuclaw-v8`) from the published v7.0.1 tag commit
`696d871e`; see the private `v8-baseline.json` for the explained lineage and the base assumption.
Nothing in this order pushes, tags, deploys, uploads, edits published assets, or sets `release_authorized`.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

| Deliverable | Where | Status |
|---|---|---|
| §1 Baseline pin (`v8-baseline.json`) | private return dir `internal/v8/v8_001_20260915T064826Z/` | COMPLETE |
| §2 Backup cancellation (`backup-cancellation.json`) | private return dir | COMPLETE for the user scope of this host; root crontab and remote hosts UNVERIFIED |
| §3 Deploy verifier repair | `tools/deploy_verify.py`, `tests/test_deploy_verify.py`; before/after evidence in the private return dir | COMPLETE |
| §4 Download-verification journal (the publisher's `download-proof` stage) | root cause + regression tests `internal/release_v7_0_1/test_download_proof_journal.py` (private, next to the publisher); repair already live in `publish_v701.py` | COMPLETE (evidence); the v8 publisher must carry the repair plus an operation identifier |
| §5 Fixtures | `tests/fixtures/v8/commitments/` (7 files + manifest), `tests/test_v8_commitment_fixtures.py` | COMPLETE |
| §5 Adapter map / persistence / UI routes | `adapter_map.md` | COMPLETE |
| §5 Real-data selection criteria | `real_data_selection_criteria.md` | COMPLETE (criteria only; no issuer selected, no crawler) |
| §5 Logo assets + README picture block | `brand/human-trace-v1/` (the delivered set by exact bytes: three approved PNGs, asset-manifest.json, brand README); `README.md` picture block above the canonical mission/vision block | COMPLETE (recovery 2026-09-15): bytes verified against HANDOFF_MANIFEST.json, asset-manifest.json and v8.0.0-scope.json; README canonical payload unchanged (sha256 c3b3d26ca94f); `YuClaw` lettering inside the images preserved, authored text says YUCLAW |
| §5 Seven-step scorecard | `scorecard.json` | COMPLETE as a record; score 0/7 NOT_DEMONSTRATED |
| §6 Inherited gate mapping | `inherited_gates.json` | COMPLETE; Gate #15 NOT_SATISFIED for v8 (v7 exception is v7-only) |
| Scope index (`V8_0_0_SCOPE_FREEZE.md`, `v8.0.0-scope.json`) | `v8/scope/` (the scope package by exact bytes, 22 files + `HANDOFF_MANIFEST.json`) and `v8/scope/SCOPE_INDEX.json` (reconciliation index: v7.0.1 integration baseline, workstream flags, roadmap 213/20, fixture conformance, gates, brand hashes, milestones) | COMPLETE (recovery 2026-09-15); the private recovery note stays in the staging directory (it names this host) |

Release limitation to disclose in 8.0.0 notes: see `release_limitation.txt` (verbatim).

## Recovery of the two missing inputs (2026-09-15)

The owner's recovery handoff (`V8_001_RECOVERY_HANDOFF.md`, private staging copy; sha256 `77c8a159…cfce95e`) supersedes the
original order's initial-start wording: V8-001 is not rerun, the worktree is not recreated, and the v7.0.1 tag commit stays the
integration baseline while v7.0.0 provenance and all published evidence are preserved. Inputs arrived as
`YUCLAW-V8-001-recovery-inputs.zip` (sha256 `24f9ac73…0514b3`; 30 manifest entries verified by sha256 and byte count; no
unsafe archive members). Owner schedule update: release target Monday 2026-09-21 (Asia/Shanghai), community promotion after the
verified release; Gate B go/no-go 2026-09-19 evening; artifact freeze target 2026-09-20. The `2026-09-22` conditional target in
`scorecard.json` is a dated V8-001 record and is superseded by the addendum. Journey score remains 0/7; Gate #15 remains
NOT_SATISFIED for v8; nothing is pushed, tagged, deployed, uploaded or published.

Finding for the release step: `README.md` is also the PyPI long description, so the relative logo path will not render on PyPI
until the assets are public or a PyPI-specific description exists. Nothing on the live site or PyPI changes now.

## Proposed next bounded order — V8-002 "connect the source-to-export workbench" (for owner approval)
1. DONE in the V8-001 recovery (2026-09-15): scope package transferred and verified against its manifest, approved
   logo assets imported by exact bytes, README picture block prepared; no other V8-002 step has been started.
2. Define `schemas/CommitmentClaim.v1.json` (range, unit, currency, fiscal period, basis, availability) and the
   `commitments.jsonl` append-only store contract (digest-chained; REVISED / WITHDRAWN / CORRECTED_SOURCE events).
3. Implement the comparator/calculator as pure functions with the seven fixtures as the acceptance suite
   (IN_RANGE / OUT_OF_RANGE / PENDING_OUTCOME / WITHDRAWN_BEFORE_OUTCOME / INCOMPATIBLE_BASIS / UNIT_MISMATCH).
4. Add `commitments/<claim_id>.json` to the packet PERMITTED class behind the receipts publication policy.
5. Stand up a LOCAL read-only browser surface for the seven steps (outside `docs/`, `check_no_forms.py` untouched) and
   record the scorecard from a browser session on the integrated candidate; select the one real issuer by the criteria.
6. Draft the v8 publisher as a reviewed copy of `publish_v701.py` with a 7.0.1 preservation tripwire row and an
   operation identifier on the download-verification stage; keep `release_authorized` false. Gate B: 2026-09-19 evening Asia/Shanghai.
