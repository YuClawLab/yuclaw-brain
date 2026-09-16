# D2 — Gate #15 decision package for 8.0.0 (prepared 2026-09-16; NO decision recorded)

## Actual status
Gate #15 "user comprehension test passes" is **MANUAL_REVIEW / NOT SATISFIED** on every v8 candidate (V8-003 generator run on 9efdd52d; V8-006 run on the staged 8.0.0 tree). The consumer-posture scaffold (five deterministic stranger personas) is GREEN; the full-form human comprehension study does not exist. No human review or user study has taken place; every adjudication and note in the v8 evidence is an automated simulated test action. Human benefit is **PENDING**.

## Governing rule (publish_v800.policy_valid)
- Route A: only when the gate table shows Gate #15 GREEN, with an accepted gate input (`CANDIDATE_GATE_INPUT`, `gate_15_proposed: GREEN`) recorded in the policy — not available: no study was run.
- Route B: only with the owner's own 8.0.0 exception wording, bound verbatim into the publisher (`EXCEPTION_TEMPLATE`, currently `None` = route closed), recorded by hash in the policy record and disclosed verbatim in the release notes and release-state record. The 7.0.1 exception is limited to 7.0.1 and is **not inherited**.
- Without a route, `authorize` refuses; nothing here selects a route.

## Evidence the owner can weigh
- v7.0.1 precedent: route B with the owner's dated D2 wording (internal/release_v7_0_1/release_policy_v7.0.1.json).
- Gate #15 kit (tools/yuclaw_gate15_study.py) exists: it builds participant packets from committed blobs and evaluates reviewer forms deterministically; it never enrols or scores real people; protocol UNADOPTED.
- v8 adds three functions that a comprehension study would have to cover (research notes, dataset coverage, scientific report/replay); the seven-step journey evidence is automated.

## Options (for the owner; none selected)
1. **Route B — owner-authored 8.0.0 exception.** The owner issues dated wording of the same shape as 7.0.1 but for 8.0.0 only, e.g. (draft for the owner to adopt, edit or reject; not adopted here): "I, the owner, accept for the 8.0.0 release only an explicit release-policy exception for Gate #15. The requirement is NOT SATISFIED; the gate remains MANUAL_REVIEW. Disclose this exception verbatim in the release notes and release-state record. No human study is authorized or scheduled. Date YYYY-MM-DD." Obligations: bind the wording into `publish_v800.py` (its identity changes; authorization is recorded after), record `policy … B <file>`, disclose verbatim in both notes tiers.
2. **Route A — run the study first.** Adopt the Gate #15 protocol, run the kit with real participants, obtain a GREEN gate input; release moves after the study. Obligations: protocol adoption, participants, evaluation, gate input record.
3. **Hold the release** until either route is available; keep the candidate frozen and the evidence as recorded.

## What this package does not do
It records no approval, selects no route, writes no policy record and inherits nothing from v7. Gate #15's status in every generated record stays MANUAL_REVIEW.
