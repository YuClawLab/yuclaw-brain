# YuClaw v8: AI-related protection and community launch

Reviewed September 14, 2026. Local preview: 8.0.0a6. This document highlights existing v8 scope; it does not add requirements to v7 or authorize publication.

**September 15 scope update:** v7.0.0 is independently verified released. The [8.0.0 scope freeze](V8_0_0_SCOPE_FREEZE.md) governs the next release: one financial-evidence workbench; COM/PRC/SHD/EVO experimental/default-off; CTL/RES and real-world benefit pilots deferred. The eight mechanisms discussed below remain a broader roadmap, not eight enabled 8.0.0 protections. Backup functionality is canceled. September 19 evening is the journey checkpoint; the owner now targets release on September 21 and promotion afterward, as recorded in the [release schedule](RELEASE_SCHEDULE.md). The historical September 14 checks below are not new release evidence.

**Mission: Make financial AI accountable to evidence.**

YuClaw's contribution is scoped evidence protection, accountable review, and human preparedness within financial research and related institutional workflows. The mechanisms below address different failure modes. They must not be presented as a single universal defense against AI attacks or as demonstrated prevention of catastrophic harm.

## Fresh checks and important findings

- Reran the nine selected test files in the science-v8 CI definition: **292 passed in 0.57 seconds** locally.
- Reran the default English-only guard: **37 authored files checked, zero Han-script violations**. This is the guard's selected scope, not a claim about every historical repository file.
- Verified all 12 source digests and six artifact digests recorded in the a6 verification file.
- Verified that the Markdown plan and JSON backlog agree on all 213 tasks.
- Verified that the three approved Human Trace logo files retain their approved hashes.
- Confirmed the outreach record remains **PAUSED_BY_USER**, with **zero sent posts** and **automatic resume disabled**.
- Found that the saved September 11 outreach drafts describe **8.0.0a4 and 178 selected tests**. Those historical drafts must be refreshed against the actual release before posting.

These checks do not include a fresh independent security audit, remote CI execution, full production API/database integration, actual institutional drills, customer trials, or measured human benefit. The complete financial-research customer journey remains integration work.

## Eight protective functions within the existing modules

### 1. Distillation Shield — input tampering and instruction isolation

**Role: direct protection at a narrow input boundary.**

The local verifier checks approved plan/seal/evidence bytes, rejects missing or altered material and unsafe file paths, and enforces bounded parsing. Evidence bodies are treated as opaque bytes, not interpreted as commands or included in model prompts inside this component. Protected reports use constrained data fields rather than supplied prose.

**Human interest:** reduce the chance that manipulated evidence changes a protected analysis or gains instruction authority inside that calculation.

**What currently works:** constructed tests reject modified files, changed plans/seals, unsafe paths, and certain resource-limit violations; instruction-like content has no execution path inside the verifier.

**Boundary:** an approved false document can pass. A compromised host or approval authority is outside this protection. Later feeding the same prose into a privileged model does not inherit the verifier's protection.

**Before shipping this claim:** implement independent approval ownership, expiry/revocation, execution isolation, tenant access checks, enforced protected routes, and integrated adversarial evaluation. Backlog: SHD-01 through SHD-12; DAT-09 and DAT-11; INT-02 and INT-07.

### 2. Evolution Evidence Audit — outdated reviews and conflicted evaluation

**Role: detect review gaps around changing AI configurations.**

The audit follows declared versions of the model, agent code, tool policy, memory, data, runtime, grader, and evaluation data. Relevant dependency or authority changes invalidate old support. It checks declared reviewer/improver conflicts, retained hidden-test exposure, and unresolved failures.

**Human interest:** make it harder for an altered financial-AI configuration to inherit an inapplicable review result or claim success through a conflicted evaluation process.

**What currently works:** local tests cover changed memory/tools/graders, inherited authority conflicts, test exposure, failure preservation, and selective reuse of unaffected evidence.

**Boundary:** identities and runtime digests are supplied declarations. The auditor is read-only; it neither detects global RSI nor prevents deployment by itself.

**Before shipping this claim:** bind to actual running versions, authenticate relevant authorities, protect evaluation data, test real controlled changes, and use a separately trusted controller if enforcement is offered. Backlog: EVO-01 through EVO-12.

### 3. Human Control Exit Audit — incomplete stop behavior

**Role: audit evidence of continued activity after a human stop request.**

The audit examines supplied stop-drill traces, downstream paths, deadlines, observation windows, timing uncertainty, and residual financial commitments. Stopping a parent does not establish that its delegates stopped.

**Human interest:** expose gaps that responsible operators can address before relying on an emergency stop procedure.

**What currently works:** local tests distinguish observed continuation, incomplete observation, uncertain timing, and outstanding commitments.

**Boundary:** it does not revoke credentials, terminate agents, or verify that supplied records are authentic. Absence of activity in incomplete logs is not proof of shutdown.

**Before shipping this claim:** connect authenticated records, inventory downstream execution paths, conduct authorized independently observed drills, and define who acts on findings. Backlog: CTL-01 through CTL-09.

### 4. Research Commons: source lineage — evidence pollution and manufactured corroboration

**Role: preserve source lineage and visible disputes.**

The Commons planner groups duplicate claims by declared claim and source-root identities. It propagates known disputes and withdrawals through aliases and identifies unknown or conflicting provenance.

**Human interest:** prevent large volumes of repeated material from appearing to be many independent sources and keep known evidence problems visible to reviewers.

**What currently works:** constructed cases group twenty echoes, preserve withdrawn-source problems after renaming, and quarantine inconsistent supplied lineage.

**Boundary:** it does not establish factual truth, discover every semantic duplicate, or prove that distinct primary artifacts contain independent information.

**Before shipping this claim:** integrate durable lineage, authenticated contributor records, correction/retraction updates, review and appeals, and real-corpus evaluation. Backlog: DAT-07 and DAT-08; COM-01 through COM-05 and COM-10.

### 5. Research Commons: review allocation — review overload

**Role: allocate a finite human review budget.**

The local planner groups repeated work, applies declared contributor limits, reserves practice time, and shows backlog. An oversized task need not prevent a later smaller task from fitting.

**Human interest:** preserve attention for useful review when AI-assisted production creates more material than people can inspect.

**What currently works:** bounded snapshot tests verify allocation rules, duplicate cost handling, contributor limits, and retained practice capacity.

**Boundary:** this is not a live rate limiter, network denial-of-service defense, or proven time-saving intervention. Contributor identities and estimated review costs can be wrong.

**Before shipping this claim:** implement persistent admission/rollover, reliable identities, actual effort accounting, logged overrides, and quality/coverage-matched comparison. Backlog: COM-05 through COM-12.

### 6. Independent Practice — preserve independent judgment

**Role: support human skill retention; indirect preparedness.**

The practice workflow freezes a question and records an attempt before this workflow reads the comparison answer. It preserves the original reasoning and enables later comparison and review.

**Human interest:** give researchers a structured opportunity to reason before seeing AI assistance.

**What currently works:** local tests reject early reveal, prevent attempt replacement, and check journal replay and comparison binding.

**Boundary:** this does not prove human authorship, lack of outside assistance, learning, or originality. The local file owner can access material outside the workflow.

**Before shipping a learning-benefit claim:** choose suitable tasks, separate access where confidentiality matters, protect participant privacy, and conduct delayed unaided assessment. Backlog: PRC-01 through PRC-10.

### 7. Human Option Reserve — continuity after a disruption

**Role: plan recovery and service continuity, rather than prevent an attack.**

The planner selects a minimum-cost complete project bundle for one human-operated mission across supplied disruption scenarios, conditional on supplied route, dependency, cost, and drill evidence.

**Human interest:** help a responsible institution identify what it would need to keep one essential service working when normal automation or infrastructure becomes unavailable.

**What currently works:** the bounded local optimizer distinguishes a supported plan under declared assumptions, a funding shortfall, and no supported plan.

**Boundary:** missing dependencies or inadequate scenarios can make a plan misleading. No service outcome, purchasing action, actual funding availability, or protection against catastrophe is established by the calculation.

**Before shipping a human-benefit claim:** independently validate inputs, test an actual institutional mission, compare with ordinary planning, and measure activation, service completion, unserved demand, and total cost. Backlog: RES-01 through RES-10; VAL-11.

### 8. Scientific evidence records — prevent silent rewriting of evaluation history

**Role: research accountability and resistance to misleading improvement claims.**

The existing kernel freezes supported study definitions and prospective predictions, preserves pending outcomes and invalidations, and supports journal replay. The planned product connects these records to typed claims, source versions, and adjudication.

**Human interest:** make it easier to inspect whether a reported improvement used a fixed target and whether unfavorable evidence was retained.

**What currently works:** local statistical-contract and journal tests exercise timing, pending units, immutable definitions, inference state, and replay behavior.

**Boundary:** hashes do not establish truth; a locally replaced journal requires an independently retained checkpoint to expose replacement. The current statistical scope does not apply to arbitrary research claims or every adaptive experiment.

**Before shipping broader claims:** authenticate adjudication, retain checkpoints, review statistical assumptions, maintain related-study history, and complete prospective evaluation. Backlog: SCI-01 through SCI-12; TIM-07.

## The most important integration gaps

1. **Protected calculations are not the whole application.** Distillation Shield currently wraps particular scientific routes. The repository also contains a separate legacy regex-based `InjectionShield`; that text-redaction helper is not the v8 verifier and does not establish application-wide instruction isolation. This review did not certify the complete agent call graph.
2. **Audit findings are not operational controls.** Independent identities, runtime measurement, credential authority, and any deployment/stop enforcement need actual integrations outside the evaluated agent's control.
3. **Declared evidence is not independently authenticated evidence.** Source approval, observation coverage, dependencies, and reviewer independence need trustworthy ownership.
4. **Engineering checks are not field effects.** Maintain separate results for correctness, integrated security, operational effectiveness, researcher learning, and customer value.

The general platform tasks already cover these requirements. Do not add a new “AI-proof” feature label or make all optional modules conditions for finishing v7. Any module advertised at the v8 launch must meet its own release gate; otherwise keep it disabled or clearly limited to an appropriate experimental scope.

## Targeted community launch

Targeted outreach belongs in the v8 release plan. The audience fit below is our assessment based on the official participation pages reviewed today; it is not a promise of acceptance, reach, endorsement, or conversion. These audiences overlap, and they are not interchangeable advertising channels.

| Audience | Why approach it | YuClaw contribution to prepare | Participation route |
|---|---|---|---|
| FINOS AI | Closest connection to financial-services AI governance and the core product | A financial-research walkthrough, version-specific evaluation evidence, and a concrete integration question | Its [AI community entry](https://ai.finos.org/join-us/) offers collaboration and working-group follow-up |
| OWASP AI Exchange | Applied AI security controls and engineering criticism | A self-contained Shield boundary demonstration showing both rejection cases and the approved-false-document limitation | [Contribution guidance](https://owaspai.org/contribute/) and the [Show and tell category](https://github.com/OWASP/www-project-ai-security-and-privacy-guide/discussions/categories/show-and-tell); confirm current moderator expectations |
| AI Village | Practical AI security, red teaming, tools, and reproducible exercises | A safe local lab for tampering, changed-agent review gaps, and incomplete stop evidence | [Discord instructions](https://aivillage.org/discord/): introduce in `#start-here`, obtain the Villager role, then use a suitable permitted research/tool channel |
| OWASP GenAI Security Project | Generative and agentic application security workstreams | A focused implementation note and a question about where the boundary/evaluation work contributes | [Current contributing instructions](https://genai.owasp.org/contributing/) identify Slack access and `#project-genai` for initial routing |

FINOS is the strongest mission fit in this assessment. OWASP and AI Village are strong candidates for technical criticism and external reproduction. Start with one appropriate OWASP venue, then use a separate workstream only where there is a distinct contribution or an invitation.

The FINOS project also describes work on shared financial-services evaluations and retained evidence, making the Evolution and scientific-evaluation integration relevant discussion topics. That is an inference about YuClaw's fit, not an assertion that FINOS has reviewed it. [FINOS evaluation and governance direction](https://www.finos.org/blog/next-phase-finos-ai).

AI Village's participation page prohibits spamming and channel disruption. Share a useful technical resource with an accurate affiliation and follow the channel's current rules. Invitation validity and authenticated posting permissions were not retested during this public-page review. The earlier access observations remain historical and must be checked at launch.

## What to prepare before the release decision

- [ ] Select only capabilities actually enabled and supported in the release.
- [ ] Publishable technical package: immutable release reference, installation instructions, bounded threat model, documented limitations, and a small reproducible demonstration.
- [ ] Core product demonstration: one financial thesis through evidence review, original-versus-revised outcome handling, history, and dataset export.
- [ ] Protection demonstration: changed evidence rejected; a relevant version change requiring review; continued downstream activity shown as a stop gap; source echoes retaining one root.
- [ ] Distinguish synthetic demonstrations from independent security evaluation and real operational findings.
- [ ] Refresh the saved a4 drafts against the actual release version and measured results; never substitute today's 292-test count for future release evidence.
- [ ] Use the approved Human Trace logo unchanged and English-only copy.
- [ ] Tailor one concise, substantive contribution for each chosen community; disclose YuClaw affiliation and AI assistance where expected.
- [ ] Verify current community rules, permitted channel, official access path, and the user's authenticated posting account.
- [ ] After v7 completion and the user's explicit v8 release/outreach readiness decision, publish only the approved scope; retain actual permalinks and delivery status.
- [ ] Measure external reproductions, actionable defects, relevant pilot requests, completed trials, and repeat use. Impressions and stars are separate engagement measures.

The protection review created no accounts, community joins, messages, submissions, posts, or spending. A later user scheduling request now has a single-run September 22 readiness follow-up, described in the release schedule. It does not monitor continuously, perform unattended implementation, or publish automatically.

## Launch message direction

Lead with the core mission and the completed workflow: **financial research with traceable evidence and accountable AI evaluation**. Present the supporting protections individually, using verbs such as **verifies**, **flags**, **records**, or **plans** that match actual behavior.

Each community contribution should contain the concrete problem, enabled implementation, reproducible demonstration, known failure or limitation, and one specific request for feedback or a suitable pilot. Claims of preventing an AI takeover, guaranteed protection, or demonstrated human benefit without field evidence are outside the supported release message.

## Local evidence and related plans

- [Full v8 backlog](V8_FEATURES_AND_TODO.md)
- [Fresh review record](protection-review.json)
- [Existing a6 verification](../yuclaw-brain/output/commons-verification.json)
- [Shield specification](../yuclaw-brain/docs/v8/DISTILLATION_SHIELD.md)
- [Evolution specification](../yuclaw-brain/docs/v8/EVOLUTION_AUDIT.md)
- [Control audit](../yuclaw-brain/docs/v8/CONTROL_AUDIT.md)
- [Commons and Practice](../yuclaw-brain/docs/v8/RESEARCH_COMMONS.md)
- [Continuity benefit evaluation](../yuclaw-brain/docs/v8/BENEFIT_EVALUATION.md)
- [Paused outreach record](../YuClaw-community-outreach-2026-09-11/publication-status.json)

The original outreach drafts and a4 facts are preserved as historical preparation. This updated document is the current planning reference; it is not ready-to-post release copy.
