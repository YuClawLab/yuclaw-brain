# 9.0.1 — research-audit corrective release (tracked record)

Research and education only. Not investment advice. **9.0.1 is NOT PUBLISHED.** This record describes a release CANDIDATE on the
validation branch `codex/research-audit-fixes`: `release_authorized=false`; any allocation for it is a new PROPOSED document; the 9.0.0
acceptance, the 9.0.0 authorization and the 9.0.0-only Gate #15 exception belong to 9.0.0 only and transfer to nothing. Gate #15 for
9.0.1 has NO owner decision yet (MANUAL_REVIEW; never PASSED); human benefit PENDING; owner walkthrough NOT_PERFORMED_OPTIONAL; no
independent security review is claimed; no human study was run, scheduled, recruited or proposed; backups remain cancelled.

## What this candidate is

- **Imported patch (the Mac handoff, verified):** commit `bd72179787fb56b7ee1907eed727cd4037f519ed` (tree `90237428…`, base `478c50ce…` =
  the published 9.0.0 evidence overlay), received as a Git bundle (`git bundle verify` OK, SHA256SUMS 49/49 OK) and fetched without
  force into `refs/handoff/research-audit-fixes`; 222 files: replay validation bound to its inputs, point-in-time exports, event-hash
  scope, earnings-comparison support checks, count denominators, composite anatomy, public prose, packet limitations, bilingual
  onboarding, real mobile/keyboard behaviour, tests and the validation-only branch trigger.
- **Spark integration (2026-10-14):** `origin/main` `3cef690f` (the nightly page refresh of 2026-10-13 23:00 UTC) merged into the branch;
  the 15 generated-page conflicts were resolved by taking main's newer pages and then regenerating every current surface through its
  normal generator on this tree against the research database in a session that cannot write (`PGOPTIONS default_transaction_read_only=on`;
  a CREATE TABLE probe was refused), followed by `tools/stage_research_corrections.py` (a repeated pass changes nothing) and the
  nightly gate battery (every gate GREEN; gate 4's production write probe NOT RUN — it needs the owner's per-run authorization).
- **Version surfaces:** `v9/V9-005/apply_version_surfaces_9.0.1.py` (release_kind patch; the `[Unreleased]` CHANGELOG entry became
  `[9.0.1] — 2026-10-14`; README transcript regenerated from a wheel of this tree in the one transcript environment; previews and research
  contracts restaged; G2 GREEN: 9.0.1 on 10 surfaces + 99 badge pages). Candidate SOURCE commit (last commit touching a packaged path): the verifier-arithmetic commit that follows the first record commit
  (the private record names it; `v3/lab/replay_check.py` is packaged). The commit that adds this record text changes no packaged path.

## Changes beyond the supplied patch, and why

| Change | Why |
|---|---|
| `v3/web/render_why_json.py`: `write_ledger_days()` leaves an existing `docs/ledger/{DATE}.json` byte-for-byte unchanged when its date, root and entries are unchanged; only new or changed days are written (`tests/test_ledger_day_preservation.py`) | the patched generator rewrote all 105 published day files with a corrected verify sentence; entries and roots were unchanged, but published day files are externally pinned by file hash (`replay-lab --require-external-ledger` takes an independently obtained ledger and its SHA-256), so a prose-only rewrite would break every external pin |
| `cron/refresh_v3_pages.sh`: the research-corrections staging moved after the weekly note (still before every gate) | the nightly wrote the weekly note AFTER the staging, so that page would ship without its responsive table regions and a second staging pass changed it; `check_weekly_note --require-contract v3` passes on the staged note |
| `docs/methodology/sourcelock_r10_admission_change_v1.txt` + registry addendum `9a51541430a0` under SCIENCE TRUST PROTOCOL v1 (`be8b34040c2e`); derived discovery ledger, anytime record and research state rebuilt; a bilingual note on `docs/research_start.html` | the order requires the prospective R10 admission change to be documented and registered under the existing process before it can affect new evidence; applies from the 9.0.1 deployment date; lexical and structural, not entailment; no historical event reclassified |
| `tools/yuclaw_release_notes_v9.py`, `tools/yuclaw_release_state_v6.py`, tests, `docs/methodology/release_notes_9.0.1_changes.md` | the 9.x composer refused any version but 9.0.0; 9.0.1 now composes as a corrective PATCH of 9.0.0 with a tracked change list, and Gate #15 binds to a decision record for exactly the released version (`v9/policy/gate15_release_requirement_<version>.json`) — the 9.0.0-only exception is never read for 9.0.1 |
| `tests/test_research_audit_fixes.py`: the replay-schema identity cases stated on an explicit legacy shape; a live lab-replay/2 drop test added | the Mac test assumed a schema-less tree bundle; after the live export the tree carries a lab-replay/2 bundle |
| `docs/evidence_changes/2026-09-02.json` removed | the generator's own 30-day archive window (the nightly would prune it the same night); no archive file was edited |
| `v3/lab/replay_check.py` + its standalone mirror `tools/replay_lab.py`: floating-point sums via `math.fsum`; p-values printed at six significant digits | the publisher's complete verification rehearsal STOPPED on the declared minimum runtime: the README transcript's full-precision statistics (introduced by the patch) differed in the last digits between Python 3.10 and 3.12 because the builtin sum changed its algorithm in 3.12; correctly rounded sums print identically on every supported runtime, and the last bits of `math.lgamma` differ between interpreter builds so p-values (through the incomplete beta) are displayed at the verification tolerance; the producer's values are compared within tolerance, never bit for bit |
| `tools/yuclaw_release_state_v6.py` gate 5: a registered append to the protocol chain (base bytes a byte prefix of the candidate chain, chain verified) is accepted; any edited, reordered or removed historical byte still fails (`tests/test_release_state_gate5_append_only.py`) | the gate was coded as byte-identity to base main and reported the appended R10 addendum — the registry's documented append-only process — as a rewrite |

Registry, ledger (entries and roots), bundle, packet and archive bytes are preserved; the hash-bound packet correction
(`docs/packets/corrections.json`, applies to the packet of base `478c50ce`) keeps its original target and is never retargeted.

## Linux validation (Spark, aarch64, Landlock backend available)

On the candidate source (Python 3.12, real private publication denylist, compliance tests on a disposable PostgreSQL 16 node seeded like
hosted CI): 574 passed, 1 skipped (the browser Explorer test, run separately: 3 passed with Playwright 1.62.0), 1 failed — the schema
test above, repaired as a test-only change. Python 3.10 floor selection (v8 workbench, modules on the real restricted worker,
transcript exactness, research-audit, ledger preservation): 254 passed, 1 failed (the same test, before its repair). The 25 Mac
"baseline platform failures" (isolation backend, /proc, resources) do not reproduce on Linux: the v8 module suites pass on the Landlock
worker. The final runs on the frozen commit, the viewport gate, the consumer checks, the clean-install pair, the artifact exercise with
its three tampering controls and the hosted CI run are recorded in the private record `~/yuclaw/internal/release_v9_0_1/`.

## Owner decisions still required (nothing here presumes them)

1. D1 on the PROPOSED allocation (`D1_allocation_9.0.1_P1.json`, private record) — including the version class (corrective patch
   9.0.1, the project's established x.0.1 route, although this patch carries one registered prospective admission rule).
2. A Gate #15 decision record for 9.0.1 in the tree (`v9/policy/gate15_release_requirement_9.0.1.json`, same shape as the 9.0.0 record,
   `applies_to.versions == "9.0.1 only"`) — or another instruction; the 9.0.0-only exception is not carried and no study is proposed.
3. The publication authorization sentence, in the owner's own message, naming exactly the final frozen commit and tree (UNISSUED).

## Remaining scientific limitations (unchanged by software tests)

Missing historical external anchors, unrecorded historical confidence inputs, the absence of independent event-level authentication and
limited empirical reliability evidence are disclosed, not repaired. This candidate establishes no predictive alpha, no causal
identification, no broad agent reliability and no human comprehension; ETF assignment still requires its registered addendum.

## Superseded on 2026-10-15

The owner renumbered this never-published candidate **9.1.0** (a minor release of the 9.0 line: `research-export` adds functionality;
SourceLock R10 changes prospective admission). This record is kept unchanged as history; the current record is `v9/V9-006/README.md`.
