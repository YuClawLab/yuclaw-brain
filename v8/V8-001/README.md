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
| §5 Logo assets + README picture block | — | BLOCKED_SCOPE_PACKAGE_ABSENT (no approved assets or hash list on this host; logo untouched) |
| §5 Seven-step scorecard | `scorecard.json` | COMPLETE as a record; score 0/7 NOT_DEMONSTRATED |
| §6 Inherited gate mapping | `inherited_gates.json` | COMPLETE; Gate #15 NOT_SATISFIED for v8 (v7 exception is v7-only) |
| Scope index (`V8_0_0_SCOPE_FREEZE.md`, `v8.0.0-scope.json`) | — | BLOCKED_SCOPE_PACKAGE_ABSENT — owner transfer required; nothing guessed |

Release limitation to disclose in 8.0.0 notes: see `release_limitation.txt` (verbatim).

## Proposed next bounded order — V8-002 "connect the source-to-export workbench" (for owner approval)
1. Transfer the scope package to this host; verify the approved logo asset hashes; then (and only then) import the
   assets by exact bytes and prepare the README picture block under the existing README text.
2. Define `schemas/CommitmentClaim.v1.json` (range, unit, currency, fiscal period, basis, availability) and the
   `commitments.jsonl` append-only store contract (digest-chained; REVISED / WITHDRAWN / CORRECTED_SOURCE events).
3. Implement the comparator/calculator as pure functions with the seven fixtures as the acceptance suite
   (IN_RANGE / OUT_OF_RANGE / PENDING_OUTCOME / WITHDRAWN_BEFORE_OUTCOME / INCOMPATIBLE_BASIS / UNIT_MISMATCH).
4. Add `commitments/<claim_id>.json` to the packet PERMITTED class behind the receipts publication policy.
5. Stand up a LOCAL read-only browser surface for the seven steps (outside `docs/`, `check_no_forms.py` untouched) and
   record the scorecard from a browser session on the integrated candidate; select the one real issuer by the criteria.
6. Draft the v8 publisher as a reviewed copy of `publish_v701.py` with a 7.0.1 preservation tripwire row and an
   operation identifier on the download-verification stage; keep `release_authorized` false. Gate B: 2026-09-19 evening Asia/Shanghai.
