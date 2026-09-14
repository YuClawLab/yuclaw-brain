# Gate #15 comprehension study — REVIEWER SCORING KEY (candidate protocol, UNADOPTED; never given to participants)

Score each task with the checklist below. A task is **PASS** only when (a) the answer was completed within 10 minutes, (b) **every** expected element is present in the participant's own words (paraphrase counts; the reviewer ticks each element), and (c) no critical error appears anywhere in the answer. Any missing element → **FAIL (incomplete)**; any critical error → **FAIL (critical)**; not completed in time → **INCOMPLETE**. Avoiding a listed wrong statement never passes an answer that lacks the expected elements. Record the tick for every element and every critical error in the decision form.

## Task 1 — Check (source of truth: the frozen README transcript; recorded status `SOURCE_MATCHED`, `matched_evidence` 5 objects, `misses` empty)
Expected elements (all required):
- E1.1 The status means the parsed claim elements (ticker NVDA, type INSIDER_SELL) matched stored evidence objects in YUCLAW's corpus (five filings).
- E1.2 It is a statement about coverage of the corpus, not that the claim is true.
- E1.3 It gives no recommendation, direction, expected return or research interpretation (`research_interpretation` is NONE).
Critical errors (any → FAIL):
- C1.1 says the claim is proven true; C1.2 says an UNSUPPORTED status would mean the claim is false; C1.3 reads any buy/sell direction, return or advice from the passport.

## Task 2 — Reproduce (source of truth: `VERIFY.md` and the verify output)
Expected elements (all required):
- E2.1 verify recomputed each listed file's SHA-256 and byte length against the packet manifest before anything else.
- E2.2 it then replayed the frozen Lab bundle and reproduced the published statistics/roots.
- E2.3 SUCCESS is not an outsider receipt, not an independent result, not proof of official origin, not a scientific validation.
Critical errors: C2.1 says SUCCESS is an independent/outsider result; C2.2 says it proves official origin; C2.3 says it validates the research.

## Task 3 — Scoreboard (source of truth: the bound `evidence_scoreboard.html` / `receipts/scoreboard.json`)
Expected elements (all required):
- E3.1 the exact-release count is zero, or the displayed state is PENDING/UNAVAILABLE — stated as such.
- E3.2 the state is displayed, not hidden.
- E3.3 the legacy program entry is prefix-bound and affiliated and does not count as an exact-wheel outsider reproduction.
Critical errors: C3.1 reads a zero/pending/unavailable state as a positive count; C3.2 invents a number; C3.3 counts the legacy entry as an outsider reproduction of the wheel.

## Task 4 — Limits (source of truth: landing page and scoreboard disclaimer)
Expected elements (all required):
- E4.1 no page gives buy/sell direction or expected returns.
- E4.2 the disclaimer states research and education only, not investment advice.
Critical errors: C4.1 believes the site gives investment direction or performance expectations.

## Task 5 — Challenge
Expected elements (all required):
- E5.1 a challenge was recorded (EXECUTION: the `list` output shows `OPEN` and `adverse: true`; TRANSCRIPT: the template is completely filled).
- E5.2 recording changes nothing about the published evidence until a designated reviewer disposes it.
- E5.3 adverse findings remain visible.
Critical errors: C5.1 cannot record a challenge / template incomplete; C5.2 believes recording one changes the evidence or the counts.

## Session outcome
- **PASS**: all five tasks PASS. **FAIL**: any task FAIL or INCOMPLETE (record which). **MISSING**: enrolled, no completed session. **ASSISTED**: any live help during a task (session recorded, reported, counted as non-PASS).
- Formative notes (confusions, wording issues, time per task) are recorded separately and never change a task score.

## Reviewer decision form (private; one per session)
```
{session_code, mode: EXECUTION|TRANSCRIPT, materials_manifest_sha256, wheel_label: REHEARSAL|RC|FINAL|NONE,
 tasks: [{task, completed, minutes, elements: {E*: true|false}, critical: {C*: true|false}, result: PASS|FAIL_INCOMPLETE|FAIL_CRITICAL|INCOMPLETE, note}],
 assistance: NONE|LIVE_HELP, relationship: RELATED-DISCLOSED|UNRELATED, decision: PASS|FAIL|MISSING|ASSISTED, reviewer_role, decided_at}
```
