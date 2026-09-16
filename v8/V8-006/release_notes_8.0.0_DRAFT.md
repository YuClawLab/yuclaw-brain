Research & education only. Not investment advice.

### YUCLAW 8.0.0 — Evidence-First Financial AI · The Science Trust Layer for Financial AI

Financial AI normally gives you an answer. YUCLAW gives you the evidence, what that evidence can support, what it cannot support, and whether that conclusion survived time.

> DRAFT (V8-006, 2026-09-16; supersedes the V8-003 draft). Tier-2 public notes composed for review. They are not publishable until the release-state generator regenerates them at the frozen 8.0.0 candidate with the owner's recorded release policy; the publisher refuses notes whose hash and policy correspondence do not match that record.

#### New in 8.0.0 — the source-to-export commitment workbench (local, loopback only)

- One owner-operated workspace traces a financial commitment through seven visible steps: exact source passage → typed claim → comparison → calculation → history → adjudication → reproducible export. Plain HTML forms, no JavaScript, bound to 127.0.0.1; nothing in it publishes.
- Typed claims (`CommitmentClaim.v1`): currency, measurement unit, scale, metric, accounting basis, fiscal period with explicit dates and resolution rule are all mandatory; a missing or incompatible field blocks with every reason listed. Amounts are exact; floats are refused.
- Deterministic comparison and calculation: original-range and revised-range evaluations are shown separately with midpoint, delta and signed distance; incompatible basis, unit, period or metric yields an explicit unresolved state, never a pass. Two IN_RANGE results are never presented as evidence of improved accuracy.
- Append-only, digest-chained history with operation identifiers: a retried form submission lands once; a rewritten, deleted or reordered line makes the workspace refuse to serve; an interrupted append is recovered explicitly, never silently. Three times are kept apart on every event: when the source became public, when the workspace first observed it, and when the action was recorded; as-of replays are cut by source availability and never backdate later information.
- Reproducible export with fresh-workspace verification: digests and lengths checked, claim digests and event hashes re-derived, calculations recomputed; tampered, incomplete and unsafe archives are refused. Excerpt bytes travel only under rights that allow it; otherwise the digest alone. Public publication eligibility is reported separately and is NOT ELIGIBLE (commitments are not in the receipts PERMITTED class).
- Bounded disclosure ingestion (command line, never imported by the server): one source at a time from an allow-listed host, https only, bounded body, no cross-host redirect, original bytes and digests kept, EDGAR acceptance time as availability, retrieval time recorded apart. Passages are rendered as inert text.
- PyPI long description: generated from the GitHub README without the picture block (byte-identical elsewhere), so the package page renders without a broken image; the approved logo bytes are unchanged and not republished.
- Research notes and unresolved evidence: a researcher records an unresolved question or explanation, the next evidence needed, the reason and an actor label on a frozen claim, links it to a version and to evidence events, and corrects it with a new linked note that keeps the earlier text. A note changes no range, metric, currency, basis, period, source or digest; it is shown beside comparable and incomparable comparisons, missing outcomes and withdrawn commitments, and never appears as contemporaneous at an earlier research cutoff. An actor label is attribution only; automated actions are marked as simulated test actions.
- Dataset coverage: one row per frozen claim derived from the workspace's stored records — identifiers, source versions and lineage, targets and revisions, corrections and withdrawals, disclosed outcome, computed result, reviewer labels and disagreement, unresolved reasons, availability precision and observation times, rights restrictions, notes, coverage gaps and known omissions — with a deterministic snapshot identity, a machine-readable endpoint, verifiable snapshot exports and retained earlier snapshots whose changes are identified. An empty workspace shows empty coverage.
- Scientific report and replay: a bounded science journal (a JSON event list) is replayed through the adapted kernel — paired binary-probability predictions scored by Brier improvement, sequential evidence as a fixed mixture of Hoeffding test supermartingales, a frozen family alpha, pending, invalidated and exploratory statuses — with every hash re-derived and every statistic recomputed; a supplied report is never trusted. Ineligible inputs receive specific reasons (monetary amounts or ranges offered as probabilities, missing prediction pairs, changed targets, unsupported metrics, integrity failures, adjudication claims). Links to a commitment's claim, version and source bytes are verified as bytes only; a commitment's IN_RANGE or OUT_OF_RANGE results are never units of a study. Replay status is exploratory, prospective-claimed-not-verified or retrospective; imported timestamps and actor labels establish neither commitment before outcome nor verified identity.
- Exports and fresh-workspace verification now carry research notes, dataset rows and scientific records and recompute all of them; exports written by earlier builds verify unchanged, and unknown schema versions are refused explicitly.
- Packaging and minimum Python: every workbench module compiles on Python 3.10; the order records and scope documents are excluded from the distribution.

#### Evidence totals (public scoreboard at composition)

- Replication attempts: primary unavailable, successful unavailable; registration PENDING; exact-release coverage BOUND
- Witness reviews unavailable · audit-break attempts unavailable · refusals unavailable · challenges unavailable · document-use receipts 0 · pilots 0
- Board timestamp 2026-09-15T02:16:37.507118Z; these are counts of records, not a quality or independence verdict

#### Activation status (every proposed activation — unchanged, all INACTIVE)

- real receipt program: INACTIVE — no reviewer appointed, no registration record adopted, the three-reproduction floor unadopted (D3)
- nightly status delivery: INACTIVE — adapter and preview only; delivery not activated (D4-NIGHTLY-STATUS)
- note-snapshot coordinator: INACTIVE — contract v3 stays live; coordinator not wired (D4-SNAPSHOT)
- sentinel policy: INACTIVE — unchanged; proposal only (D4-SENTINEL)
- Phase-C prospective protocol: INACTIVE — draft; unregistered; nothing runs (D4-PHASE-C)
- Phase 6 / A2 designation of S: INACTIVE — candidate record only; not registered; N_eff not computed (D4-A2-S)
- ETF class addendum: INACTIVE — proposed classification path; registered set untouched (D4-ETF-ADDENDUM)
- U-ladder promotion / window: INACTIVE — fixture validation only; no admission, promotion or registered window (D4-U-LADDER-WINDOW)
- Gate #15 human study: INACTIVE — kit ships; no study run; gate MANUAL_REVIEW
- Phase-5 contribution anatomy: a READER of registered protocol lines and registered results; it is not a registered result and registers nothing
- Optional modules COM / PRC / SHD / EVO: ABSENT from the distribution; nothing is default-on

#### Release policy (recorded; the publisher refuses notes that do not match the record)

- Release policy: NOT RECORDED — owner decisions D1 (allocation document) and D2 (Gate #15 route) for 8.0.0 are pending. Gate #15 (user comprehension test passes) is NOT SATISFIED; no 8.0.0 exception has been issued and the 7.0.1 exception is not inherited. These notes are a draft and are not publishable until the policy record exists.

#### Continuing objects (unchanged from 7.0.1) — name · receipt · status

- Layered Evidence Dependency v1, first read · chain lines 81–82, sha256 0b2ac8a5967b13aa… · STRUCTURE_PRINTED — structural_completeness = PARTIAL; N_eff PENDING; READ_SCOPE = STRUCTURAL_ONLY (chain 81–82)
- Science Trust surfaces — per-name research-state cards + machine JSON, 132 names · anchor ac51ddfe97eb… · gate GREEN (machine JSON equals the human card, byte-reproducible); staged preview, not linked from the live navigation
- Research states · sha256 0163fe63f72bb13f… · 132 names: INSUFFICIENT_EVIDENCE 132 — derived, never hand-maintained
- Discovery Ledger · sha256 4951bd6ade88722a… · 37 hypotheses in bijection with 37 registered protocol lines; status counts ACCRUING 18, INCONCLUSIVE 1, OPEN 7, REGISTERED 7, SUPERSEDED 4 — negative and inconclusive findings preserved
- Anytime Evidence Record · sha256 ac37757aa2fb8f62… · 3 prospective enrollments — ACCRUING, not adjudicated
- Evidence Completeness Profiles · sha256 aa2f9c5e3d376cce… · 132 names; ETF class membership BLOCKED_BY_REGISTRATION
- Protocol registry · 82 chained lines, tip ac51ddfe…, chain-verified (no line added by 8.0.0)
- Public daily evidence ledger · 84 daily blocks, latest 2026-09-14 root d3fb98ff2448… · append-only, replayable
- C6 risk channel: rare-by-construction confirmed OOS (22% fire rate, n=9 held-out); sign positive at n=2 elevated — accruing · fourth read chain line 77 (98dcf74a827a…): DESCRIPTIVE
- Cross-lens reversal coherence · chain line 79 (be05bf7a9dc8…) · INSUFFICIENT — accruing, no coherence claim (chain 79)
- Consumer-posture gate · five deterministic stranger personas · GREEN (scaffold); full-form user-comprehension study NOT YET
- Replication · public log 1 entry, bundle sha256 f431f9c629ac38b5… · REPRODUCED — External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0
- yuclaw 8.0.0 package · wheel + sdist sha256 attached to this release · CLI · REST · MCP · SDK · v8 workbench (seven steps, research notes, dataset coverage, scientific report/replay)

#### Not in this release

- Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery.
- Human benefit: PENDING — no pilot, no user study; the workbench's fixture journeys demonstrate behaviour, not benefit.
- Real data: one issuer's quarterly net-sales guidance (Microchip Technology, Q1 FY2026) was replayed RETROSPECTIVELY through the workbench as a behaviour demonstration on real sources; the issuer is not eligible under the recorded selection criteria and no dataset product is claimed. The scientific examples that ship with the package are fictional fixtures; no experiment was run and no scientific improvement is claimed.
- Review: every adjudication and note in the release evidence was recorded by the automated journey runner as a simulated test action; there was no human review and no user study.
- Experimental audits: EXPERIMENTAL and absent.
- N_eff PENDING · Phase-5 contribution anatomy NOT YET · user-comprehension study NOT YET · unaffiliated replications 0

#### Made in Canada

Built in Canada — from Lake Ontario to Lake Louise and Kananaskis Lake — with gratitude to the country whose land and light frame this work.
