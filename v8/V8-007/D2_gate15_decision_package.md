# D2 — Gate #15 decision package for 8.0.0 (V8-007, 2026-09-16; NO decision recorded)

Supersedes the V8-006 package (`v8/V8-006/D2_gate15_decision_package.md`) with the coherent-candidate results; nothing else changes. Research and education only. Not investment advice.

## Actual status
Gate #15 "user comprehension test passes" is **MANUAL_REVIEW / NOT SATISFIED** on every v8 candidate: V8-003 generator run on `9efdd52d`; V8-006 run on the staged 8.0.0 tree `ca50b42e` (18 GREEN / 1 RED / 1 MANUAL_REVIEW); V8-007 run on the coherent staging `479a5aef` + staging render (**19 GREEN / 1 MANUAL_REVIEW**, gate 15 the only non-GREEN gate). The consumer-posture scaffold (five deterministic stranger personas) is GREEN; the full-form human comprehension study does not exist. No human review or user study has taken place; every adjudication and note in the v8 evidence is an automated simulated test action. Human benefit is **PENDING**. The owner's browser checklist (`owner_ui_checklist.md`) is an owner acceptance walk-through, not a comprehension study, and does not change this status.

## Governing rules (verbatim from `internal/release_v8_0_0/publish_v800.py`)
- `policy_valid`: with gate 15 **GREEN** in the table, the policy must record route **A** with `gate_input = CANDIDATE_GATE_INPUT` and `gate_15_proposed = GREEN`; with gate 15 **MANUAL_REVIEW**, only route **B** with the owner's exception text matching `EXCEPTION_TEMPLATE` verbatim (hash recorded) permits the release; `EXCEPTION_TEMPLATE` is currently `None`, so route B is **closed**: "gate 15 is MANUAL_REVIEW (NOT SATISFIED) and no 8.0.0 Gate #15 exception wording has been issued by the owner; the 7.0.1 exception is not inherited".
- `cmd_policy`: the route is recorded together with D1 in one policy record; route B needs the exception file whose text matches the template; route A needs the accepted gate-input record.
- `cmd_authorize`: refuses when the gate table has any RED entry, when the policy is missing or inconsistent, when the manifest was composed from a different policy record, and when the manifest's `notes.policy_correspondence` is non-empty. On the coherent staging that field is `['not a 7.x release']` (release-tool blocker TB-1 in `gates.json`): even a recorded route does not authorize until the 8.x notes composition path exists.
- The 7.0.1 exception (`internal/release_v7_0_1/release_policy_v7.0.1.json`) is limited to 7.0.1 and is **not inherited**.

## Evidence the owner can weigh
- v7.0.1 precedent: route B with the owner's dated D2 wording.
- Gate #15 kit (`tools/yuclaw_gate15_study.py`): builds participant packets from committed blobs and evaluates reviewer forms deterministically; it never enrols or scores real people; protocol UNADOPTED.
- 8.0.0 adds three functions a comprehension study would have to cover (research notes, dataset coverage, scientific report/replay); the seven-step journey evidence is automated (7/7 on the checkout and on both installed artifacts; the wheel bytes of the coherent candidate were demonstrated 7/7 in the V8-006 rehearsal re-run).

## Options (for the owner; none selected)
1. **Route B — owner-authored 8.0.0 exception.** The owner issues dated wording of the same shape as 7.0.1 but for 8.0.0 only. Draft for the owner to adopt, edit or reject (not adopted here): "I, the owner, accept for the 8.0.0 release only an explicit release-policy exception for Gate #15. The requirement is NOT SATISFIED; the gate remains MANUAL_REVIEW. Disclose this exception verbatim in the release notes and release-state record. No human study is authorized or scheduled. Date YYYY-MM-DD." Obligations after selection: bind the wording as `EXCEPTION_TEMPLATE` in `publish_v800.py` (publisher identity changes → its 21 tests and the mocked rehearsal are re-run and re-recorded), then `policy <D1 file> B <exception file>`, then verbatim disclosure in both notes tiers (needs TB-1 resolved).
2. **Route A — run the study first.** Adopt the Gate #15 protocol, run the kit with real participants, obtain a GREEN gate input; release moves after the study. Obligations: protocol adoption, participants, evaluation, gate-input record, `policy <D1 file> A <gate input>`.
3. **Hold the release** until either route is available; keep the candidate as staged and the evidence as recorded.

## What selecting a route permits and does not permit
- Selecting a route and recording it (with D1) satisfies `policy_valid`. It does **not** set `release_authorized`, does not designate or freeze the candidate, and does not publish anything. Publication authorization is a separate act: the owner's sentence in the `AUTH_TEMPLATE` form naming the frozen sha and tree, accepted only when 0 RED, policy valid, notes correspond and the worktree is clean at that sha/tree.

## What this package does not do
It records no approval, selects no route, writes no policy record, binds no wording and inherits nothing from v7. Gate #15's status in every generated record stays MANUAL_REVIEW.

## Next action after each decision
- **Route B chosen** → owner supplies the dated wording → bind it into the publisher (reviewed change; tests + rehearsal) → resolve TB-1 (reviewed release-tool change) → after designation and freeze: `policy <D1-ACCEPT file> B <wording file>` → regenerate the manifest with `--release-policy` → authorization sentence.
- **Route A chosen** → protocol adoption and study (outside this order's scope) → gate input record → same sequence with `A`.
- **Hold** → nothing further runs; the staging worktree, preliminary pair and records stay as they are; the weekly-note result expires with the next evidence-store change and is re-rendered at the freeze.
