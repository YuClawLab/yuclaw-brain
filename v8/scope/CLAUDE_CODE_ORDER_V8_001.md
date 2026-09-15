# YUCLAW — Claude Code order V8-001

Date: September 15, 2026. Status: prepared for owner handoff; not sent by this task. Type: local implementation and evidence preparation only. This order does not authorize pushing main, tagging, deployment, PyPI uploads, modifying published release assets, sending messages, or community publication.

## Objective and governing scope

Establish a clean v7-based v8 integration workspace, implement the owner's backup cancellation on the actual YUCLAW runtime where accessible, and repair the two publisher defects with regression evidence. Prepare the exact source-to-export acceptance fixtures and adapter inventory for the next implementation order. Do not attempt the entire 213-task roadmap in this order.

Use [V8_0_0_SCOPE_FREEZE.md](V8_0_0_SCOPE_FREEZE.md) as the 8.0.0 scope and [v8.0.0-scope.json](v8.0.0-scope.json) as its machine-readable index. If these documents are not available on the executor host, have the owner transfer this handoff package; do not guess missing requirements or read another host's paths as if they were local.

Mission: **Make financial AI accountable to evidence.**

Vision: **Become the Science Trust Layer for Financial AI.**

Preserve both exact wording and meaning. All newly authored product content must be English. Use `YUCLAW` in new public text. Preserve exact technical identifiers, source attribution, historical records, and the approved Human Trace PNGs, including their `YuClaw` lettering. Do not redesign, regenerate, recolor, or modify the logo.

## 1. Pin and protect the baseline

1. Inspect applicable repository instructions, current branch/status, deployment ownership, and existing release machinery. Record facts without printing credentials or private customer records.
2. Resolve `v7.0.0` again and compare its peeled commit to `6a619b74c46ee6601434e73d25963b5e2e61d59d`. The observed main commit `c2401102579a0e2baea8b664ddbb4cda611db750` is a later evidence commit, not the tag. Stop baseline integration on an unexplained identity mismatch.
3. Use an isolated `codex/` integration branch/check-out from the verified tag. Do not reset, clean, stash away, or overwrite the dirty a6 preview working tree. Review post-tag main differences separately, then carry forward applicable release evidence without changing historical artifacts. Follow the repository DCO policy for any local commits; do not invent a signing identity.
4. Verify the release manifest against the inherited wheel/sdist if using those artifacts. Expected wheel SHA-256: `6cd1164c7ffa744f6f1b876205144ea1bc52ed7b480223cc2bc93b356abe69aa`; expected sdist: `7399a1f1ed50d86b59d2301d3cbd1a5d188547a82b69809e787f2c426035116a`.
5. Map the existing v7 source, receipt, packet, claim-support, challenge, UI, storage and release interfaces. Reuse those with suitable semantics. Preview data structures and commands are candidates for selective integration, not permission to overwrite the v7 implementation.

Required output: `v8-baseline.json` containing actual commits, dirty-work preservation, manifest hashes, inherited interface paths, differences requiring adaptation, and applicable instructions. No live change is needed to produce this record.

## 2. Cancel backup functionality now

This is the owner's direct cancellation, not a deferral until Calgary. Do not create or retain an automatic reactivation trigger.

- Inventory actual YUCLAW backup entry points, configuration, cron/systemd/launchd jobs, cloud schedules and relevant Codex automations on the authorized runtime. Read only the relevant configuration and redact secrets.
- Disable identified YUCLAW backup producers and triggers using the existing service's scoped configuration. For a dedicated backup unit, stop that unit and disable its timer; for a shared scheduler, remove only the matching backup entry. Do not terminate a shared worker that serves other functions.
- Remove backup/restore UI, commands, job registrations, new dependencies and gate requirements from enabled 8.0.0 scope if they exist. Preserve historical code/evidence unless a runtime entry point actually needs to be disconnected. Do not remove receipt export, evidence replay, release verification, or privacy guards that search for leaked copies.
- Preserve all existing data and backup files. No file deletion, retention purge, unrelated infrastructure changes, or rewrite of v7 release evidence is authorized.
- Verify the producer is disabled and cannot be restarted by an identified timer/dependency. Report the inspected host and scheduler, before/after state, producer status, and residual triggers. If no matching runtime exists, record that fact. An inaccessible remote host remains `UNVERIFIED`; continue the remaining authorized work.
- Record the release limitation: `Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery.`

Required output: `backup-cancellation.json` with observed entries, exact scoped changes, verification, untouched data, and any unverified runtime. Local review already found no matching Codex backup automation or user LaunchAgent, and no crontab for `zhang`; this does not establish remote state.

## 3. Repair the deploy verifier

Confirmed v7 source: `tools/deploy_verify.py` requires every body to be at least 1,024 bytes before comparing it with the local build. That rejects genuine short artifacts. The final v7 release target manifest itself is 730 bytes, although that does not prove this particular file traversed the canonical-site verifier during v7 publication.

1. Reproduce the refusal with a deterministic, mocked HTTP 200 response from the canonical origin containing a valid short artifact that matches the expected local bytes. Retain the failing regression evidence before the fix.
2. Make acceptance depend on the frozen expected artifact identity: exact digest and byte length, plus expected content/schema checks where applicable. Retain strict canonical-origin, redirect-chain and HTTP-status checks. A MIME header alone cannot establish authenticity. Reject unknown manifest paths or missing expected artifacts.
3. A generic minimum body size must not reject a valid manifest-matching short artifact. Do not replace the old limit with a blanket allow for all small HTTP 200 bodies. Keep error/redirect bodies from satisfying a successful verification.
4. Test valid short text/JSON, the 1,023/1,024-byte boundary, wrong bytes, truncated bytes, unexpected HTML error content, wrong final origin, redirects including redirect-to-200, non-200 status, and a normal large artifact. Keep checks appropriate to the actual artifact contract; preserve existing CLI behavior where compatible.
5. Update the verifier's misleading documentation and self-test assumptions. Run the existing affected tests and a mocked full verifier run. Real live publication is not part of this order.

Required output: minimal patch, before/after test evidence, artifact contract, and compatibility notes. Do not alter frozen v7 artifacts to make verification pass.

## 4. Diagnose and repair the download-proof journal

Claude reports a TypeError after a journal write. The public v7 source inventory did not locate the actual publisher implementation under obvious publisher/download-proof names. This review has not reproduced that defect or established its root cause.

1. Locate the actual runtime implementation and retrieve a redacted traceback from the v7 event. Record file/function, input shape, and whether the record was durably appended before the exception. Do not fabricate a stack trace or infer the cause from the exception class alone.
2. Reproduce with a temporary journal and mocked download. Fix the actual type/serialization/return-contract fault at its source. Do not catch and suppress all exceptions or falsely return success.
3. Distinguish failed download, checksum failure, append failure, durable append with failed acknowledgment, and completed proof. Validate before writing where possible and reconcile an ambiguous retry with an operation identifier and matching content. Do not append duplicate success records or silently mutate history.
4. Test success, the original failure input, download/hash failure, append failure, and retry after durable append. A permission/serialization failure must remain visible; an unconfirmed outcome must not count as verified. Add concurrency/crash checks only if the actual journal contract requires them.
5. Rehearse the publisher path using temporary outputs and a local/mocked package source. Never upload, replace or delete a real release while reproducing it.

Required output: root-cause evidence and scoped patch with regression results, or a precise `BLOCKED_SOURCE_UNAVAILABLE` record identifying what executor evidence is missing. A missing publisher source does not block independent core fixture work, but this defect remains unresolved on the release path.

## 5. Prepare the next workbench order

- Check in a clearly fictional commitment fixture: original range 110–120 million, revised 105–115 million, comparable actual 112 million, explicit currency/fiscal period/basis/availability dates. Add missing outcome, withdrawal, incompatible basis, unit mismatch, out-of-range outcome and corrected-source variants.
- Document which v7 interfaces will implement the seven visible steps: source, typed claim, comparison, calculation, history, adjudication, reproducible export. Identify genuinely missing adapters, persistence contracts, and UI routes; do not count a mocked screen as a completed integration.
- Define the initial one-issuer real-data selection criteria. Keep fixture validation separate from real-data quality and human benefit. Do not activate a crawler or claim commercial dataset coverage.
- Keep COM/PRC/SHD/EVO disabled by default; experimental packaging is secondary. CTL/RES, full rival/action engines, multi-tenancy, pilot and research extensions are outside 8.0.0. Do not add new product tabs for them.
- Import the approved logo assets by exact bytes into the integration checkout and prepare its README picture block while preserving the v7 README text, mission and vision. Do not copy the older README wholesale. Verify light/dark references and the asset hashes listed in the scope package.
- Produce the seven-step scorecard. A step counts only when demonstrated on the same v7-based integrated candidate through the browser; fixture creation alone scores no journey step.

## 6. Release discipline and return package

Preserve the existing A-6 release authorization mechanism, its actor/type checks, one-build/same-bytes discipline, and tripwires protecting 6.0.x and 7.0.0. Inventory the actual implementation; do not invent a replacement that bypasses a gate. Do not mark release authorization true. Follow-up review of anything later authorized to touch main/PyPI must verify external observed state, not merely the executor's success message.

The published v7 Gate #15 human-study exception is explicitly v7-only. Include an inherited-gate mapping for v8 showing requirement, applicability, evidence and status. Pilot deferral does not silently remove that requirement. Keep a new exception request, if necessary, for the concrete pre-release decision with completed evidence; implementation may proceed now.

Return:

1. Changed-file list and reviewable diff, with local commit IDs only if valid commits were made.
2. Baseline, scope and backup-cancellation records, including precise observation limits.
3. Publisher reproduction/fix evidence and unresolved findings.
4. Fixture manifest, v7 adapter map, approved-brand hash check and seven-step scorecard.
5. Applicable checks actually run, with commands/results and clearly identified checks not run.
6. A proposed next bounded order for connecting the source-to-export workbench.

Use `COMPLETE`, `PARTIAL`, or `BLOCKED` per deliverable and substantiate each status. Human benefit remains `PENDING`; experimental audits remain `EXPERIMENTAL`. Do not equate implementation completion with verified customer demand, independent audit, resistance to every AI attack, or a scientific breakthrough.

September 19 evening, Asia/Shanghai, is the Gate B go/no-go checkpoint. If the seven-step RC cannot be demonstrated, report the missing evidence and revised target explicitly. September 22 is a conditional release/promotion target, not permission to publish. No message to any community or reviewer is authorized by this order.
