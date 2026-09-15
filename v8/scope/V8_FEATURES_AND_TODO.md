# YuClaw v8: features, functions, and implementation checklist

Roadmap baseline: September 14, 2026; active release scope updated September 15. This is a consolidated implementation roadmap, not a production release announcement. All unfinished checkboxes describe proposed work. Roles below are ownership recommendations, not people already assigned.

**8.0.0 execution scope:** [Scope freeze and Claude feedback review](V8_0_0_SCOPE_FREEZE.md) controls the first release; the 213 tasks below remain the broader roadmap. The owner-operated seven-step workbench is enabled scope. COM/PRC/SHD/EVO are experimental/default-off, and CTL/RES, the full RIV/ACT engines, multi-tenancy, the pilot and RND are deferred. **Backup functionality is canceled by the owner, with no automatic Calgary resumption.** See [the first executor order](CLAUDE_CODE_ORDER_V8_001.md).

**Mission: Make financial AI accountable to evidence.**

**Vision: Become the Science Trust Layer for Financial AI.**

**Standing user instruction:** never change, replace, or redefine this approved mission or vision without the user's explicit permission specifically authorizing that change. Logo, feature, release, and promotion approvals do not grant that permission. This applies to every YuClaw version and all product and public materials.

The product promise is: **Turn a financial thesis into explicit claims, investigate what could disprove it, preserve what was known at the time, and produce a reviewed record of what subsequently happened.**

V8 belongs on its own development and release path. V7 keeps its existing scope. Deployment, publication, and community outreach remain paused. Completing v7 does not automatically authorize launching or promoting v8. All YuClaw-authored interfaces, documentation, reports, examples, and marketing remain English only.

**Approved brand identity:** use [YuClaw — The Human Trace](../YuClaw-brand-assets/human-trace-v1/README.md), including the selected light logo, dark logo, and transparent symbol. The user approved these assets without further design changes. Use the delivered files for v8; preserve geometry, typography, proportions, and colors. This brand approval does not lift the deployment or outreach hold.

**Protection and launch review:** [AI-related protective functions and targeted community launch](V8_AI_PROTECTION_AND_LAUNCH.md) maps eight protective functions to this existing backlog, records fresh checks, and identifies suitable launch communities. Historical a4 outreach drafts must be refreshed against the actual v8 release before use.

**Release status and targets:** v7.0.0 was independently verified released on September 15. The owner now targets v8 release on Monday September 21, followed by promotion after verified release. The September 19 evening Gate B go/no-go checkpoint remains; final audit and artifact freeze are targeted for September 20. See the [release schedule and readiness follow-up](RELEASE_SCHEDULE.md). Dates do not establish completion or waive release gates, and v7's release-policy exception does not automatically apply to v8.

This plan consolidates the existing product design, local implementations, research reports, and verification records. It does not claim a new exhaustive literature review, demonstrated customer demand, or an independently proven scientific breakthrough.

## 1. Where the product stands

The local preview is **8.0.0a6**. Its recorded verification includes **292 selected offline tests passed**, installed-package replay of **36 Shield/Evolution/Commons cases**, and a complete local practice-command flow. This is useful engineering evidence. It does not establish full application integration, remote CI success, commercial readiness, resistance to every AI attack, or measured human benefit. See [the verification record](../yuclaw-brain/output/commons-verification.json).

| Existing foundation | Completed locally | Still required for a customer product |
|---|---|---|
| Scientific evidence kernel | Frozen study contracts; paired binary predictions; prospective outcome updates; invalidation; replay; diagnostics | Product adapters, authenticated adjudication, external checkpoints, scientific review, UI and real studies |
| Evidence inspection | Dated bundled source inspection and exclusions | Fresh ingestion, durable source versions, full historical query service |
| Human Control Exit Audit | Read-only analysis of supplied stop-drill traces and financial commitments | Authenticated operational records, complete scope, institution integration and independent drills |
| Human Option Reserve | Exact planning for one mission under supplied scenarios and evidence | Actual service data, independently verified dependencies, real drills and benefit evaluation |
| Distillation Shield | Bounded input parsing, approved-byte verification and data-only output | Trusted approval management, tenant integration, execution isolation and enforced production boundaries |
| Evolution Evidence Audit | Configuration lineage, review applicability, conflicts, failures and commitment summaries | Measured runtime identities, authenticated authorities, real change feeds and separate deployment control |
| Research Commons Guard | Duplicate grouping, source-lineage checks, quarantine and bounded review allocation | Persistent queues, reliable identities/statuses, actual review-time accounting and appeals |
| Independent Practice | Attempt-before-comparison sequence with local journal and replay | Product UI, separate permissions, meaningful task selection and measured learning outcomes |

The six main customer capabilities remain proposed product scope: thesis specification, competing explanations, financial consistency checks, evidence selection, research history, and derived data delivery. Existing commands are building blocks for those capabilities.

## 2. The complete customer journey

1. Select a company, a research question, and an information cutoff.
2. Convert the question into editable claims and explicit assumptions.
3. Attach original evidence, quantities, dates, and source lineage.
4. Compare plausible explanations and inspect calculations or contradictions.
5. Choose the next research action, obtain review, or remain unresolved.
6. Freeze eligible predictions before outcomes become available.
7. Review the later outcome independently using the original resolution rule.
8. Inspect the full history and export reusable, versioned research data.

The main screens are **Thesis Workspace**, **Evidence & Review Queue**, and **Dataset Browser**. History, source inspection, and evaluation reports are connected views. Optional institutional tools appear in a **Trust & Continuity** area. Research Commons supports the normal queue; Independent Practice is optional.

### A fictional acceptance scenario

A company states a revenue target of 110–120 million units of a specified currency for a defined fiscal quarter. The researcher records the exact passage, accounting basis, metric scope, and dates. The company later changes the target to 105–115 and then reports 112 on a comparable basis.

V8 must preserve the original and revised targets, show when each became available, evaluate the outcome against each relevant frozen definition, and export amendment and outcome events. It must not replace the original target, confuse a fiscal quarter with calendar dates, count copied summaries as independent evidence, or label an unavailable outcome as a miss. Different economic explanations can remain unresolved even when the numerical target is met.

This scenario is a product test fixture, not a claim about a real issuer or proof of customer value.

## 3. Priorities and ownership

**P0 — Core pilot:** necessary for the first complete financial-research workflow and controlled customer evaluation. A pilot is not general availability.

**P1 — Supporting v8 modules:** included in the v8 backlog, delivered behind explicit feature controls until their own integration and validation gates pass. Their unfinished work does not become a new v7 requirement.

**P2 — Research extensions:** experiments that may improve v8 after a reliable baseline exists. They are not promised launch capabilities.

| Workstream | Priority | Proposed accountable role | Main prerequisite |
|---|---|---|---|
| GOV — Scope and inherited baseline | P0 | Product lead | Released v7 for integration; preparation can start now |
| DAT — Evidence and shared objects | P0 | Data engineer | GOV interface inventory |
| CLM — Thesis specification | P0 | Application engineer | DAT contracts |
| RIV — Competing explanations | P0, narrow initial domain | Research lead | CLM |
| CHK — Financial consistency | P0, explicit limited rules | Financial-data lead | DAT, CLM |
| ACT — Research action queue | P0 deterministic; learned policy P2 | Product/research lead | RIV, CHK |
| TIM — Research history | P0 | Data engineer | DAT |
| SET — Commitments and outcomes dataset | P0, limited coverage | Dataset lead | CLM, CHK, TIM |
| SCI — Scientific evaluation | P0 for the claimed evaluation scope | Research lead | CLM, TIM |
| COM — Research Commons | P1 | Review-operations lead | DAT, CLM |
| PRC — Independent Practice | P1 | Research-training lead | COM |
| SHD — Distillation Shield | P1 module; required for any shipped Shield-backed route | Security engineer | DAT, GOV |
| EVO — Evolution Evidence Audit | P1 | Model-risk lead | SHD, SCI |
| CTL — Human Control Exit Audit | P1 | Institutional-risk lead | DAT, GOV |
| RES — Human Option Reserve | P1 | Continuity lead | SHD, CTL |
| UX — Customer workbench | P0 core; optional module views P1 | Product designer | CLM, TIM, SET, ACT |
| INT — Application and operations integration | P0 core; optional adapters P1 | Platform engineer | DAT, GOV |
| VAL — Real-world validation | P0 core; module-specific studies P1 | Independent evaluation lead | SCI, UX, INT |
| REL — Release and customer readiness | P0, only for enabled scope | Release lead | VAL |
| RND — Research extensions | P2 | Research lead | Reliable baseline and separate study approval |

Prerequisites describe integration order. Design work and isolated development can proceed in parallel. A feature's backend does not have to wait for its final UI to be designed. No calendar estimate is credible until the v7 interfaces, team capacity, and pilot corpus are known.

## 4. Shared data objects and system rules

| Object | Minimum contents | Rule that must hold |
|---|---|---|
| SourceArtifact | Stable ID; exact-byte digest; version; publisher; retrieval record; availability; entitlements | A source correction creates a new version |
| EvidenceSpan | Artifact version; page/section/offset; exact passage; extraction method | A citation opens the exact version used |
| Quantity | Value/range; currency; scale; metric; basis; fiscal period; segment | Incomparable quantities cannot silently become comparable |
| ClaimDefinition | Subject; type; target; threshold; horizon; resolution rule; version | A frozen prediction retains its original definition |
| ClaimDependency | Parent/child; relationship type; supporting evidence or assumption | An asserted causal edge is visibly an assumption unless separately established |
| Investigation | Tenant; researcher; cutoff; claim versions; state; collaborators | Private investigations stay within authorized scope |
| RivalHypothesis | Mechanism; observable implications; discriminating evidence; unresolved issues | Multiple generated explanations do not count as independent evidence |
| ResearchAction | Question; source/action; expected cost; status; observed usefulness | Waiting and abstention remain visible outcomes |
| Adjudication | Frozen definition; outcome evidence; rubric; reviewer; conflicts; result; reason | A disputed or missing outcome cannot silently become a binary label |
| StudyManifest | Population; unit; metric; model identities; error allocation; stopping rules | Renaming or repeating a study does not erase previous attempts |
| DatasetSnapshot | Schema version; selection rule; row IDs; cutoff; corrections; rights; quality report | Every delivered snapshot is reproducible |
| ReviewGroup / PracticeRecord | Source-root lineage; claim scope; budget or attempt sequence; review state | Duplicate volume cannot manufacture corroboration or erase protected practice time |
| ConfigurationVersion | Artifact inventory; ancestry; dependencies; authorities; reviews | Old evidence is reused only within its documented applicability |
| AuditFinding | Scope; observed fact; gap; evidence; timestamp; status; responsible role | A completed computation is distinct from operational assurance |

Common rules: retain unknowns; record disagreement; distinguish byte integrity from source authenticity and truth; preserve prospective commitments; keep deterministic calculations separate from generated suggestions; require explicit authorized actions for external effects.

## 5. Detailed implementation backlog

### GOV — Scope, baseline, and product decisions

Priority: P0. Current status: design and local preview exist; released-v7 integration is pending. Output: approved v8 scope and interface inventory.

- [ ] GOV-01 Inventory the released v7 features and interfaces before assigning duplicate work; record which capabilities v8 inherits, extends, or introduces.
- [ ] GOV-02 Create the v8 integration branch from the approved released baseline when available; preserve current preview artifacts for comparison and migration.
- [ ] GOV-03 Record one initial customer job, eligible company population, disclosure types, and coverage limits; make exclusions visible in the product.
- [ ] GOV-04 Freeze the canonical mission, vision, and English-only authoring policy in product requirements and automated checks.
- [ ] GOV-05 Define feature controls for Commons, Practice, Evolution, Control, and Reserve; document which roles can enable each module.
- [ ] GOV-06 Maintain a capability register separating implemented locally, integrated, independently evaluated, pilot-enabled, and publicly released states.
- [ ] GOV-07 Assign accountable owners and independent reviewers; document who can change evidence, freeze studies, adjudicate outcomes, and authorize releases.
- [ ] GOV-08 Record explicit launch and outreach holds; require a separate user readiness decision after v7 completion before any publication or promotion.

Acceptance: the feature inventory identifies the actual inherited baseline; no v8 task is added to the v7 completion criteria; no preview is represented as production functionality.

### DAT — Evidence ingestion and shared research objects

Priority: P0. Current status: bundled evidence inspection and local schemas exist; the shared product pipeline is unfinished. Output: versioned evidence service.

- [ ] DAT-01 Adopt stable issuer, filing, artifact, passage, claim, investigation, and dataset identifiers; preserve inherited v7 IDs through explicit adapters.
- [ ] DAT-02 Implement SourceArtifact and EvidenceSpan storage with immutable versions, digests, publisher attribution, and exact passage locations.
- [ ] DAT-03 Separate publication time, first observation, economic period, source revision, and processing time; store uncertainty instead of invented timestamps.
- [ ] DAT-04 Build ingestion for one approved initial disclosure corpus; retain original artifacts separately from parsed text and YuClaw-authored output.
- [ ] DAT-05 Record source entitlements and redistribution permissions; enforce tenant boundaries and prevent private research from entering shared datasets by default.
- [ ] DAT-06 Add extraction records for tables, passages, units, fiscal periods, and footnotes; attach uncertain extraction to a review queue.
- [ ] DAT-07 Represent primary, derived, and unknown source lineage; retain shared roots and explicit gaps rather than counting URLs as independent sources.
- [ ] DAT-08 Implement immutable correction and withdrawal events; find affected claims, calculations, reviews, and dataset snapshots without rewriting their history.
- [ ] DAT-09 Define authenticated roles and authorization checks for source ingestion, reviewer identity, study ownership, and evidence approval.
- [ ] DAT-10 Support idempotent ingestion and explicit failure states; replaying a job must not duplicate an artifact or silently drop failed records.
- [ ] DAT-11 Implement safe rendering of untrusted documents and passages; source text must never gain permission to invoke tools or alter privileged instructions.
- [ ] DAT-12 Publish a data dictionary and fixtures covering missing periods, conflicting currencies, corrected sources, shared roots, and inaccessible licensed content.

Acceptance: an ingested source can be traced to its exact bytes and passage; a correction reaches dependent views as a new event; unauthorized users cannot retrieve its private content through UI, API, search, or export.

### CLM — Thesis specification and claim graph

Priority: P0. Current status: proposed product capability. Output: editable, versioned thesis definitions.

- [ ] CLM-01 Build thesis creation with issuer, information cutoff, research question, author, and initial scope; save drafts without falsely marking them reviewable.
- [ ] CLM-02 Extract candidate claims from supplied narratives and disclosures; show source-linked suggestions for human editing before acceptance.
- [ ] CLM-03 Require metric, unit, accounting basis, fiscal period, comparator, threshold or range, horizon, and resolution rule where applicable.
- [ ] CLM-04 Classify nodes as observed fact, calculation, assumption, prediction, or open question; keep uncertainty in those classifications visible.
- [ ] CLM-05 Provide typed dependency edges and explanations; reject graph cycles where the selected relationship requires an acyclic dependency.
- [ ] CLM-06 Detect unresolved scope, vague terms, and missing units or dates; prevent freezing an operationally undefined prediction.
- [ ] CLM-07 Support reviewer comments, proposed edits, accepted revisions, and explicit disagreement with author identity and time.
- [ ] CLM-08 Freeze a claim version with the exact source set and resolution rule; later edits create successor versions rather than changing past commitments.
- [ ] CLM-09 Link one broad thesis to several narrower measurable implications; explain that passing an implication does not prove the whole investment thesis.
- [ ] CLM-10 Attach conditions that would weaken or contradict each claim; allow an honest unresolved state when no discriminating observation exists.
- [ ] CLM-11 Implement draft, needs clarification, reviewable, frozen, awaiting outcome, adjudicated, and invalidated states with permitted transitions.
- [ ] CLM-12 Export the claim graph with schema/version information, evidence references, uncertainty, and revision history; support a round-trip validation check.

Acceptance: “growth is sustainable” remains a draft until operationally defined; a later relaxed threshold cannot convert the original failed prediction into a success.

### RIV — Competing explanations

Priority: P0 for a narrow, reviewed first implementation. Current status: proposed capability. Output: a comparison of plausible mechanisms and discriminating observations.

- [ ] RIV-01 Select an initial explanation domain with a financial reviewer; document the kinds of mechanism the first release can reasonably compare.
- [ ] RIV-02 Generate a small editable set of alternatives, each linked to the observation it explains and its economic assumptions.
- [ ] RIV-03 Require at least one observable implication for every retained alternative; distinguish unavailable data from an unfalsifiable formulation.
- [ ] RIV-04 Build a comparison matrix showing supporting observations, contradicting observations, shared predictions, and unresolved differences.
- [ ] RIV-05 Identify source and model overlap; repeated agent agreement from one filing must not raise an independent-evidence count.
- [ ] RIV-06 Retain minority views, reviewer objections, and rejected alternatives with reasons; provide a visible route to reopen them with new evidence.
- [ ] RIV-07 Mark alternatives as observationally indistinguishable when available evidence cannot separate them; avoid forced winners or fabricated probabilities.
- [ ] RIV-08 Freeze the comparison used in a prospective study; alternatives invented after the outcome belong to a new exploratory version.
- [ ] RIV-09 Evaluate against ordinary retrieval and retrieval plus skeptical review at matched source access, task difficulty, and total research cost.

Acceptance: demand, delivery timing, and product mix explanations can be compared without claiming causal identification. An unsupported preference remains an assumption or unresolved judgment.

### CHK — Financial consistency checks

Priority: P0 for a bounded rule set. Current status: proposed product capability. Output: reproducible calculations and explainable discrepancy reports.

- [ ] CHK-01 Define typed quantities with exact decimal or suitable bounded arithmetic; document rounding and missing-value behavior for every rule.
- [ ] CHK-02 Check currency, scale, and conversion basis before comparison; record exchange-rate source and date when an authorized conversion is used.
- [ ] CHK-03 Resolve fiscal calendars and distinguish quarter, year-to-date, full year, and trailing periods before performing arithmetic.
- [ ] CHK-04 Check denominators, percentages, percentage-point changes, and per-share bases; preserve the exact inputs and calculation.
- [ ] CHK-05 Implement a small approved catalogue of accounting identities and reconciliation rules with materiality and rounding tolerances.
- [ ] CHK-06 Detect metric redefinitions, segment changes, gross/net presentation changes, and accounting-basis differences that break comparability.
- [ ] CHK-07 Require explicit assumptions for cross-company relationships; do not treat supplier revenue and customer capital expenditure as an accounting equality.
- [ ] CHK-08 Produce a discrepancy card with rule version, source passages, formula, observed difference, tolerance, missing inputs, and reviewer disposition.
- [ ] CHK-09 Recompute affected results after source corrections while retaining the earlier result and its original inputs.
- [ ] CHK-10 Build a reviewed challenge corpus of common financial interpretation errors; report rule-level precision, recall, and unresolved cases.

Acceptance: a quarter-versus-YTD comparison is blocked or explicitly reconciled; missing counterparty coverage is not called a contradiction; another reviewer can reproduce each result from its cited inputs.

### ACT — Evidence selection and research action queue

Priority: P0 deterministic baseline; learning-based selection is P2. Current status: proposed capability. Output: an accountable next-action list.

- [ ] ACT-01 Convert unresolved claims and rival predictions into candidate actions: inspect a disclosure, obtain a permitted field, request review, or wait.
- [ ] ACT-02 Show which uncertainty each action addresses and which alternatives it could distinguish; avoid generic “research more” recommendations.
- [ ] ACT-03 Estimate acquisition cost, review time, availability, and required permissions; separate estimates from subsequently observed costs.
- [ ] ACT-04 Implement a transparent configurable ranking baseline with visible reasons; avoid presenting an uncalibrated score as a probability of truth.
- [ ] ACT-05 Support assignment, due dates, waiting-on-disclosure, blocked-by-access, completed, and no-longer-relevant states with history.
- [ ] ACT-06 Capture action outcomes and reviewer-assessed usefulness, including actions that produced no information or misleading evidence.
- [ ] ACT-07 Allow explicit stopping or abstention with recorded missingness and reason; include these cases in evaluation denominators.
- [ ] ACT-08 Add user-requested alerts for newly available evidence and source changes, with deduplication and configurable delivery; do not create unsolicited outreach.
- [ ] ACT-09 Compare the baseline with chronological/manual queues using reliable resolution, coverage, total cost, and reviewer effort together.

Acceptance: a future disclosure generates a visible waiting state; an action identifies a specific question and source; an unanswered hard case does not count as a saved successful investigation.

### TIM — Research history and information cutoffs

Priority: P0. Current status: local dated inspector exists; product timeline and historical service are unfinished. Output: reproducible as-of investigations.

- [ ] TIM-01 Implement historical queries over immutable source versions using the declared availability policy and selected cutoff.
- [ ] TIM-02 Display publication, first observation, economic period, revision, and processing times separately with timezone and uncertainty.
- [ ] TIM-03 Pin each investigation snapshot to exact source, claim, extraction, rule, model, and reviewer versions.
- [ ] TIM-04 Build a timeline of claim changes, source corrections, target amendments, reviews, and outcome transitions.
- [ ] TIM-05 Add side-by-side comparison of two cutoffs showing added, removed-by-policy, corrected, and still-unresolved evidence.
- [ ] TIM-06 Explain why a source was excluded from a historical view; distinguish later availability, missing date, and entitlement restrictions.
- [ ] TIM-07 Integrate separately retained checkpoints or a trusted timestamping service for selected journals; document what the anchor does and does not authenticate.
- [ ] TIM-08 Define correction behavior for unreliable timestamps without rewriting what the system previously recorded as known.
- [ ] TIM-09 Label historical model replay as potentially affected by information in model training; require future observations for prospective claims.
- [ ] TIM-10 Verify historical query and export against fixtures with delayed discovery, later corrections, backdated source metadata, and timezone boundaries.

Acceptance: a correction observed after the cutoff is absent from the earlier snapshot and visible later; the application explains the availability policy instead of claiming perfect historical knowledge.

### SET — Management commitments and disclosed outcomes dataset

Priority: P0 with narrow coverage. Current status: proposed dataset, not an existing commercial data product. Output: reviewed longitudinal annotations and reproducible exports.

- [ ] SET-01 Freeze the initial universe, disclosure categories, time coverage, inclusion rules, and exclusion rules; publish known coverage gaps.
- [ ] SET-02 Extract explicit management commitments with exact passage, issuer, metric, accounting basis, unit, segment/geography, target range, and horizon.
- [ ] SET-03 Link commitment rows to immutable source versions, availability records, extraction versions, and reviewer records.
- [ ] SET-04 Model amendment, reaffirmation, withdrawal, maturity, and resolution as distinct events linked to the original commitment.
- [ ] SET-05 Match later disclosed outcomes using a written comparability rubric; route metric changes and ambiguous mappings to independent review.
- [ ] SET-06 Produce supported, contradicted, ambiguous, or unresolved labels with reasons; preserve disagreement and the adjudication trail.
- [ ] SET-07 Enforce that withdrawal is not automatically failure, missingness is not a negative outcome, and a redefined metric is not automatically comparable.
- [ ] SET-08 Compute clearly defined derived fields such as target revisions and deviation from a comparable original range; expose formulas and unavailable values.
- [ ] SET-09 Build versioned snapshots and stable row IDs; allow filtered CSV/JSON downloads and reproducible programmatic queries.
- [ ] SET-10 Publish a dataset card covering coverage, annotation rules, quality estimates, corrections, source restrictions, and prohibited interpretations.
- [ ] SET-11 Add correction reports, dispute submission, and affected-row lookup; keep old snapshots reproducible while displaying later corrections.
- [ ] SET-12 Validate researcher usefulness and source entitlements before commercial distribution; test whether teams repeatedly use the data for a specific analysis.

Acceptance: a researcher can reproduce a row from its evidence and rules, distinguish original and revised targets, and recover the same snapshot. The product describes new annotations and measurements, not newly created market facts or guaranteed investment returns.

### SCI — Scientific evaluation and accountable improvement

Priority: P0 for any advertised scientific evaluation. Current status: local kernel implemented; product integration and independent scientific validation pending. Output: inspectable studies with defensible interpretations.

- [ ] SCI-01 Integrate the existing study manifest into a guided workflow covering population, sampling unit, target, loss, effect margin, and model identities.
- [ ] SCI-02 Keep the current paired binary-probability evaluation within its supported scope; reject composite scores and undefined targets as probability inputs.
- [ ] SCI-03 Commit both predictions and evidence identities before eligible outcomes become available; preserve ordering and pending-outcome constraints.
- [ ] SCI-04 Authenticate adjudicators, document conflicts, and retain the outcome evidence; prevent the candidate system from unilaterally assigning its own success.
- [ ] SCI-05 Expose hypothesis-family membership, error allocation, minimum and maximum sample, stopping rules, invalidations, and inconclusive outcomes.
- [ ] SCI-06 Maintain a study-attempt registry so retries, renamed families, and unsuccessful experiments remain visible; define cross-study governance before broad adaptive use.
- [ ] SCI-07 Connect journal export, semantic replay, numerical replay, and independent checkpoints to the application and its review process.
- [ ] SCI-08 Display conditional statistical evidence separately from operational approval, causal benefit, calibration, and financial performance.
- [ ] SCI-09 Add only diagnostics with their assumptions attached; fixed-family multiple-testing adjustment, isotonic projection, and preference cycles are not truth certificates.
- [ ] SCI-10 Commission a qualified independent review of the statistical contract, sampling design, implementation, and interpretation before publishing guarantee claims.
- [ ] SCI-11 Run prospective comparisons with strong baselines and issuer/event clustering accounted for; predefine appropriate procedures for endpoints outside the current kernel.
- [ ] SCI-12 Evaluate improvement per total review effort, error, coverage, and cost; keep failures and distribution changes visible after an earlier favorable result.

Acceptance: an inconvenient pending outcome cannot disappear; changing a study name cannot erase past attempts; a successful computation or evidence threshold never automatically trades, deploys, or certifies truth.

### COM — Research Commons Guard: capacity and source integrity

Priority: P1 supporting feature; shared source lineage also supports core research. Current status: bounded local planner implemented. Output: a usable review queue that preserves provenance and human review capacity.

- [ ] COM-01 Connect incoming claim packets to shared evidence and claim objects; preserve exact source-root identities rather than inventing a second provenance system.
- [ ] COM-02 Persist duplicate groups across ingestion runs with idempotent membership updates; distinguish exact duplication from unverified semantic similarity.
- [ ] COM-03 Show shared primary roots and unknown ancestry; do not count many summaries of one source as independent corroboration.
- [ ] COM-04 Propagate declared disputes and withdrawals through aliases and dependencies; retain the original source and reasons for quarantine.
- [ ] COM-05 Add authenticated contributor identities and admission limits; document remaining collusion and identity-abuse limits.
- [ ] COM-06 Replace assumed review costs with estimated and observed minutes; include triage, quarantine investigation, corrections, and coordination.
- [ ] COM-07 Integrate contributor caps, review budgets, and a separately reserved practice allocation into a persistent daily or session queue.
- [ ] COM-08 Define queue rollover, cancellation, partial work, urgent review, and budget changes explicitly; log overrides rather than silently erasing backlog.
- [ ] COM-09 Preserve useful smaller tasks when one task exceeds available capacity; display both selected work and reasons for deferral.
- [ ] COM-10 Provide manual dispute resolution and appeals with reviewer identity; avoid treating an automated quarantine as a verdict of misconduct.
- [ ] COM-11 Record backlog age, repeated roots, unique claims, estimated versus actual effort, and review completion without equating document volume with productivity.
- [ ] COM-12 Compare the integrated queue with a conventional queue using actual review effort, error, coverage, and contributor participation.

Acceptance: twenty copies of one claim do not create twenty independent supports or lower its recorded review cost; renaming a withdrawn artifact does not clean its lineage; protected practice time is not automatically borrowed by production work.

Current boundary: the local planner handles up to 64 sources and 256 packets per supplied snapshot. It is not yet a persistent admission service, semantic fact checker, or proven optimal scheduler. Distinct primary artifacts do not prove independent information.

### PRC — Independent Practice: protect the capacity to judge

Priority: P1, the third part of Research Commons. Current status: local attempt-before-comparison workflow implemented. Output: an optional research practice workflow with auditable attempts and later assessment.

- [ ] PRC-01 Choose suitable, bounded financial-research tasks with a qualified reviewer; do not assume every withheld answer creates meaningful practice.
- [ ] PRC-02 Freeze the question, source scope, task identity, and comparison digest before a session opens.
- [ ] PRC-03 Build an evidence-reading and reasoning view that allows an unaided attempt before the normal comparison view becomes available.
- [ ] PRC-04 Require a judgment, supporting reasoning, relevant source references, and an explicit unresolved option; record assistance and prior exposure as declarations.
- [ ] PRC-05 Preserve the attempt without replacement; record later revisions as separate reflection rather than rewriting the original response.
- [ ] PRC-06 Separate question and comparison storage permissions where genuine confidentiality is required; do not describe the local CLI ordering check as access control.
- [ ] PRC-07 Reveal a clearly labeled comparison and support discussion; distinguish an unadjudicated model answer from an independently reviewed reference.
- [ ] PRC-08 Add optional reflection, reviewer feedback, and exportable records; protect participant privacy and avoid unsupported employee capability rankings.
- [ ] PRC-09 Design delayed, unaided assessment with consent, suitable tasks, and a comparator workflow; measure accuracy and reasoning transfer, not only assisted task scores.
- [ ] PRC-10 Retain journal replay and independently held checkpoints; document that records alone cannot prove human authorship, no outside assistance, or research originality.

Acceptance: the workflow rejects an early comparison reveal, preserves the original attempt, and does not call answer agreement a learning gain. A claim of researcher development requires delayed independent assessment.

### SHD — Distillation Shield: a bounded evidence boundary

Priority: P1 as a supporting module; mandatory for any route advertised as Shield-backed. Current status: local byte-verification and bounded parsing implemented. Output: an enforced input boundary with clear trust ownership.

- [ ] SHD-01 Document trusted approval roots, untrusted inputs, source owners, executable identity, and the exact outputs that cross the boundary.
- [ ] SHD-02 Provision approved pins through a separately controlled process; the submitting agent must not be able to approve its own evidence bundle.
- [ ] SHD-03 Add approval identity, expiry, rotation, revocation, and retrieval records without weakening exact-byte matching.
- [ ] SHD-04 Preserve strict JSON validation, duplicate-key rejection, numerical constraints, depth limits, and documented input and file budgets.
- [ ] SHD-05 Preserve safe relative-file access and rejection of escaping paths, symbolic links, inappropriate file types, and unstable reads.
- [ ] SHD-06 Keep evidence bodies inert during verification; expose only typed fields, fixed result codes, and permitted references to privileged callers.
- [ ] SHD-07 Place the verifier in an operating-system and service boundary with resource limits, least privilege, and controlled network and secret access.
- [ ] SHD-08 Wire production routes to fail closed on rejection; prohibit fallback to an unshielded evaluator under the same protected API promise.
- [ ] SHD-09 Protect approval and audit stores from tenant crossover and untrusted writes; record administrative changes and emergency revocations.
- [ ] SHD-10 Test parser exhaustion, tampering, stale approvals, unsafe files, malicious instruction text, and compromised approval inputs at the integrated boundary.
- [ ] SHD-11 Keep source authentication and factual adjudication as separate checks; a correctly approved false document must remain a documented possible failure.
- [ ] SHD-12 Obtain independent security review for the actual deployed architecture before making product security claims; publish the supported threat model and limits.

Acceptance: changed bytes and unsafe paths are rejected; instruction text cannot grant tool authority through the verifier; the UI says what was verified. `VERIFIED_BYTES_ONLY` never means “true,” “safe against all AI,” or “human benefit established.”

The current limits include 2 MiB input, 128 KiB seal, 64 evidence files, 8 MiB per file, and 32 MiB total evidence bytes. Preserve or deliberately revalidate those bounds. “Distillation Shield” is a product name; the current mechanism does not distill a model or provide universal attack immunity.

### EVO — Evolution Evidence Audit: prepare for faster AI change

Priority: P1. Current status: local configuration and review audit implemented. Output: version-specific evidence applicability, review gaps, and relevant financial commitments.

- [ ] EVO-01 Connect the eight-part inventory: model, agent code, tool policy, memory, data, runtime, grader, and evaluation data.
- [ ] EVO-02 Measure actual runtime and deployment identities where available; mark mutable provider aliases and unavailable identities as unresolved rather than inventing hashes.
- [ ] EVO-03 Record version ancestry, dependency changes, and authority changes; validate supplied graph completeness against the institution's inventory.
- [ ] EVO-04 Reuse evaluation evidence only when its dependency scope, fingerprint, protocol, and validity period still apply; explain each reuse decision.
- [ ] EVO-05 Authenticate model improvers, reviewers, graders, test custodians, and release authorizers; check relevant conflicts through ancestry.
- [ ] EVO-06 Track protected-test access; revoking access does not erase previous exposure, and a new digest alone does not prove semantic test freshness.
- [ ] EVO-07 Keep matching failures open until an authorized resolution process addresses them; a later pass, expiry, or renamed protocol cannot silently erase failure.
- [ ] EVO-08 Show current unreviewed transitions, evidence age, and unresolved review gaps; distinguish retrospective review from evidence available at a historical release.
- [ ] EVO-09 Link supplied financial commitments to configuration versions and review gaps; group by currency and show unknown amounts separately.
- [ ] EVO-10 Add a separately trusted deployment controller only for institutions that authorize enforcement; the audited agent cannot alter the gate, its rules, or approvals.
- [ ] EVO-11 Provide change-diff views, targeted reevaluation requests, independent review exports, and explicit unknown-inventory findings.
- [ ] EVO-12 Evaluate missed material changes, unnecessary reevaluation, review delay, and identity failures using real controlled version changes and a strong baseline.

Acceptance: a memory or tool-policy change invalidates the relevant evidence; an unrelated change can retain scoped evidence; a grader controlled by an ancestor improver creates a conflict; financial commitments are not labeled predicted losses.

This is preparedness for changing financial-AI systems. It is not a detector of global recursive self-improvement, an AGI countdown, or proof that a model can safely self-modify. The current version model has a single parent; branching/merging requires an explicit later schema and validation decision.

### CTL — Human Control Exit Audit

Priority: P1 optional institutional module. Current status: read-only local audit implemented. Output: evidence about whether a defined human stop request was respected along declared action paths.

- [ ] CTL-01 Select one financial-AI workflow and define the stop request, responsible people, affected capabilities, downstream paths, and service scope.
- [ ] CTL-02 Integrate authenticated stop-drill records with baseline, request time, deadline, observation window, clock bounds, and evidence ownership.
- [ ] CTL-03 Inventory reachable tools, delegated agents, scheduled jobs, credentials, and external commitments relevant to the declared stop scope.
- [ ] CTL-04 Distinguish observed activity after the deadline, no observed activity under sufficient coverage, and inadequate observation; preserve clock uncertainty.
- [ ] CTL-05 Track residual commitments and outstanding actions by currency and status; retain unknown amounts instead of treating them as zero.
- [ ] CTL-06 Display path-level findings, missing evidence, evidence age, and responsible follow-up roles; do not condense everything into an unsupported safety score.
- [ ] CTL-07 Run institution-authorized drills with an independent observer and retained artifacts; avoid treating a supplied success statement as authenticated evidence.
- [ ] CTL-08 Define how findings reach existing operational controls and responsible humans; this audit itself remains read-only unless a separate control integration is explicitly authorized.
- [ ] CTL-09 Compare findings against the institution's existing procedure and independent observations; measure missed activity, false alarms, review effort, and response delay.

Acceptance: an unobserved downstream path appears as a gap; continuing activity is not hidden by a successful parent stop; the product never equates “no logged activity” with proof of shutdown.

### RES — Human Option Reserve

Priority: P1 optional institutional module. Current status: bounded local optimizer implemented; human benefit not established. Output: an evidence-conditioned fallback plan for one human-operated critical service.

- [ ] RES-01 Choose one institution-owned mission with measurable minimum capacity, duration, activation deadline, and responsible operator.
- [ ] RES-02 Define relevant disruption scenarios, including shared dependencies and failures of services that a purported human fallback still requires.
- [ ] RES-03 Inventory candidate routes, required projects, direct and transitive dependencies, maintenance obligations, and evidence owners.
- [ ] RES-04 Collect authenticated drills covering capacity, duration, activation, and freshness; preserve missing, stale, or contradicted evidence.
- [ ] RES-05 Record project costs, recurring commitments, available budget, and financing assumptions; a supplied budget is not proof of available funds.
- [ ] RES-06 Integrate the exact minimum-cost planner within its declared bounds; preserve the distinction between a complete plan, a funding shortfall, and no supported plan.
- [ ] RES-07 Show shared projects, scenario coverage, unsupported routes, sensitivity to missing dependencies, and diagnostic partial solutions.
- [ ] RES-08 Add maintenance and repeat-drill scheduling with user-configured alerts; invalidate readiness evidence when relevant dependencies or service requirements change.
- [ ] RES-09 Test against an ordinary checklist and spreadsheet with equal evidence and cost accounting; include planning, training, maintenance, and activation effort.
- [ ] RES-10 Measure real service completion, activation time, unserved demand, and cost in qualified drills before claiming benefit; use a design that does not withhold necessary service.

Acceptance: a cheaper route with an omitted critical dependency cannot be accepted as independently validated readiness; a best partial plan is not displayed as a complete supported plan. Budget shortfalls and missing evidence remain explicit.

The current optimizer supports at most 16 projects, 64 routes, 16 scenarios, and 256 dependency nodes. One route must cover the whole mission; it does not pool capacity across routes. Expanding those limits or semantics is separate engineering work. Its computation does not purchase equipment, move funds, or prove protection against catastrophic AI risk.

### UX — One customer workbench

Priority: P0 for core screens; P1 for optional module views. Current status: the six main capabilities do not yet form an integrated customer UI. Output: an accessible English-only research application.

- [ ] UX-01 Create the Thesis Workspace with editable claims, typed assumptions, original sources, rivals, calculations, and unresolved questions in one investigation; use the approved Human Trace logo assets unchanged.
- [ ] UX-02 Add company and cutoff selection with clear corpus coverage and freshness; never imply that a bundled snapshot is a live feed.
- [ ] UX-03 Implement a source drawer opening the exact passage, source version, availability, lineage, and correction status used in a claim.
- [ ] UX-04 Build the Evidence & Review Queue with purpose, assignment, cost, dependencies, waiting states, and review outcomes.
- [ ] UX-05 Build the Dataset Browser with filters for issuer, metric, period, event, comparability, adjudication, missingness, and snapshot.
- [ ] UX-06 Add a history view comparing claim and source versions, including the original frozen prediction beside the eventual outcome.
- [ ] UX-07 Provide an evaluation report with denominator, population, uncertainty, unresolved cases, baselines, study status, and replay download.
- [ ] UX-08 Integrate Commons controls into review work and Practice as an optional mode; avoid using contributor volume as evidence quality.
- [ ] UX-09 Add a Trust & Continuity area for enabled Evolution, Control, Shield, and Reserve functions with scope-specific language and responsible roles.
- [ ] UX-10 Provide useful loading, empty, stale, failed-ingestion, permission-denied, disputed, invalidated, and inconclusive states.
- [ ] UX-11 Verify keyboard navigation, readable tables, focus behavior, screen-reader labels, responsive layouts, and accessible status distinctions.
- [ ] UX-12 Complete usability sessions on the end-to-end journey; test comprehension of uncertainty, corrections, frozen definitions, and the limits of verification badges.

Acceptance: a user can complete the fictional commitment scenario through export without command-line assistance; every material conclusion can be traced to evidence, assumptions, or unresolved status.

### INT — API, storage, jobs, and operations

Priority: P0 core; P1 adapters for optional modules. Current status: local CLI and package behavior verified selectively; full authenticated application integration pending. Output: reliable product services.

- [ ] INT-01 Define versioned API contracts for sources, investigations, claims, actions, timelines, adjudications, studies, dataset snapshots, and optional audits.
- [ ] INT-02 Implement object-level tenant authorization for reads, writes, search, jobs, exports, and audit references; test direct-ID access attempts.
- [ ] INT-03 Define storage ownership and migrations against the actual inherited database; preserve source, claim, and historical ledger identities.
- [ ] INT-04 Build durable ingestion, extraction, correction propagation, review, and export jobs with idempotency, bounded retries, and inspectable failures.
- [ ] INT-05 Resolve concurrent edits and adjudications through explicit version checks or transactions; prevent silent overwrites and duplicate outcome resolution.
- [ ] INT-06 Connect the existing scientific CLI modules through typed adapters; keep process success, audit findings, and scientific conclusion statuses distinct.
- [ ] INT-07 Expose narrowly scoped API or MCP tools for permitted retrieval and research actions; model-generated tool calls must obey the same authorization policy.
- [ ] INT-08 Record operational metrics for latency, job age, correction delay, model/data spend, failures, and source freshness without leaking private content.
- [ ] INT-09 Establish retention, authorized deletion, secret management, dependency updates, and incident procedures suited to the actual deployment. Backup creation, scheduling, restoration, and restore drills are canceled by the owner; preserve existing data and disclose that restoration is not demonstrated.
- [ ] INT-10 Set realistic load and cost targets from the intended pilot workload; test representative documents, concurrent reviews, and large allowed exports.
- [ ] INT-11 Run inherited application/database regressions and authenticated integration tests alongside the selected science tests; complete remote CI and package checks.
- [ ] INT-12 Rehearse safe application-code rollback and interrupted-write/export handling with compatible additive migrations and transactions; reject destructive or unsupported data transitions. Do not add backup restoration or imply lost-data recovery.

Acceptance: unauthorized access is denied across all interfaces; retried jobs do not create duplicate outcomes; the integrated application passes its relevant database and API checks, not only the local science suite.

### VAL — Demonstrate customer value and human benefit

Priority: P0 for core claims; P1 for module-specific benefit claims. Current status: constructed engineering demonstrations exist; field effectiveness and customer demand are unestablished. Output: auditable evidence that can support or reject product claims.

- [ ] VAL-01 Prepare a concrete pilot protocol for one repeated financial-research task and three to five candidate teams; recruitment requires later explicit outreach authorization.
- [ ] VAL-02 Fix eligible tasks, exclusion rules, material-error rubric, outcome definitions, minimum useful effects, and analysis procedures before final evaluation.
- [ ] VAL-03 Compare the incumbent workflow, retrieval with citations, retrieval plus skeptical review, and YuClaw using matched permissible evidence and measured total resources.
- [ ] VAL-04 Estimate sample size from an excluded pilot; account for issuer/event dependence and avoid treating many claims from one disclosure as independent trials.
- [ ] VAL-05 Use independent adjudication and blinded comparison where feasible; retain disagreements, missing outcomes, integration failures, and abstentions.
- [ ] VAL-06 Measure extraction precision/recall, scope and unit errors, material errors, answer coverage, correction effort, elapsed time, and total cost.
- [ ] VAL-07 Test the proposed 30% median review-time reduction target only with predeclared quality and coverage floors; report uncertainty and failed targets.
- [ ] VAL-08 Measure repeat use, completed investigations, dataset reuse, paid-pilot conversion, and renewal separately; do not infer demand from compliments or demos.
- [ ] VAL-09 Evaluate Commons and Practice using actual review capacity and delayed unaided judgments; do not substitute queue compression for learning or time savings.
- [ ] VAL-10 Evaluate Evolution and Control against independently observed changes and drill outcomes; include missed events, false alarms, and review costs.
- [ ] VAL-11 Evaluate Reserve through qualified service drills and the full chain from finding to corrective action to service outcome; include opportunity costs and adverse effects.
- [ ] VAL-12 Publish an internal evidence table stating supported, unsupported, and contradicted claims; revise product scope when benefits disappear under fair comparison.

Acceptance: a measured product claim names its population, comparator, denominator, uncertainty, and evaluation version. A feature may pass software verification and still fail the customer or human-benefit gate.

### REL — Release, documentation, and commercial readiness

Priority: P0 for enabled release scope. Current status: local preview, no deployment or outreach. Output: a reviewable release package and a separate release decision.

- [ ] REL-01 Confirm v7 completion and the exact inherited baseline before final v8 integration; do not alter the agreed v7 feature set.
- [ ] REL-02 Freeze enabled v8 capabilities and clearly label unavailable or experimental modules; remove unsupported claims from all product surfaces.
- [ ] REL-03 Prepare English-only onboarding, task examples, API documentation, dataset cards, limitations, accessibility guidance, and operator runbooks; use the approved Human Trace identity without redesign.
- [ ] REL-04 Verify corpus/source permissions, customer isolation, export terms, retention configuration, and correction procedures for the actual release scope.
- [ ] REL-05 Complete relevant integration, security, statistical, performance, recovery, and usability reviews; retain unresolved findings with an explicit release disposition.
- [ ] REL-06 Package reproducible builds, migrations, rollback instructions, release notes, verification evidence, and a capability-status matrix.
- [ ] REL-07 Prepare a pricing hypothesis from observed costs and willingness to pay; offer a narrowly specified deliverable rather than promising alpha or universal AI protection.
- [ ] REL-08 Prepare private, reviewable launch materials and community-specific drafts; include only measured claims and verified capability descriptions.
- [ ] REL-09 Keep deployment and community posting disabled until the user explicitly authorizes the concrete v8 release and outreach scope; no automatic resume.
- [ ] REL-10 After separate launch authorization, monitor onboarding failures, quality, corrections, costs, and retention; use predefined rollback or feature-disable conditions.

Acceptance: the release package describes exactly what is enabled and supported. An unfinished optional module stays disabled; it does not block the core solely because it exists on this backlog. User authorization remains a distinct final release step.

### RND — Scientific extensions after a reliable baseline

Priority: P2. Current status: research proposals, not implemented or promised. Output: experiments and decisions rather than speculative launch claims.

- [ ] RND-01 Test whether learned evidence selection improves reliable resolution per total cost over the deterministic queue at fixed coverage and error targets.
- [ ] RND-02 Test dependence-aware source selection against repeated-agent and source-diverse baselines; measure added information rather than agreement counts.
- [ ] RND-03 Investigate stopping and abstention rules with explicit sampling and dependence assumptions; do not transplant unrelated theoretical guarantees.
- [ ] RND-04 Test whether financial contradictions predict future adjudicated errors beyond simple retrieval and rule-based baselines.
- [ ] RND-05 Explore extension of the statistical contract to required nonbinary outcomes and cross-study error governance with qualified methodological review.
- [ ] RND-06 Evaluate richer evolution ancestry or pooled fallback capacity only after a real user requirement and explicit semantics justify the additional complexity.
- [ ] RND-07 Assess privacy-preserving aggregate research only if a permitted cross-tenant use case exists; hashing is not differential privacy and private data is not shared by default.
- [ ] RND-08 Conduct a fresh primary-source prior-art review before any originality claim; publish reproducible comparisons and negative findings before asserting a breakthrough.

Acceptance: each extension has a falsifiable hypothesis, a strong baseline, a fixed evaluation protocol, and a decision to keep, revise, or stop. It does not silently expand the advertised v8 scope.

## 6. Permissions and review responsibilities

| Role | Intended powers | Boundary |
|---|---|---|
| Researcher | Create investigations, suggest claims, inspect entitled evidence, propose predictions | Cannot rewrite frozen history or self-certify independent evaluation |
| Reviewer | Review claims and outcomes within assigned scope; record disagreement | Identity and conflicts must be recorded; a label alone does not prove independence |
| Data steward | Ingest and correct source records; maintain provenance and entitlements | Corrections are versioned; publisher assertions are not independently established facts |
| Study owner | Propose manifests and manage eligible study workflow | Cannot erase unfavorable attempts, change frozen targets, or bypass pending outcomes |
| Security/approval custodian | Maintain Shield approvals and separately controlled verification configuration | Submitting agents cannot control their own trust roots |
| Institutional operator | Supply inventories and drills; act through separately authorized operational systems | Audit output alone does not authorize shutdown, spending, or deployment |
| Release owner | Review evidence and prepare an enabled release scope | User launch/publication authorization is still required |
| Customer administrator | Manage tenant membership and authorized module configuration | No cross-tenant access or permission to alter immutable shared evidence history |

Use least privilege and explicit delegation. For a small team, roles may share personnel where appropriate, but an independence claim requires actual separation in the relevant evaluation. Record exceptions instead of pretending they do not exist.

## 7. Integration contract and initial endpoints

These are proposed resource contracts to map onto the released v7 architecture, not claims that endpoints already exist. Prefer inherited naming and authentication conventions when suitable.

| Resource family | Required operations | Important constraint |
|---|---|---|
| Sources / evidence spans | Ingest, inspect exact version, fetch permitted passage, record correction | Original bytes and entitlements remain traceable |
| Investigations / claim versions | Create, edit draft, link dependencies, freeze, inspect history | Optimistic concurrency or equivalent protects simultaneous edits |
| Rival hypotheses / checks | Propose, review, compare, reproduce calculation | Generated suggestions do not silently become reviewed facts |
| Research actions / reviews | Assign, wait, complete, dispute, record cost and result | Retries are idempotent and every transition is attributable |
| Historical snapshots | Create or query cutoff view, compare versions, explain exclusions | Later evidence is not silently available in an earlier snapshot |
| Commitments / outcomes | Record lifecycle event, adjudicate, correct, query | Original target and unresolved status are preserved |
| Dataset snapshots / exports | Freeze selection, download permitted rows, verify manifest | A snapshot is reproducible and bound to schema and rights |
| Studies / predictions / resolutions | Register, commit, independently resolve, invalidate, export/replay | Supported statistical scope and timing constraints are enforced |
| Commons / practice | Allocate review, inspect lineage, commit attempt, reveal, reflect | No hidden permission escalation through a convenience endpoint |
| Shield / evolution / control / reserve | Verify input, run scoped analysis, inspect findings, export evidence | Findings are distinct from external operational actions |

Every API needs stable IDs, schema version, tenant authorization, input validation, status semantics, bounded pagination, audit events, and documented error behavior. Sensitive background jobs must recheck entitlements when producing their final outputs. Export formats must carry the snapshot, data dictionary, missing-value rules, and correction references.

## 8. Release sequence and measurable gates

The sequence is driven by evidence and dependencies, not a predicted AGI date or an assumed two-week delivery date for v7.

| Gate | Required demonstration | Failure response |
|---|---|---|
| A — Scope and inherited interfaces | Agreed v8 scope; actual v7 interface inventory; English-only controls; separate release path | Resolve adapters or scope before integrating |
| B — One complete research journey | A reviewed commitment travels from source to typed claim, comparison, calculation, history, adjudication, and reproducible export | Complete the missing workflow; do not call isolated commands a finished product |
| C — Evidence and data quality | Representative extraction/reconciliation checks; provenance/correction behavior; rights and tenant tests; independently reviewed labels | Reduce coverage or repair data definitions |
| D — Application and scientific assurance | Relevant API/database/CI checks; interrupted-write safety and safe code rollback; reviewed statistical scope; complete replay and audit records; explicit disclosure that backup/restore functionality is canceled and restore is not demonstrated | Correct the failure or disable the affected claim/capability; do not reinstate backup requirements |
| E — Controlled core pilot | Predeclared quality/coverage/cost endpoints with strong baselines and independent adjudication | Revise the workflow or narrow the value proposition |
| F — Optional module readiness | Each enabled module passes its own integrated engineering gate; claimed operational benefits have supporting field evidence | Keep it disabled or explicitly experimental without benefit claims |
| G — Release decision | Reviewable build, documentation, support/rollback plan, v7 completed, explicit user readiness authorization | Keep launch and outreach paused |

The first pilot can use a small, explicitly selected corpus. Wider coverage, unattended automation, and paid distribution each require appropriate additional evidence; they are not inferred from a successful demonstration.

For 8.0.0, apply the scope freeze's gate mapping: A/B/C/D/G remain applicable; E's real-user pilot is deferred and F remains pending for default-off experimental modules. The v7-only Gate #15 exception is not inherited. Gate applicability and any unmet requirement must remain explicit at the v8 release decision. Canceling backups changes that requirement; it does not certify recovery capability.

### What must be built first

1. Inventory the inherited v7 architecture and freeze shared source, claim, and outcome contracts.
2. Build one exact-source ingestion path and one editable claim workflow.
3. Add the narrow financial rule set and original-versus-revised commitment lifecycle.
4. Connect historical views, independent adjudication, and versioned export.
5. Add the initial rival comparison and transparent next-action queue.
6. Integrate the scientific kernel and complete the customer workbench.
7. Validate the core workflow, then enable supporting modules as their gates pass.
8. Prepare the complete release package for the separate launch decision.

Parallel preparation is appropriate for designs, data dictionaries, threat models, pilot protocols, and optional module adapters. It must not turn into unreviewed production changes to v7.

## 9. Evidence required for the benefits we want

| Intended benefit | Observation needed | What is insufficient |
|---|---|---|
| Better financial research | Lower independently adjudicated material error at acceptable coverage and cost, or a justified quality/cost tradeoff | More text, more citations, or more agents agreeing |
| Useful new research data | Reproducible longitudinal rows, reviewed comparability, documented coverage, repeated use for an actual research task | A synthetic example, extracted text alone, or an unvalidated universal score |
| More efficient review | Measured total effort including triage, correction, and administration with quality retained | Deduplicating twenty synthetic packets and calling it twenty reviews saved |
| Preserved independent judgment | Suitable delayed unaided assessment with an appropriate comparator and participant safeguards | A timestamped attempt or higher performance while AI is available |
| Safer configuration changes | Fewer missed material changes or conflicts at acceptable review overhead in observed integrations | A version graph or a successful audit exit code |
| More credible human control | Independent observation of scoped stop behavior and complete enough downstream coverage | A parent's success message or absence of logs |
| Better service continuity | A correct finding leads to a responsible action and a fallback that improves measured service outcomes at defensible cost | A minimum-cost plan from incomplete declared dependencies |
| Commercial traction | Actual repeat use, authorized paid pilots, conversion, and renewal | Community interest, compliments, or claims that innovation guarantees customers |

The continuity benefit chain is: **authentic evidence → correct finding → responsible action → maintained capability → effective activation → improved service outcome**. Each link needs evidence. Software verification primarily addresses parts of the first two links.

For the core pilot, the previously proposed 30% reduction in median review time is a candidate target, not an achieved result or an immutable commitment. Set quality, coverage, uncertainty procedures, and the minimum useful effect before collecting final evaluation data. Do not let a favorable time result conceal lower reliability or excessive abstention.

## 10. How the research changes the design

| Inspiration from the existing research | Concrete v8 consequence | Boundary |
|---|---|---|
| Weijie Su: precise formulation, selection, dependence, evaluation and stopping | Typed claims; explicit study families; prospective commitments; source-overlap records; accountable stopping | A theorem's assumptions do not automatically hold for financial research or adaptive agents |
| Research on calibration and preference inconsistency | Separate probabilities from scores; retain disagreement and cyclic preferences; evaluate appropriate endpoints | Better Brier loss is not by itself a proof of calibration or investment value |
| Discussions of accelerating AI development and RSI | Bind review evidence to actual versions, dependencies, authorities and protected evaluation data | An API name, release cadence, or report of AI-assisted research does not certify unrestricted recursive self-improvement |
| Xinyi Yuan's concerns about paralysis, pollution, and suppression | Commons review capacity; primary-source lineage; protected independent practice | Source integrity does not prove truth; protected practice does not establish learning or originality |
| Human-control and resilience research | Scoped stop evidence and an evidence-conditioned fallback plan | YuClaw has not established prevention of catastrophic AI harm or benefit to all humanity |

The research index and notes do not claim that every paper was fully verified, or that any text was reread hundreds of times. The defensible contribution is the operational system and its measured results. Intellectual inspiration does not imply endorsement by any researcher, organization, or declaration.

## 11. Commercial product shape to validate

The initial buyer hypothesis is a research team that repeatedly interprets company disclosures, or a team evaluating financial-AI outputs. The first deliverable to test is one completed research workflow plus its exportable commitments/outcomes data.

Three possible offers should be tested rather than assumed:

1. **Research Workspace:** investigations, evidence review, claim history, calculations, and exports for recurring team work.
2. **Research Dataset:** reviewed commitment/outcome snapshots and programmatic delivery, subject to source and annotation rights.
3. **Institutional Audit Modules:** optional configuration, control, and continuity evidence tools integrated with the customer's existing systems.

Packaging and price depend on actual recurring use, integration cost, source cost, support effort, and willingness to pay. These are proposed offers, not existing tiers, revenue forecasts, or commitments to build three separate products.

A core commercial decision is whether users principally value the workflow, the derived data, or the audit integration. Collect that evidence before widening coverage or adding speculative feature families.

## 12. Decisions and capabilities deliberately left open

- Exact initial issuer universe, disclosure types, and paid source access.
- Actual released v7 interfaces, reusable UI components, and database ownership.
- Named owners, available engineering/reviewer capacity, and credible calendar estimates.
- Independent reviewers, pilot institutions, and consented practice participants.
- Production deployment target, trusted checkpoint provider, and key-custody arrangement.
- Minimum pilot sample, formal uncertainty procedures for each endpoint, and justified noninferiority margins.
- Commercial packaging, price, and the authorized future launch/outreach scope.

These are decision items to resolve during implementation. This planning request does not require interrupting the user to approve them now.

The v8 launch backlog does not include autonomous trading, agent-authorized deployment, unrestricted self-modification, a universal market simulator, a global AGI detector, a blanket management credibility score, a plagiarism verdict engine, or a guarantee against AI attacks. Each would require a separate product decision and substantial evidence beyond the present work.

## 13. Source and verification map

This checklist is a synthesis of the local project record. The linked research reports contain original references, attribution, source versions, and the limitations of the earlier reading. No current competitor or market-price assertions are needed for this implementation plan.

| Record | What it supports |
|---|---|
| [Product vision](../yuclaw-brain/docs/v8/PRODUCT_VISION.md) | Mission, six core capabilities, first dataset, initial validation and v7/v8 separation |
| [Implementation overview](../yuclaw-brain/docs/v8/README.md) | Actual commands and local implementation boundaries |
| [Scientific design](../yuclaw-brain/docs/v8/SCIENCE.md) | Su-inspired formulation, implemented statistical contract, research questions and limitations |
| [Publication catalogue](../yuclaw-brain/docs/v8/su_publications.json) and [reading notes](../yuclaw-brain/docs/v8/reading_notes.json) | Bibliographic coverage and paper-specific reading scope |
| [Control audit](../yuclaw-brain/docs/v8/CONTROL_AUDIT.md) and [control research](../yuclaw-brain/docs/v8/HUMAN_CONTROL_RESEARCH.md) | Scoped stop-evidence design and evidence limits |
| [Reserve design](../yuclaw-brain/docs/v8/HUMAN_OPTION_RESERVE.md) and [reserve research](../yuclaw-brain/docs/v8/HUMAN_OPTION_RESEARCH.md) | Bounded continuity planner, assumptions and proposed pilot |
| [Benefit evaluation](../yuclaw-brain/docs/v8/BENEFIT_EVALUATION.md) | Tested limitations, missing causal chain, and human-benefit status |
| [Distillation Shield](../yuclaw-brain/docs/v8/DISTILLATION_SHIELD.md) | Implemented input verification, resource bounds, trust assumptions and residual risks |
| [Evolution audit](../yuclaw-brain/docs/v8/EVOLUTION_AUDIT.md) and [RSI research](../yuclaw-brain/docs/v8/RSI_RESEARCH.md) | Configuration review semantics, research interpretation and limits |
| [Commons design](../yuclaw-brain/docs/v8/RESEARCH_COMMONS.md) and [Commons research](../yuclaw-brain/docs/v8/RESEARCH_COMMONS_RESEARCH.md) | Review allocation, lineage, practice workflow and effectiveness boundaries |
| [Release notes](../yuclaw-brain/docs/v8/RELEASE_NOTES.md) | Evolution of the local preview |
| [a6 verification](../yuclaw-brain/output/commons-verification.json) | Recorded selected test results, installed replays, package checks and nondeployment status |

The companion `v8-backlog.json` is a machine-readable extraction of this checklist. IDs identify planned work; they are not tickets already created in an external project-management system. An unchecked task can reuse existing local implementation while still requiring its stated product integration or evaluation work.
