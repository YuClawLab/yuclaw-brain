# 9.1.0 — research-audit release, renumbered from the unpublished 9.0.1 candidate (tracked record)

Research and education only. Not investment advice. **9.1.0 is NOT PUBLISHED while this record says so.** The candidate on the
validation branch `codex/research-audit-fixes` carries `release_authorized=false` until the owner's separate authorization stage.

## Owner decisions of 2026-10-15 (recorded verbatim where a tool reads them)

- **Version:** 9.1.0, a **minor release of the existing v9 product**. The `research-export` command adds functionality and
  SourceLock R10 changes prospective evidence admission; the patch definition (defect repairs only) is not widened to fit this release.
  `v9/V9-006/apply_version_surfaces_9.1.0.py` applies the renumbering (release_kind minor; the unpublished `[9.0.1] — 2026-10-14`
  CHANGELOG heading becomes `[9.1.0] — <freeze date>`); the 9.x notes composer composes 9.1.0 as a minor release (`MINOR_OF`),
  `PATCH_OF` is empty, and the release-state generator takes `--minor` with the tracked change list
  `docs/methodology/release_notes_9.1.0_changes.md`.
- **D1 allocation:** accepted for 9.1.0 — the research-audit scope of the 9.0.1 proposal with the classification corrected; the F1–F5
  scope and the inherited capabilities kept; every activation row carried from the accepted 9.0.0 allocation unchanged and INACTIVE;
  human study NOT AUTHORIZED; backups cancelled; no historical event, estimate, registry entry or ledger record rewritten; R10
  prospective from deployment under its registered addendum. The accepted document is private (release record) and is bound to the
  final candidate, artifact pair and publisher identity by the publisher's policy stage. D1 acceptance is not a publication authorization.
- **Gate #15:** the owner's explicit **9.1.0-only** exception, verbatim in `v9/policy/gate15_release_requirement_9.1.0.json`
  (status EXCEPTION_ACCEPTED, gate_result MANUAL_REVIEW, not carried to any later release; no study run, scheduled or recruited).
  The 9.0.0-only record is not read for 9.1.0 and is not authority for it.
- **Gate 4:** ONE execution of the documented production write probe authorized for the final 9.1.0 candidate through the release-state
  generator with `--allow-production-write-probe`; the private release record journals the candidate identity, run identifier, outcome
  and the consumption of that single permission.

## Registered record naming the preparation number

The Science Trust addendum `9a51541430a0` (registry line 83) and its method record `docs/methodology/sourcelock_r10_admission_change_v1.txt`
were registered on 2026-10-14 and name the carrying release "9.0.1" in the addendum's registered name and scope. Registered bytes are
never rewritten: the release that carries R10 is the same candidate, renumbered 9.1.0 by the owner; the applies-from date is the
9.1.0 push-to-main timestamp. The change list and the CHANGELOG state this.

## History

`v9/V9-005/` (the 9.0.1 preparation record and its version tool) is kept unchanged as superseded history; the published 9.0.0
(`c5c86d06`, tag v9.0.0, its records and artifacts) is untouched.
