# D2 — Gate #15 decision package for 8.0.0 (V8-008, 2026-09-16; NO decision recorded; NO route selected)

> **SUPERSEDED BY OWNER DECISION (2026-09-16, V8-009):** the owner removed the Gate #15 human-comprehension study as a mandatory v8 release requirement. No study, no route A/B selection and no exception statement are required; the publisher records Gate #15 as NOT_REQUIRED bound to `v8/policy/gate15_release_requirement.json` (status REMOVED_BY_OWNER — never PASSED; human benefit PENDING). The options below no longer apply to v8; the text is retained unchanged as the historical record.


Supersedes the V8-007 package with the revised candidate and the TB-1 repair; the rules, options and status are otherwise unchanged. Research and education only. Not investment advice.

## Actual status
Gate #15 "user comprehension test passes" is **MANUAL_REVIEW / NOT SATISFIED** on every v8 candidate, including the revised proposed candidate `3d43089e` (V8-008 run 1 as staged: 18 GREEN / 1 RED weekly note / 1 MANUAL_REVIEW; run 2 with a staging-only render: 19 GREEN / 1 MANUAL_REVIEW). The consumer-posture scaffold (five deterministic stranger personas) is GREEN; the full-form human comprehension study does not exist. No human review or user study has taken place; every adjudication and note in the v8 evidence is an automated simulated test action. Human benefit is **PENDING**. The owner UI checklist is the owner's functional review and does not change this status.

## Governing rules (verbatim from `internal/release_v8_0_0/publish_v800.py`)
- `policy_valid`: "with gate 15 in MANUAL_REVIEW the policy record must carry the SPECIFIC owner exception (route B, verbatim template, hash) or route A with an accepted gate input GREEN. Allocation acceptance (D1) must be recorded and bound to the allocation document by id + sha256." With gate 15 MANUAL_REVIEW and no bound wording the stage returns: "gate 15 is MANUAL_REVIEW (NOT SATISFIED) and no 8.0.0 Gate #15 exception wording has been issued by the owner; the 7.0.1 exception is not inherited". `EXCEPTION_TEMPLATE` is `None` in the shipped publisher: route B is **closed** until the owner's wording is bound.
- `cmd_policy`: records D1 and the route together: `policy <allocation file> B <exception file>` or `policy <allocation file> A <gate input file>`; "a generic 'go' or source sentence never selects the exception"; an activation marked other than INACTIVE needs an activation record.
- `cmd_authorize`: refuses with any RED gate ("gate table has RED entries"), an invalid policy, a manifest composed from a different policy record, or a non-empty `notes.policy_correspondence` ("public notes do not correspond to the policy record"). After the TB-1 repair the 8.0.0 composer runs and, with no policy recorded, reports `['no release-policy record']` — the honest blocking value until D1 + D2 exist.
- The 8.0.0 composer (`tools/yuclaw_release_notes_v8.py`) discloses the route verbatim: route B quotes the owner's exception text and states "NOT SATISFIED"; route A states the accepted gate input; a PROPOSED allocation or a route without its record never corresponds.

## Route A — actual requirements
1. Adopt the Gate #15 protocol and run the study kit (`tools/yuclaw_gate15_study.py`) with real participants (recruitment needs its own explicit authorization; none exists).
2. Obtain the accepted gate-input record: `gate_input = CANDIDATE_GATE_INPUT`, `gate_15_proposed = GREEN`, with coverage of the materials manifest and the wheel it covers.
3. The generator's gate table must then show Gate #15 GREEN; `policy <D1-ACCEPT file> A <gate input file>` records D1 + D2.
4. Disclosure in both notes tiers: "accepted gate input CANDIDATE_GATE_INPUT proposing GREEN; covers materials manifest …/wheel … only".

## Route B — actual requirements and disclosures
1. The owner issues dated wording for 8.0.0 only, of the same shape as 7.0.1 (the 7.0.1 text is **not inherited** and is refused by the publisher). This package does not draft it as the owner's statement; a shape reference is in `v8/V8-007/D2_gate15_decision_package.md`.
2. The wording is bound verbatim as `EXCEPTION_TEMPLATE` in the publisher (a reviewed change; the publisher identity changes, so its tests and the mocked rehearsal are re-run and re-recorded).
3. `policy <D1-ACCEPT file> B <wording file>` records D1 + D2 with the text and its hash.
4. Disclosure in both notes tiers and the release-state record, verbatim, with "Gate #15 (user comprehension test passes): NOT SATISFIED; released under the owner's explicit release-policy exception". The gate stays MANUAL_REVIEW and is not waived.

## Hold
No route is recorded; nothing further runs; the candidate stays staged, the evidence stays as recorded, `release_authorized` stays false. Hold means hold: no rendering of the notes as final, no designation by implication.

## What a recorded route permits and does not permit
It satisfies `policy_valid` (with D1). It does **not** set `release_authorized`, does not designate or freeze the candidate, does not clear gate 14 (the freeze-day weekly-note render) and does not publish anything. Publication authorization is the separate owner sentence for the FROZEN sha/tree, accepted only with 0 RED, a valid policy, corresponding notes and a clean worktree.

## Next action after each decision
- **Route B** → owner supplies the dated wording → bind into the publisher (reviewed change; tests + rehearsal re-recorded) → designation and freeze → `policy … B …` → regenerate the manifest with `--release-policy` → authorization sentence.
- **Route A** → protocol adoption and study (outside this order) → gate input record → designation and freeze → `policy … A …` → same sequence.
- **Hold** → nothing further; the staging worktree, preliminary pair and records stay; the weekly-note result expires with the next evidence-store change.
