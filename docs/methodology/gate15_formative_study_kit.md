# Gate #15 — Formative comprehension study kit (v7 candidate, version-bound)

**Status: kit only. Gate #15 remains MANUAL_REVIEW.** Five enrolments, a scaffold pass, or this document cannot turn the gate green. Turning it green requires (a) a documented privacy/ethics applicability determination, (b) an authorized protocol and a designated reviewer, (c) actual eligible humans, (d) observed scores under the rubric below, and (e) the release-policy actor who may change the gate value — none of which exist at the time of this kit (V7-004 §5; fact packet §5.6).

Registered sentence (master plan Phase 13): "user comprehension test passes". Deterministic scaffold: `tools/check_consumer_posture.py` (five personas) — its docstring states the human study does not exist.

## Version binding
This kit binds to one exact candidate: the release tag and source SHA are written into every session record; a session against a different artifact is a different study. Materials to hand a participant: the offline verification packet (`yuclaw packet build`), the public site at the candidate's commit, and the README quickstart.

## Eligibility (candidate rules — owner decision pending)
- 5 participants; none owner-affiliated; each declares relationship (RELATED-DISCLOSED / UNRELATED) and receives no outcome-dependent incentive.
- Adults able to read English technical documentation; no prior YUCLAW authorship; no requirement of finance expertise (the population the gate targets is "strangers").
- Missing session: recorded as MISSING, never replaced silently; the study reports n_completed / n_enrolled.

## Task script (each task ≤ 10 min; participant works alone unless assistance is disclosed)
1. **Check**: "Using only the site or CLI, determine whether the corpus supports this claim: *[claim text]*. State what the passport establishes and what it does not."
2. **Reproduce**: "Run `yuclaw packet verify <dir>` on the packet you were given. What did it verify? What did it not establish?"
3. **Read the scoreboard**: "How many outsider reproductions have been verified for the exact 7.0.0 wheel? Is that number zero, pending, or hidden?"
4. **Limits**: "Does any page tell you whether to buy or sell? What does the disclaimer say the evidence is for?"
5. **Challenge**: "Record a challenge for something you believe is wrong or unclear, using the CLI or the issue template."

## Critical-error rubric (any critical error = the session fails the task)
| task | critical error |
|---|---|
| Check | states that an UNSUPPORTED passport means the claim is false, or that a match means the claim is true |
| Reproduce | states that a SUCCESS verify is an independent/outsider result, or a scientific validation |
| Scoreboard | reads a zero/pending state as a positive count, or invents a number |
| Limits | believes the site gives investment direction or performance expectations |
| Challenge | cannot record a challenge, or believes recording one changes the evidence |
Non-critical observations (confusions, time-outs, wording issues) are recorded verbatim and fed to documentation fixes, not scored.

## Assistance rules
No help during tasks. A documented fallback (e.g. the packet's VERIFY.md) may be read. Any live help is recorded as ASSISTED and the task is excluded from the primary tally.

## Consent and disclosure choices (owner/ethics decision)
- Option A — no personal data retained beyond a session code and the recorded task outcomes; no recording.
- Option B — screen recording with explicit consent, deleted after scoring.
- Either way: no names in any public artifact; participants may withdraw; the study's purpose (comprehension of a research tool, not evaluation of the person) is stated up front.

## Reviewer decision form (per session)
`{session_code, artifact: {tag, source_sha}, tasks: [{task, completed, critical_error, notes}], assistance, relationship, decision: PASS|FAIL|MISSING, reviewer_role, decided_at}` — stored privately; only aggregate counts are published.

## Pass condition (candidate; owner decision)
≥ 4 of 5 completed sessions with zero critical errors on tasks 1–4. Reported publicly as n/N with the artifact identity; failures and MISSING sessions are published, never dropped.
