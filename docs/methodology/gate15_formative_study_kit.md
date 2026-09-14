# Gate #15 — Formative comprehension study: CANDIDATE PROTOCOL (v7, version-bound, UNADOPTED)

**Status: candidate protocol only. Gate #15 remains MANUAL_REVIEW on current evidence.** It is MANUAL_REVIEW because no authorized human study exists — not because a rule forbids a future, authorized, evidence-based change. Turning it green requires (a) a documented privacy/ethics applicability determination, (b) this protocol (or an amended one) adopted by the owner with a designated study reviewer, (c) actual eligible humans, (d) observed scores under the rubric below, and (e) the release-policy actor who may change the gate value. None of these exist at the time of this document. Prior 6.0.x authorizations with the gate in MANUAL_REVIEW are historical records; they create no v7 release exception. No session, outreach, consent adoption or reviewer designation happens by publishing this document.

Registered sentence (master plan Phase 13): "user comprehension test passes". Deterministic scaffold: `tools/check_consumer_posture.py` (five personas) — its docstring states the human study does not exist.

## 1. Version binding (hashes, not names)
Every session record binds the exact materials by SHA-256 + byte length and the source identity of the checkout they came from. The binding list is generated, never typed: `docs/methodology/gate15_materials_manifest.json` (written by `python3 tools/yuclaw_gate15_materials.py --write`, optionally `--wheel <file> --wheel-label REHEARSAL|RC|FINAL --packet <dir>`). It carries, per material, `path`, `sha256`, `size_bytes`, `source_head`, `source_tree` and, for the wheel, its label. Materials:

| material | role in the study |
|---|---|
| this document (task script + rubric + scoring key) | what the reviewer scores against |
| `README.md` (contains the frozen CLI transcript used as Task 1 material) | Task 1 input |
| the offline verification packet built for the study (`PACKET_MANIFEST.json` digest recorded) | Task 2 input |
| `docs/evidence_scoreboard.html` and `docs/receipts/scoreboard.json` | Task 3 input |
| `docs/index.html` and `docs/capabilities.json` | Task 4 input |
| the wheel handed to the participant, if any — labeled REHEARSAL, RC or FINAL | Task 2 environment |

Rules: a session against any material whose hash differs from the manifest is a different study. The study asks about **the supplied artifact**; it never implies that a wheel not yet built was tested. If a later release ships materials whose hashes are identical to the manifest's, the result may be cited for that release only with an explicit identity comparison (`sha256` equality per material) and a claim scoped to those materials; a rebuilt wheel with a different hash is not covered.

## 2. Enrollment and denominator (fixed)
- **N = 5 enrolled**, fixed at enrollment; the primary fraction's denominator is always 5. A participant who withdraws, does not show, is ASSISTED, or times out stays in the denominator as a non-PASS — nobody is removed to improve the fraction.
- Eligibility: adults able to read English technical documentation; no YUCLAW authorship; not owner-affiliated (declared relationship RELATED-DISCLOSED or UNRELATED); no outcome-dependent incentive (a fixed, outcome-independent honorarium is permitted if the owner adopts one).
- Each participant receives: the packet directory, the README, the site pages listed above (local copies at the bound hashes, or the live site only if its served bytes equal the manifest at session start — recorded), and this task script. Nothing else.

## 3. Task script (five tasks; each ≤ 10 minutes; participant works alone)
Materials are read-only. The participant answers in writing; the reviewer scores against the key in §4.

1. **Check.** Open the README's CLI transcript block and find the recorded output of `yuclaw check-claim --text "NVDA reported an insider sale in May 2026"` (frozen transcript; status `SOURCE_MATCHED`, `matched_evidence` 5 objects, `misses` empty). Question: "What does this output establish, and what does it not establish?"
2. **Reproduce.** Run `yuclaw packet verify <packet dir>` on the supplied packet (or read the supplied `VERIFY.md` and the recorded verify output if no environment is provided). Question: "What did the verification check, what did it reproduce, and what does a SUCCESS *not* establish?"
3. **Read the scoreboard.** Open `evidence_scoreboard.html`. Question: "How many outsider reproductions of the exact wheel you were given have been verified? Is that number a zero, a pending state, or hidden?"
4. **Limits.** Open the landing page and the scoreboard disclaimer. Question: "Does any page tell you whether to buy or sell anything, or what a strategy will return? What does the disclaimer say the evidence is for?"
5. **Challenge.** Using the CLI (`yuclaw challenge --store <your private dir> --synthetic create …`) or the issue template text in `VERIFY.md`, record one challenge for something you believe is wrong or unclear. Question: "What did recording the challenge change about the published evidence?"

## 4. Scoring key and critical-error rubric
A task is **completed** when a written answer is given within 10 minutes. A **critical error** is any statement in the reviewer's list below. A task with a critical error is FAIL; a task without a completed answer (timeout, skipped) is INCOMPLETE; otherwise PASS.

| task | expected content (all must be present for PASS) | critical error (any one = FAIL) |
|---|---|---|
| 1 Check | `SOURCE_MATCHED` means the parsed claim elements (ticker NVDA, type INSIDER_SELL) matched stored evidence objects (five filings); it establishes coverage of the corpus, not that the claim is true, not a recommendation; `research_interpretation` is NONE | says the claim is proven true; says an UNSUPPORTED status would mean the claim is false; reads any direction, return or advice from the passport |
| 2 Reproduce | verify recomputed each file's SHA-256 + length against the packet manifest, then replayed the frozen Lab bundle's published statistics; SUCCESS means exact bytes + reproduced statistics; it is not an outsider receipt, not independent, not proof the packet is an official release, not a scientific validation | says SUCCESS is an independent/outsider result; says it proves official origin; says it validates the research |
| 3 Scoreboard | the exact-release count is zero (or the state is PENDING/UNAVAILABLE as shown); the state is displayed, not hidden; the legacy program entry is prefix-bound and affiliated, not an exact-wheel reproduction | reads a zero/pending/unavailable state as a positive count; invents a number; counts the legacy affiliated entry as an outsider reproduction of the wheel |
| 4 Limits | no page gives buy/sell direction or expected returns; the disclaimer states research and education only, not investment advice | believes the site gives investment direction or performance expectations |
| 5 Challenge | a challenge was recorded (or the template completed); recording changes nothing about the published evidence until a reviewer disposes it; adverse findings stay visible | cannot record a challenge; believes recording one changes the evidence or the counts |

Timeouts: the 10-minute clock per task is recorded; exceeding it makes the task INCOMPLETE (not a critical error). Non-critical observations (confusions, wording issues, time to answer) are recorded verbatim as formative notes and fed into documentation fixes; they never enter the gate result.

## 5. Session and study outcomes (precise)
- **Session PASS**: all five tasks completed with zero critical errors. **Session FAIL**: any critical error, or any INCOMPLETE task. **MISSING**: enrolled participant with no completed session (withdrawal, no-show). **ASSISTED**: any live help during a task — the session is recorded and reported, but counted as non-PASS in the primary fraction (a documented fallback such as reading `VERIFY.md` is not assistance).
- **Primary fraction** = PASS sessions / 5. **Candidate threshold (pending owner adoption): ≥ 4 of 5**, over **all five tasks** (this changes the earlier draft, which scored tasks 1–4 only; the change is explicit and unadopted).
- Reported publicly as `n_pass / 5` with the materials manifest digest and, per session, the outcome label (PASS / FAIL / MISSING / ASSISTED) — never individual answers. Formative notes are summarized separately from the gate result.
- A study result becomes a gate input only after the owner adopts this protocol and the release-policy actor records the change; until then the gate stays MANUAL_REVIEW on current evidence.

## 6. Data, consent and disclosure (owner/ethics decision; nothing here is advice or a determination)
- **Session code**: a pseudonymous label for bookkeeping. It is not anonymity: the reviewer can link it to the enrolled person until the enrollment list is destroyed. No claim of a legal or ethics exemption is made here; applicability is the owner's/institution's determination (template in the private review material).
- **Option A (minimal data)**: retained after scoring — session code, per-task outcome labels, timing, and the reviewer's task notes written as behavior descriptions (no quotations of anything personal, no names, no contact data); no recording. The enrollment list (code ↔ person) is kept by the owner only until the public aggregate is published, then destroyed. Written answers are destroyed after scoring; the reviewer decision form is the retained record.
- **Option B**: screen recording with explicit consent, deleted after scoring; everything else as in A.
- Either option: consent text states the purpose (comprehension of a research tool, not evaluation of the person), withdrawal at any time (recorded as MISSING; the denominator stays 5), and that public output is the aggregate only. No names in any public artifact.

## 7. Reviewer decision form (per session; private)
`{session_code, materials_manifest_sha256, wheel_label, tasks: [{task, completed, timed_out, critical_error, note}], assistance, relationship, decision: PASS|FAIL|MISSING|ASSISTED, reviewer_role, decided_at}` — stored privately; only aggregate counts are published.

## 8. What this document does not do
No participants are contacted, no consent is collected, no reviewer is designated, no gate value changes, and no owner decision is taken by shipping it. Two distinct decision paths exist for the owner and are listed in the private V7-004-V3 review material: (1) an actual authorized study under this protocol; (2) an explicit, recorded release-policy exception that leaves the human comprehension result unpassed. Neither is selected here.
