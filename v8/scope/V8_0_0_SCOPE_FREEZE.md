# YUCLAW 8.0.0 — implementation scope and review decision

Decision date: September 15, 2026. This is the execution scope selected for the first v8 implementation order after reviewing the owner's supplied Claude feedback. It is not release authorization, a completed implementation, or approval of an inherited policy exception. The 213-task backlog remains the broader roadmap; this document controls what is built for 8.0.0.

**Mission: Make financial AI accountable to evidence.**

**Vision: Become the Science Trust Layer for Financial AI.**

Neither wording nor meaning may change without the owner's explicit permission specifically authorizing that change.

## 1. Review verdict

Accept the narrow, owner-operated financial research workbench as the 8.0.0 target. The owner's subsequent September 15 instruction targets release on Monday, September 21, with promotion after the verified release. See the [V8-001 schedule addendum](V8_001_SCHEDULE_ADDENDUM.md). The present evidence does not establish that the deadline will be met. One complete, reviewable journey is the completion measure; a large count of passing component tests cannot substitute for it.

Apply these corrections to Claude's recommendation:

1. **Cancel backup functionality.** Remove backup creation, scheduling, restoration tooling, restore drills, and any Calgary-triggered resumption from the active scope and release requirements. Retain evidence journals, reproducible research exports, historical release artifacts, privacy controls, and safe code rollback. They serve separate purposes.
2. **Retain comparison.** Omitting the full RIV and ACT workstreams must not remove the comparison step from Gate B. Include an original-versus-revised target comparison and an explicit unresolved explanation/next-evidence field. Automated rival generation and action optimization are deferred.
3. **Keep Gates A and C applicable.** Baseline verification, source rights, data quality, and evidence integrity are not optional merely because the short scope table named B/D/G.
4. **Do not inherit v7's human-study exception.** The published v7 notes expressly limit its Gate #15 release-policy exception to 7.0.0. Gate E's pilot deferral does not satisfy or waive that inherited gate. Determine its applicability to the v8 release policy; if it remains unmet, complete the applicable requirement or obtain a new explicit owner decision on the concrete v8 evidence package before publication. Do not ask for a speculative exception at implementation start.
5. **Preserve the approved logo.** New authored public text uses `YUCLAW`. The approved Human Trace PNGs contain `YuClaw`; preserve their bytes and lettering. Technical package identifiers, commands, URLs, citations, and historical originals retain their exact spelling. Do not introduce a validator that rejects the approved logo or rewrites immutable material.
6. **Treat both publisher defects as release-path work.** The short-body refusal is independently confirmed in v7 source. The post-write TypeError is reported by Claude and requires the executor's actual publisher source and traceback before diagnosis.

## 2. Independently checked v7 baseline

Read-only verification on September 15, 2026 established:

- GitHub release `v7.0.0` is published, neither draft nor prerelease; publication timestamp `2026-09-15T02:14:59Z`.
- Annotated tag object: `f22ced5f9f47fc9c64daa1e7487e3f751d4dfd5e`.
- Peeled release commit: `6a619b74c46ee6601434e73d25963b5e2e61d59d`.
- Release source tree in the attached final target manifest: `3de0b2e4a4ee045df33b68834b13d5f811e9bf33`.
- Main observed at `c2401102579a0e2baea8b664ddbb4cda611db750`; this is not the release-tag commit. Review post-tag evidence changes separately.
- Downloaded PyPI wheel and sdist bytes match both PyPI digests and the GitHub release's final target manifest. This verifies artifact identity, not runtime correctness.
- The live `validation_lab.html` returned HTTP 200 and displayed `v7.0.0`.

| Artifact | SHA-256 |
|---|---|
| `yuclaw-7.0.0-py3-none-any.whl` | `6cd1164c7ffa744f6f1b876205144ea1bc52ed7b480223cc2bc93b356abe69aa` |
| `yuclaw-7.0.0.tar.gz` | `7399a1f1ed50d86b59d2301d3cbd1a5d188547a82b69809e787f2c426035116a` |
| Attached final target manifest | `f830a0b3de4469523220b312e16bf611fdf68763e7b8689894c38b92c643bbb6` |

Evidence: [verification record](v7-baseline-review-2026-09-15/verification.json), [final target manifest](v7-baseline-review-2026-09-15/target_manifest.json), [GitHub release](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v7.0.0), [PyPI release](https://pypi.org/project/yuclaw/7.0.0/), [live Lab](https://yuclaw.ca/validation_lab.html).

The existing local `8.0.0a6` working tree remains on the older `c34e19bffb1a9f8851bf03ac1e64b68be3bcb710` baseline with staged, unstaged, and untracked work. Preserve it. Integrate selected v8 changes into a separate checkout beginning at the verified v7 release commit; inspect later main changes before incorporating them. A preview patch must not replace v7 files wholesale.

## 3. Enabled scope

The first customer job is to trace a financial commitment from an exact source through revision, numerical checks, outcome review, and an export that another researcher can inspect and reproduce.

| Workstream | 8.0.0 deliverable | Boundary |
|---|---|---|
| GOV | Exact baseline, interface inventory, release scope, gate mapping | No silent scope expansion or automatic release authorization |
| DAT | One bounded disclosure ingestion path; original bytes; source version; exact passage; availability and retrieval dates; provenance and rights | No broad crawler, synthetic source authenticity, or copied-source independence |
| CLM | Editable typed revenue commitment with amount/range, currency, scale, fiscal period, accounting basis, issuer, version, and resolution rule | Unknown or incomparable fields prevent a misleading resolution |
| Comparison | Side-by-side original and amended commitments, basis checks, and unresolved explanation/next-evidence notes | Full RIV generation and ACT prioritization are deferred |
| CHK | Deterministic unit/basis/period checks and outcome-versus-range calculation, with visible inputs and formula | No general-purpose financial verdict or investment recommendation |
| TIM | As-of source view, immutable commitment revisions, correction history, and reviewer actions | No backdated knowledge or overwritten original target |
| SET | Narrow commitments-and-outcomes dataset; row provenance; correction status; deterministic snapshot and export | New annotations and measurements, not invented market facts or demonstrated alpha |
| SCI | Typed adapters to the existing supported scientific kernel; explicit eligibility and unresolved outcomes | No new statistical theorem, unsupported continuous-outcome inference, or benefit claim |
| UX | One connected browser workbench: source, claim, comparison, calculation, history, adjudication, export | Owner-operated, single workspace; no CLI required to complete the journey |
| INT | Actual v7 adapters, local persistence, transactions, safe migrations, interrupted-job handling, restricted file/network access, bounded jobs | No multi-tenant service, hosted customer accounts, billing, or backup subsystem |
| REL | Publisher repairs, reproducible release artifacts, current evidence, accurate notes and branding | No release, main push, PyPI upload, or outreach through this implementation order |

The initial real-data corpus is capped at one selected SEC-reporting issuer and one metric: quarterly revenue guidance. Select an issuer only after verifying eligible original/amended disclosures, source availability, rights, and comparable outcome data when available. Record omissions. A missing outcome stays unresolved. The fictional fixture is mandatory regardless of corpus choice. A fictional-only build must be labeled a demonstration, not a validated dataset product.

Single workspace still requires access boundaries. Bind locally by default. Any network exposure requires an explicit deployment design with authentication; source text must not execute scripts or instructions. Record who adjudicated each outcome and any conflicts. Owner review can be functional evidence but must never be labeled independent review without support.

## 4. Experimental and deferred work

| Status | Modules / work | Rule |
|---|---|---|
| Experimental, disabled by default | COM, PRC, SHD, EVO | Include only isolated, verified audit/replay artifacts that do not delay the core. Label `EXPERIMENTAL`; report human or operational benefit as `PENDING`. Pending Gate F forbids activating them on normal product routes. Omit an unsafe or unverified module from the distribution rather than claiming it shipped. |
| Deferred beyond 8.0.0 | CTL, RES, full RIV/ACT, RND, multi-tenancy, managed accounts, billing, real VAL pilot | Retain on the broader roadmap. No new runtime endpoints, UI tabs, automatic dependencies, or promised benefits in 8.0.0. |
| Canceled by owner | Backup functionality | No automatic reactivation, including at Calgary. Existing data and historical copies are retained. |
| Paused pending concrete release and authorization | Community publication | Draft preparation is separate from distribution. A date or completed v7 release does not authorize sending. |

Existing source-integrity and basic security requirements remain mandatory for the core even with SHD default-off. The experimental Shield is a bounded verifier, not a substitute for ordinary isolation, permissions, safe rendering, or secret handling. Evolution auditing does not prove that RSI occurred and does not control model deployment. CTL/RES deferral preserves the financial-evidence mission and leaves their research available for later decisions.

## 5. Seven-step acceptance contract

Use a clearly fictional issuer, fixed fixture dates, a named currency and fiscal quarter, and a consistent accounting basis. Original target: 110–120 million. Amendment: 105–115 million. Comparable actual: 112 million. The two targets remain separate definitions. Record all amounts as values plus units; avoid floating-point ambiguity in monetary calculations.

| Step | Required browser demonstration | Required negative case |
|---|---|---|
| 1. Source | Open the exact original and amended passages, their versions and availability timestamps | A later source is not visible as available at an earlier cutoff; unknown availability is explicit |
| 2. Typed claim | Save and freeze a fully specified claim; amendment creates a new version | Missing fiscal period, currency, basis, or resolution rule blocks an unsupported freeze |
| 3. Comparison | Show original and revised ranges side by side and state whether their metrics are comparable | Metric or accounting-basis change yields `INCOMPARABLE`; explanatory notes are not causal proof |
| 4. Calculation | Recompute 112 against each compatible range, showing units, inputs, formula, and source links | Currency/scale/period mismatch cannot silently produce a pass; outside-range fixture produces the correct distinct result |
| 5. History | Replay before amendment, after amendment, and after actual disclosure | Later information never rewrites the original claim or earlier as-of result |
| 6. Adjudication | Record reviewer identity, rule, evidence, reason, conflicts, and result; retain corrections | Missing outcome is unresolved; withdrawal is not automatically a miss; disputed labels remain visible |
| 7. Reproducible export | Download a rights-permitted snapshot containing schema, claim versions, source references/digests, events, method and result; verify it through the UI in a fresh workspace | Changed payload fails verification; export terms forbid bundling source bytes where rights do not allow it; interrupted output is not presented as complete |

Canonical research content and its digest must reproduce. An export operation's timestamp may differ, but keep that metadata outside the canonical content digest and document the rule. Source digests bind bytes; they do not prove publisher authenticity. An export is not a promised disaster-recovery or backup service.

Each step needs its RC commit/build identity, fixture digest, visible evidence, and an automated behavioral check where appropriate. Count a step only when demonstrated on the same v7-based integrated candidate. Initial score: **0/7 qualifying demonstrations recorded in this review**; this describes missing evidence, not a claim that no relevant code exists. Previous a6 component tests are not journey evidence.

## 6. Gate interpretation for 8.0.0

| Gate | Required 8.0.0 evidence | Current status |
|---|---|---|
| A | Frozen scope; exact v7 baseline and interface/adaptor inventory; English-only and mission/vision controls | Baseline verified; integration inventory pending |
| B | All seven steps on one RC, through the browser, plus the named negative cases | Not demonstrated |
| C | Corpus manifest and rights; bounded extraction/comparison quality checks; correction behavior; reviewer provenance and actual access controls | Pending; no multi-tenant claims |
| D | Applicable application/database/CI/security checks; supported statistical semantics; replay and audit evidence; interrupted-write safety and safe code rollback | Pending; backup creation/restoration canceled; `Restore not demonstrated` must be disclosed |
| E | Real-user pilot with predeclared outcomes and appropriate review | Deferred; benefit claims remain `PENDING`; inherited human-study gate applicability still requires resolution |
| F | Isolated engineering verification and applicability review for each optional audit module | Pending; experimental/default-off only |
| G | One built artifact set and manifest; mapped inherited release gates; two-tier notes; no unresolved critical defect; concrete owner release authorization | Pending; implementation order does not set release authorization |

Do not silently mark an inherited gate green or waived. Keep v7 evidence as historical evidence with its original status; a new v8 release decision is separate. A clean scope document does not substitute for a passing application check.

## 7. Backup cancellation and operational limits

Effective immediately, remove backup/restore functionality from the active v8 plan, including the `restored backups` condition in Gate D and backup/restore portions of INT-09. There is no automatic Calgary trigger. Do not delete stored data, existing backup files, source snapshots, release evidence, or append-only journals. Do not disable privacy checks merely because they inspect accidental backup copies.

Local inspection found no matching YUCLAW backup automation, no matching user LaunchAgent, and no crontab for user `zhang`. Historical system-export backup scripts are not evidence of an active YUCLAW scheduler and were not changed. Remote publisher/server schedules have not been inspected. Order V8-001 directs the executor to inspect its actual runtime and disable only identified YUCLAW backup producers/triggers, preserving data and unrelated jobs. Report before/after state and any inaccessible host; do not claim a remote cancellation without evidence.

Exact release disclosure: **Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery.**

Without backups, do not perform a destructive in-place data migration. Use compatible additive changes, transactions and preflight checks; refuse an unsupported transition. Retain interrupted-export safety and safe application-code rollback without pretending either restores lost data.

## 8. Milestones and reporting

| Date, Asia/Shanghai | Deliverable / decision |
|---|---|
| September 15 | Scope fixed for execution; clean v7 baseline; backup cancellation recorded; publisher defects reproduced or explicitly bounded |
| September 16–18 | Connect the seven-step workbench; integrate and verify data contracts and source-to-export behavior |
| September 19, evening | Go/no-go checkpoint: demonstrate Gate B on the RC. If not demonstrable, state the missing step and move the target date explicitly; no silent RC designation. |
| September 20 | Resolve findings; complete applicable testing, audit, release-policy mapping, branding and same-artifact checks; target artifact freeze |
| September 21 | Target release of the actual candidate after the concrete release decision; promotion follows verified release within the authorized scope |

Daily scorecard format: `YYYY-MM-DD | RC <commit/build> | journey <n>/7 | new evidence <paths> | blockers <facts> | next step <one action>`. Human review/response times cannot be guaranteed by this document. No additional daily automation was created.

Execute the first bounded work package in [Claude Code order V8-001](CLAUDE_CODE_ORDER_V8_001.md). Machine-readable scope: [v8.0.0-scope.json](v8.0.0-scope.json). This order has been prepared locally and has not been sent.
