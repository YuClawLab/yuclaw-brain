# YUCLAW — V8-014: implement and ship SHD, EVO, COM and PRC in the expanded candidate

Owner instruction, September 20, 2026, Asia/Shanghai. Execute in the owner's existing Claude Code workflow. V8-013 is paused.

**Revision 2 — three-pass design review.** This revision refines the same authorized scope. Use the `r2` input archive and its manifest. Earlier V8-014 inputs remain historical; preserve any legitimate implementation already completed and apply these clarifications incrementally.

## 1. Outcome and authorization

Build the four modules into the existing v8 financial-evidence workbench. A researcher must be able to admit evidence through SHD, inspect change-sensitive evidence through EVO, manage a durable review queue through COM, and complete an attempt-before-comparison session through PRC. Package these capabilities in both the wheel and sdist, with browser navigation, help, persistence, export verification and tested security boundaries.

This is an implementation order. Continue through working integration and verification; do not stop after an assessment, a proposal, copied prototype functions or a new menu. The owner has explicitly expanded the scope. Do not ask again whether these four modules should be included or use the old experimental/default-off exclusion to defer them.

Preserve useful existing work. The reported baseline is `codex/v8-integration` at `a4fa151f82efd8e7de45c1a5cd66088ae4a9c2c7`, tree `392a6487c25b1004618d6c813d7ba85455fa5f09`. Hosted run `35485844365` passed there. Check actual HEAD, ancestry and working state before editing. Preserve later legitimate work; do not reset or overwrite it to match this historical SHA.

The previous release candidate and its CI remain historical evidence. New packaged code needs a new candidate identity and relevant verification. Do not relabel the old pair or reuse old test counts as results for this implementation.

Keep `release_authorized=false`, D1 unaccepted, and V8-013 paused. No new remote push, force push, main merge, tag, package upload, deployment, live agent action, community message or timed release is authorized. Local commits and local implementation checks are authorized. The prior one-command use of the owner's `gh` credential is not ongoing publication permission. Do not alter tokens or Git credential configuration.

## 2. Inputs and bounded discovery

Read this order and `OWNER_SCOPE_EXPANSION_2026_09_20.md`. Use `V8_014_RESEARCH_AND_ACCEPTANCE.md` and `v8-014-backlog-map.json` for implementation rationale and the 46 original backlog rows.

If the owner transferred `YUCLAW-V8-014-r2-implementation-inputs.zip`, read its `README_FIRST.md` and verify `MANIFEST.json`. Its `reference/` directory contains selected local prototype sources, tests and documentation from an older, dirty `8.0.0a6` preview. Treat them as reference material, never as a patch to apply wholesale to this checkout. They are not the current workbench, a release package, or proof of installed integration.

Inspect the current workbench's routing, claim/source identity, event persistence, scientific kernel adapter, exports, recovery, rights filtering, security controls and installed test runner. Create a concise implementation map connecting those existing interfaces to the four modules. Start implementation in this same run. Do not reread every historical order or repeat previous browser journeys just to rediscover the baseline.

Reuse correct algorithms and test ideas after adapting them to current contracts. Extract small common validators where necessary: the prototype Shield imports Control/Continuity helpers, but that does not authorize activating CTL, RES or canceled backups. Do not replace the current SCI kernel, version metadata, dependency configuration or release tooling with the old preview copies.

If a companion file is unavailable, use the requirements in this order and inspect available code; proceed on independent work rather than stopping solely to request the old prototype. Record what reference material was actually used.

## 3. Shared integration foundation

Use the current financial claim, version, source, evidence and journal identities throughout. Do not create a second disconnected provenance universe. Persist new versioned events and bounded indexes in the existing storage model, or justify a small additional store with explicit atomicity and recovery rules. A cross-store crash must not silently consume capacity, expose a comparison, approve evidence or lose a correction. Additive migrations must preserve old records and old export verification; refuse unsupported future versions clearly.

Build a minimal local authorization boundary for these workflows, not a SaaS account platform. Separate capabilities for administration/approval, submission, review and practice. Bind actor IDs to server-authenticated principals; a JSON field or display name is not authentication. Enforce object and workspace scope on every route, CLI service entry and export. A principal with multiple roles must still be checked for conflicts on the particular task. Attribute automated fixtures honestly.

Provide a usable local setup command and browser setup/status page. Generate no default shared passwords or embedded production signing keys. Keep secrets out of URLs, logs, exports and packages. Use maintained authentication/cryptography primitives rather than custom algorithms. Test credential expiry/revocation, CSRF/origin and Host validation, parameterized storage, safe rendering, session separation, cross-workspace access and bounded requests. Preserve loopback binding and the existing SSH-tunnel workflow; do not expose a public listener.

Maintain separate timestamps for asserted source time and server-recorded actions. Later approvals, reviews, corrections and revocations must not silently appear as if known in earlier historical views. Authentication proves which local credential acted, not legal identity, human authorship, reviewer qualification or factual truth.

Integrate a clear Modules page and context links from sources, claims and exports. All four modules must be discoverable in a normal installed workbench. An unconfigured trust boundary should show the precise setup step and refuse protected actions; do not hide the module or silently fall back. Keep explanations about commit hashes and implementation details in diagnostic views unless needed for a user's decision.

## 4. SHD — Distillation Shield

Deliver a protected evidence-admission and typed-result path used by the new EVO/COM workflows. Here, Distillation Shield means a deterministic boundary around untrusted evidence; it does not train a model or guarantee removal of every malicious sentence.

### Trust and approval

Implement an owner-controlled approval registry outside submitter-controlled evidence. Bind each approval to exact input/manifest and source digests, permitted purpose, workspace, approver principal/key identity, issue time, expiry and policy version. Include rotation, revocation and retrieval/audit records. Use a maintained signature implementation for portable approvals, or an equivalently independent authenticated registry for local approval; document the exact trust mechanism.

Use an explicit versioned canonical signing/approval envelope with unambiguous types and domain separation for approval, evaluation and checkpoint records. Reject unknown schema versions and ambiguous encodings. An approval signature cannot be reused as an evaluation or a checkpoint. Preserve canonical financial-unit and timestamp rules; do not create a custom cryptographic algorithm.

A submitting principal must not be able to enroll its own trusted root, mint its own accepted approval, change the policy, replace an audit checkpoint or approve its own bundle. New root enrollment and approval administration require the separate administrative capability. No trust-on-first-use from an imported bundle. A receiver's trust configuration determines whether an exported approval is trusted.

Revalidate approval applicability at the protected operation, not only during upload. Bind the verified bytes, policy version and decision to the committed operation. Define the transaction boundary for concurrent revocation: an action committed before revocation remains historical; an action after revocation must not use a stale authorization cache. Clock uncertainty, missing approval, expiry or revocation produces an explicit refusal, not a successful result.

Separate historical verification from current authorization when offline. Display the authenticated trust/revocation snapshot and verification time actually available. A disconnected receiver cannot establish that no later revocation exists; use an explicit freshness/unknown status and do not authorize a freshness-dependent action from it. Imports must not overwrite newer trusted policy, resurrect revoked credentials or install roles/keys from the payload. Lower or conflicting trust-state revisions require an explicit administrative resolution, with the discrepancy retained.

### Parsing, files and worker isolation

Preserve strict schema validation, duplicate-key rejection, bounded integers/nesting/counts/total bytes, stable reads and safe relative-path resolution. Cover archive traversal, duplicate archive names, decompression limits, symbolic/hard links, special files and concurrent replacement if archives are accepted. Never let evidence provide arbitrary host paths, module names, shell commands, URLs to fetch or serialization constructors. Keep evidence text inert; do not execute it, render it as active HTML or feed it into privileged tool instructions.

Run untrusted parsing/evaluation in a restricted worker on the supported Linux deployment, using an available maintained isolation backend such as bubblewrap or an equivalently constrained rootless container. Implement the launcher and capability check, not just a suggested command in documentation. Allow only required runtime libraries and the exact staged input, with a bounded output channel, no host home/credentials/control sockets, no external network, no privilege escalation, and CPU/time/memory/process/file limits. Use a fixed executable and fixed argument structure. Validate worker output again in the trusted parent.

Apply limits from the first HTTP/CLI bytes, before allocation or complex parsing in the trusted parent. Stage bounded raw content through safe handles; archive extraction and complex untrusted parsing belong inside the restricted path. Document the parent's minimal unavoidable envelope parser and bound it separately. Never parse the whole hostile document before launching the sandbox. Clear unnecessary environment variables and inherited file descriptors; bound and validate stdout, stderr and error records as well as successful outputs.

A same-user subprocess and file mode 0600 alone are not an OS security boundary. Document exactly what the selected backend denies, then test those denials. Do not weaken host security, enable privileged containers, mount Docker sockets or disable system protections to make a test pass. If a required isolation facility is unavailable, keep the protected route closed and report the specific platform gap while completing independent work. Do not label that platform's SHD integration complete. Ordinary supported read-only workflows may remain available with their existing guarantees.

### Product result

Show the user the submission, approval provenance, fixed verification/rejection reason, revocation status and next action. Expose only validated typed fields and permitted identifiers through privileged consumer APIs. Human-readable source inspection is a separate escaped, authorized view. A rejected bundle must not reach an unshielded evaluator through a retry, compatibility route or CLI shortcut carrying the same protected promise.

Keep byte integrity, authority approval, factual adjudication and release permission as separate fields. A correctly approved but false financial statement must remain possible and visible in the negative-control demonstration; successful SHD verification must never turn it into a true fact.

## 5. EVO — Evolution Evidence Audit

Deliver persistent version registration, change comparison, review evidence, targeted reevaluation requests and reproducible audit export. Cover model, agent code, tool policy, memory, data, runtime, grader and evaluation data.

Measure available local installed code, dependency/runtime identities, policy and approved data/memory snapshots from trusted configured locations. Label each component `MEASURED`, `DECLARED`, `UNKNOWN` or justified `NOT_APPLICABLE`. Hashing a provider alias or user-provided string does not measure model weights. Do not invent unavailable deployment identity. Bound discovery to configured roots and exclude secret values.

Record ancestry, dependency edges, inventory completeness and authority changes. Require evidence reuse to match the actual dependency closure, protocol, validity period, target identity and relevant authority state. Explain why a result is reused or invalidated. An unrelated component change may reuse unaffected evidence; a transitive dependency, grader or test-policy change must invalidate what depends on it. Unknown required inventory stays unresolved.

Bind a trusted local evaluation to the exact immutable snapshot actually executed. A file changed between collection and execution must be rejected or recollected as a new identity, not evaluated under an earlier digest. Compare dependencies to the configured collector/runner contract; deleting a dependency edge in submitted metadata must not make its stale evidence reusable. Incomplete required coverage yields a review gap, not an empty dependency set or silent NOT_APPLICABLE.

Authenticate submitters, improvers, reviewers, graders and test custodians through the shared principal layer. Track conflicts through ancestry. Preserve protected-test exposure after access is revoked. A new test digest alone does not establish fresh semantic content. Store imported declared evaluations distinctly from evaluations produced by a trusted configured runner.

Persist failures with stable issue identities and scope/lineage links. A later pass, changed version label, renamed protocol, expiry or new digest must not silently erase a still-applicable failure. Provide an authorized resolution event with supporting evidence and reason, preserving the original failure. Conversely, do not hold unrelated versions forever: show and test the applicability/resolution rule.

Separate present-day review from review known at a historical cutoff. Reject or label backdated assertions so they cannot manufacture historical approval. Show unreviewed transitions, evidence age, open failures, missing inventory, test exposure and conflicts together.

Implement typed requests for supported local reevaluation jobs only; no payload-supplied arbitrary executable. Route evaluation inputs through SHD where the protected promise applies. Provide a read-only decision/eligibility API that identifies the exact evaluated subject. It does not by itself control an external deployment. A real institutional deployment controller remains conditional on a separately authorized integration; do not claim it exists.

Retain supplied financial-commitment links by configuration and currency, with unknown amounts separate; do not invent FX conversions, avoided losses or trading decisions.

Prove the integration with actual controlled file/configuration changes observed by the collector, not only hand-edited digest strings. Include a relevant dependency change, an unrelated change, an authority change, a grader change, a mutable/unknown model identity, a persisting failure and a valid resolution. Compare targeted reevaluation with a repeat-everything baseline on the same controlled fixtures and disclose missed changes and unnecessary reruns.

## 6. COM — Research Commons Guard

Deliver a durable evidence-review queue connected to existing claims and sources. Users must submit, inspect duplicates/lineage, allocate work, start/pause/finish review, resolve or appeal quarantine, and resume after restart.

Persist exact duplicate groups and idempotent membership across ingestion runs. Group only compatible canonical claim/version contracts and known source roots; preserve differences in metric, currency, unit, accounting basis and fiscal period. Show shared roots and unknown ancestry. Many summaries of the same source do not become independent corroboration. Do not label semantic similarity or a common source as plagiarism or misconduct.

Propagate recorded disputes, withdrawals and source corrections through aliases and affected dependencies without editing original source bytes or erasing previous review history. Distinguish source-byte identity from the authority of a withdrawal: an untrusted submission must not be able to quarantine the whole workspace merely by asserting that a source is withdrawn. Use authenticated review/administrative events and retain appeal/resolution history.

Enforce admission and contributor limits using authenticated stable principals. Bound total queue/storage growth and request rate. Display names cannot reset caps. Document that local credentials do not solve collusion or real-world Sybil identity. Preserve every contributor's attribution even when work is grouped.

Use transactions for reservations, assignment and completion. Concurrent submissions or workers must not spend the same capacity twice. Persist an explicit state machine for queued, assigned, active, paused, completed, deferred, quarantined and canceled work, or an equally clear equivalent. Define rollover, lease/recovery behavior, cancellation, partial work and budget changes. Urgent overrides must be recorded by an authorized role and must not silently create capacity.

Track estimated effort separately from server-observed session time and manual effort declarations. Include triage, quarantine investigation, correction and coordination. Timers are not proof of attentive human labor. Reserve a separate practice allocation; never silently borrow it for general review. Oversized work must not block fitting smaller tasks. Show unspent capacity, deferred reasons and backlog age.

Treat submitter cost estimates as proposals. Establish or revise scheduling cost through an authorized estimator/reviewer rule; repeated duplicate submissions cannot inflate an existing group's cost or reduce its reservation. Test both directions of manipulation. Define aging and oversized-task escalation so repeated small arrivals do not silently starve older work. Escalation must not manufacture budget. If an authorized budget reduction falls below recorded consumption, show the overrun and stop new reservations rather than rewriting consumption or making remaining capacity negative.

Expose a dashboard with unique claims, duplicate volume, shared roots, queue age, allocation, estimates versus recorded effort and completion. Implement a reproducible comparison with a conventional FIFO queue using the same synthetic arrivals and effort assumptions. Label it a controlled simulation; it cannot establish actual human productivity, error reduction or fairness. Provide the instrumentation needed for a future voluntary human comparison without enrolling anyone now.

## 7. PRC — Independent Practice

Deliver a browser workflow for a bounded financial-research task: open frozen question/source scope, read evidence, commit a judgment and reasoning, reveal the comparison, record reflection, receive optional reviewer feedback, and export a permitted session record. Implement optional scheduled/delayed follow-up tasks as local due-state functionality; do not launch a study, contact participants or schedule this assistant.

Freeze task identity, source/claim versions and reference content before opening. A curator's credential and declared qualification may be recorded; do not fabricate qualification or an independent human reviewer. Public packaged example answers are demonstrations, not confidential assessments.

Keep the comparison in server-controlled storage unavailable to the practitioner capability before an attempt. Enforce this on direct URLs, APIs, export, journal, help/static resources, errors, caches and alternative claim views. A hidden HTML element, disabled button or CLI order check is insufficient. Restrict question/source scope deliberately; do not claim genuine blinding if another permitted view already reveals the answer. Use a salted commitment or another reviewed approach if a low-entropy public answer hash would reveal it by enumeration; reveal the verification material only when permitted.

Require judgment, reasoning, relevant source references and an unresolved option. Record assistance and prior exposure truthfully, including assisted/already-exposed sessions. Never force users to claim they have not seen an answer simply to continue. Distinguish those sessions from an unaided attempt.

Commit the original attempt atomically before releasing comparison content. Preserve it; subsequent changes are separate reflections or feedback. Make retries idempotent and concurrent submission/reveal behavior deterministic. Show comparison provenance: an unadjudicated reference or model answer is not ground truth. Evidence-reading events establish access, not comprehension.

Preserve journal replay and support separately held checkpoints. Detect alteration and truncation when a receiver supplies a trusted checkpoint; a hash chain with a checkpoint from the same hostile bundle is not sufficient. Keep participant records private by default. Support explicit, scoped export with preview/redaction; no automatic training dataset or employee ranking.

When a source is corrected/withdrawn or a relevant EVO identity changes after task opening, preserve the frozen session and display the effect on current interpretation. Do not rewrite the original attempt, silently substitute the answer, or retroactively upgrade a retrospective result. A host administrator, curator, outside assistance or a compromised owner account is outside the claimed answer-confidentiality boundary; document that plainly.

## 8. One integrated demonstration

Provide one reproducible installed-package journey with labeled fictional financial evidence and separate test principals:

1. Register a source and compatible typed claim using the existing workbench.
2. Submit a changed/self-approved/expired bundle to SHD and observe refusal through the actual protected route. Admit an independently approved valid bundle. Keep source text containing hostile instructions inert, with no unauthorized effect.
3. Submit repeated packets to COM, including after restart. Show one appropriate review group, retained attributions and no duplicate budget spending. A different claim contract remains separate. A recorded dispute has a visible, reversible-by-new-event review path.
4. Allocate a practice task from the reserved capacity. A practitioner cannot retrieve the comparison before committing. Then commit, reveal, reflect and export. Also demonstrate an honestly assisted session without calling it unaided.
5. Register and measure an EVO version, record scoped review evidence, change an actual relevant input, and show affected evidence becoming stale while unrelated evidence can be reused. An unresolved failure remains visible until a valid resolution event.
6. Export permitted evidence and verify it in a fresh workspace. Verify byte/schema integrity independently of receiver trust and permissions; an unknown signer must not silently become trusted. Recompute relevant derived views, and reject forged links or unauthorized private-answer inclusion.

Record executable commands, expected and observed results, platform and source identity. Retain the original seven-step workbench journey and source-availability correction behavior. A narrated screenshot or synthetic actor labeled as a real human is not acceptable evidence.

## 9. Verification and adversarial acceptance

Add meaningful tests with the code. Reuse existing stable coverage; do not repeatedly run the entire suite during every edit. Run focused tests during development and the appropriate full regression suite after integration. Re-run affected checks after any later packaged change.

Predefine expected outcomes for benign and adversarial cases from the requirements, not from the implementation's current output. Each important refusal needs a valid authorized positive counterpart, so rejecting everything cannot pass. Use a small targeted test-sensitivity check for the main boundaries: safely disable the relevant check only in an isolated test variant and confirm that the corresponding test detects the violation. Never weaken the actual product to run such a check, and do not expand this into an exhaustive mutation-testing project.

Record workload size, hardware, dependency versions, seeds and denominators. Measure protected-operation latency and peak memory, capacity conservation, relevant-change detection and unnecessary reevaluation. Compare bounded-input cases with the declared budgets and show scaling on at least two justified workload sizes. Run the preexisting core journey as a regression reference. Do not invent a universal latency target or claim an improvement where no comparable measurement exists. Keep security zero-violation assertions limited to the enumerated tested cases.

The companion matrix names required acceptance families. At minimum test: forged/self-enrolled approvals; expiry/revocation/rotation and concurrent use; duplicate/deep/oversized JSON; path and archive escapes; symlink/special-file and read races; forged worker outputs; failed isolation with no fallback; denied worker network/secret/host-write access; cross-role/workspace requests; forged actor IDs; CSRF/unsafe rendering; approval and audit-store writes denied to submitters; relevant versus irrelevant runtime changes; unknown inventory; grader conflicts and historical test exposure; persistent failure resolution; duplicate floods and cap evasion; concurrent capacity allocation and crash recovery; withdrawal authority and appeals; early comparison leakage on every accessible surface; idempotent attempt/reveal; cross-session access; assisted-session labels; tampered exports and truncation against an independent checkpoint.

Use controlled local fixtures and canary files/endpoints for security tests. Do not attack third parties, access production credentials or send live SEC requests. Keep attack payloads and synthetic approvals clearly separated from genuine owner decisions.

The protected Linux path needs actual isolation probes on supported infrastructure, including the intended architecture. Mock-only tests or skipped security tests do not prove that boundary. Keep a support matrix for executor Linux and hosted Linux; unsupported platforms must refuse only the operations whose guarantees cannot be met and explain why.

Build one final candidate wheel/sdist after packaged implementation settles. Inspect both distributions for all four modules, resources, schemas and help. Exclude keys, credentials, private participant/session data, policy/order records and development artifacts. Install each in a fresh environment outside the checkout, without editable installation or PYTHONPATH fallback. Run the integrated demonstration and existing applicable regression journeys from both. Retain the supported Python 3.10 floor, package checks, original data preservation and export compatibility. Never remove a failing test or change an expected security refusal just to obtain green results.

Update the existing pre-release CI workflow to run relevant module integration and isolation checks with least permissions and no publication side effects. Rehearse locally. A new hosted run requires a separately approved branch push; return a concrete diff and SHA for that approval. Keep `REMOTE_CI_NOT_RUN_FOR_NEW_SHA` explicit until it runs. No stale green result may be attached to a new commit.

## 10. Scope, evidence and product wording

Update the active scope representation, feature inventory, package resources, operator/data guides, release-note composer, draft notes and proposed D1 consistently. Preserve old D1 proposals and old order records. The new proposal names the actual expanded candidate and distinguishes included capabilities from optional operational activation. Do not accept D1 for the owner.

Map every original COM/PRC/SHD/EVO backlog row to code, a current check and its honest status. Never turn the original 46 rows into COMPLETE by reducing their definitions. COM-12's actual human effort comparison, PRC's qualified-reviewer/learning evidence, SHD-12's independent security review and EVO-10's authorized external deployment integration require separate real evidence or authority. Build their useful software/instrumentation now; keep unavailable external evidence explicit. They do not justify pretending an unfinished module is delivered, and they do not reinstate Gate 15.

Preserve Gate 15 as `REMOVED_BY_OWNER / NOT_REQUIRED`; no route A/B/hold choice or new human-study exception. Human benefit remains `PENDING`. Distinguish `IMPLEMENTED`, `INSTALLED_AND_DEMONSTRATED`, `HOSTED_CI_VERIFIED`, and `RELEASED`; do not collapse them into one completion word.

Produce a short claim-to-evidence table with candidate-specific test links and limitations. Suitable claims describe observed behavior, such as rejecting a modified approved bundle in a supported configuration, invalidating review evidence after a measured dependency change, grouping exact duplicate review work, or withholding a comparison from a practitioner until submission. Do not claim all AI attacks are prevented, evidence is true because signed, self-improvement is controlled, duplicates prove misconduct, financial returns improve, or human ability is proven to improve.

Distinguish established techniques, the proposed YUCLAW integration contribution, and empirically demonstrated advantages. Evaluate a connected workflow against the same components used separately, measuring manual re-entry, missing/stale links and reproducibility under a controlled source correction. A weaker baseline must be labeled. No superlative novelty, patentability, state-of-the-art security or user-benefit claim follows from feature count, a long order, token usage or internal test totals. Capture failed comparisons as well as favorable ones.

Keep the approved mission, vision, logo bytes and English-only product content. Preserve canceled backups and deferred CTL/RES/RND/full RIV/ACT/multi-tenant/accounts/billing scope. Do not introduce a new external model subscription, live LLM evaluation bill, telemetry service or dependency on hosted AI calls for basic module operation.

## 11. Execution and stopping point

Use a dependency-aware sequence: shared contracts/persistence/authorization; SHD boundary; EVO and COM integrations; PRC confidentiality and workflow; integrated export/UI; verification and packaging. Make reviewable local commits with the repository's required sign-off. Keep a compact progress record so a context continuation resumes completed work rather than restarting it.

Resolve ordinary implementation choices autonomously. Do not create repeated owner approvals for each internal function. If a genuine external prerequisite blocks one component, report the exact failed operation, the secure alternatives attempted and what remains; continue independent work. Do not spend repeated cycles on unchanged failures or silently weaken the boundary. Do not purchase credits, change the user's model or assume that long token usage proves innovation.

After the expanded candidate is built and locally verified, return:

- What each module lets a user do, with entry points and setup steps.
- Baseline, commits, final source SHA/tree, working status, artifact names/hashes and platform/dependency requirements.
- Current tests, negative cases, installed journeys and actual isolation results, with failures/skips listed separately.
- The 46-row reconciliation, the proposed D1 and claim-to-evidence table.
- Remaining external evidence or owner action, including a precise proposed CI branch push if needed. Do not execute it.
- A short manual walkthrough with observations left blank for the owner, and an updated realistic freeze/readiness assessment.

Then stop. Do not resume V8-013, freeze, publish, schedule a release or send messages. This order authorizes implementation in the owner's Claude Code workflow; it does not authorize Codex to connect to the DGX Spark.
