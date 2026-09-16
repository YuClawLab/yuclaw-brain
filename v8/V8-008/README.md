# V8-008 — TB-1 repaired (8.0.0 notes composition), proposed state revised, 213-task roadmap reconciled (nothing published; decisions pending)

Recorded 2026-09-16. Branch `codex/v8-integration`; repair commit **`10d480cd`** (tree `13d91550…`) on `7ade9c78`; this record is a later record-only commit. Implementation candidate
unchanged **`d70edd02`** (no packaged code changed by V8-006, V8-007 or V8-008). Nothing pushed, tagged, deployed, uploaded or messaged; `release_authorized` stays **false**; Gate #15
stays MANUAL_REVIEW / NOT SATISFIED; human benefit **PENDING**; production untouched (weekly note sha `9576196c…` before and after; refresh chain not run). **Release readiness is
NOT reported**: owner decisions and the freeze-day render are open (section 7). No DGX Spark access was used or authorized by this order.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

## 1. TB-1 is FIXED (release tooling only) — `tb1_repair.json`, diff in the private record

- Defect: the generator composed policy-bound Tier-2 notes only for versions starting with `7.` and recorded `policy_correspondence = ['not a 7.x release']` for 8.0.0; the publisher's
  authorize stage correctly refuses any non-empty value.
- Repair (commit `10d480cd`): `tools/yuclaw_release_notes_v8.py` (new; not packaged), a version dispatch in `tools/yuclaw_release_state_v6.py` (7.x → the unchanged v7 composer;
  exactly 8.0.0 → the new composer; any other version → no composition path, never corresponds), `tests/test_release_notes_v8.py` (10 tests). The 8.0.0 account is composed from the
  workbench's own seven-step inventory, the machine-readable scope (enabled workstreams, minimal comparison/next-evidence behaviour, absent experimental modules, deferred work, the
  owner's backup disclosure verbatim) and the recorded V8-005 scorecards; the policy half reuses the 7.x helpers unchanged. Not done on purpose: no dropped policy check, no
  accept-every-version, no hardcoded empty list, no PROPOSED policy treated as accepted, no gate touched, no inherited 7.0.1 exception.
- Distinctions kept apart: version support (`notes_composer`) · correspondence (`check_correspondence`, text vs the RECORDED policy) · gate satisfaction (the gate table; Gate #15
  MANUAL_REVIEW on every run) · publication authorization (the owner's sentence; refused with any RED, an invalid policy or non-empty correspondence).
- Verification on fixed inputs: composer tests 10 passed; v7 regression `tests/test_v5_closure.py` 5 passed; publisher suite 15 passed (one new: the old sentinel, a missing record, a
  mismatch and an unsupported-version message all stop `authorize`; a PROPOSED allocation fails `policy_valid`; only an accepted record with `[]` passes, in a disposable repo with a
  labelled rehearsal wording); download-proof suite 7 passed. Every synthetic policy record is a labelled test fixture, kept out of the decision package and the candidate state.
- End to end: the generator on the revised staging now reports **`['no release-policy record']`** (V8-007: `['not a 7.x release']`) and the public notes carry the 8.0.0 account, the
  NOT RECORDED policy line, the backup disclosure, the Microchip retrospective / NOT ELIGIBLE statement, the simulated-review attribution, PENDING benefit and the absent modules.
  The rehearsal fixture (private) now composes with the 8.0.0 composer; it was compiled, not re-run (it repeats the runtime journeys).

## 2. Revised proposed state (`revised_candidate.json`, `designation_proposal.md`)

- Staging worktree at `10d480cd` + the version patch through `v8/V8-008/candidate_bump_8.0.0.py` with **explicit path staging** (allow-list; refuses anything else) → staged commit
  **`3d43089e`** (tree `c5bd485b…`); 108 files; patch-id `27267a97…` (identical to V8-006/V8-007); no symlink; `output/output` absent; clean tree. Status: **PROPOSED, not designated.**
  V8-007's `479a5aef` is retained as history; the render commits `30a5cf4e` (V8-007) and `25783e87` (V8-008) are staging evidence only.
- Preliminary pair rebuilt from `3d43089e`: wheel `aa988727…` (849,964 B), sdist `bc974991…` (4,992,067 B) — **byte-identical** to the V8-007 pair; twine 7 strict PASSED. Applicability
  stated explicitly: the repair touches no packaged path, so the V8-007 member accounting and the V8-006 rehearsal re-run's installed demonstration of these wheel bytes apply; each pair
  keeps its own identity record naming its own source commit (no relabelling). The final set still needs the frozen commit's own build (the sdist changes with the freeze-day docs).

## 3. Real release-state checks on the revised state (`gates.json`; V8-007's 19/0/1 was NOT transferred)

| Run | Tree | Gates | Correspondence | Meaning |
|---|---|---|---|---|
| 1 — as staged | `3d43089ea31e` | {'GREEN': 18, 'RED': 1, 'MANUAL_REVIEW': 1} | ['no release-policy record'] | exact status of the proposed candidate: gate 14 RED (committed weekly note stale; freeze-day render pending); gate 15 MANUAL_REVIEW |
| 2 — + staging-only render | `25783e87c54f` | {'GREEN': 19, 'MANUAL_REVIEW': 1} | ['no release-policy record'] | models the freeze-day tree; point-in-time (live recheck reconciled 269 events at 07:10:38Z) |

Both runs: tripwire (pre-publish) GREEN, `release_authorized` false. Gate table of run 2:

| # | Gate | Result | Evidence (truncated) |
|---|---|---|---|
| 1 | P0 registrations valid | **GREEN** | bace258b0bbb + 74c9a12a60e3 LOCKED; module METHOD_HASH == registry; A1 file sha256 == line-81 method_hash |
| 2 | chain verifies | **GREEN** | Registry.verify_chain on load: 82 lines, tip ac51ddfe97eb709a |
| 3 | zero unexplained ledger breaks | **GREEN** | docs/ledger 84 blocks 2026-05-20..2026-09-14; sessions without a block: 0; evidence-changes gate rc=0 |
| 4 | point-in-time guard | **GREEN** | as_of endpoint hash + twice-run identity (evidence-changes gate); u350 isolation proven by attempted writes |
| 5 | no v1 historical silent rewrite | **GREEN** | chain file byte-identical to base 696d871e: True; v1 evidence_geometry.json identical to base: True (last changed 0f10c2ec 2026-07-31); Phase-6 canoni |
| 6 | dependency calculations reproducible | **GREEN** | the registered structural first-read computation reproduced byte-identically from frozen inputs (fresh NO-WRITE replays this session) |
| 7 | truncation ledger reconciles | **GREEN** | [truncation-gate] OK — 13 ledger entries (schema + anchors verified), detector clean over v3/tools (allowlist v1, 10 constants) |
| 8 | hypothesis/discovery lineage reconciles | **GREEN** | [discovery-gate] OK — 37 hypotheses <-> 37 protocol lines (bijection both directions), 33 families locked, artifact byte-identical to chain-derived re |
| 9 | sequential methods pass registered fixtures | **GREEN** | anytime gate + registered fixtures selftest |
| 10 | research-state derivation reproducible | **GREEN** | [research-state-gate] OK — 132 names render registered artifacts only; byte-identical rebuild; platform C6 verdict verbatim |
| 11 | machine JSON agrees with human page | **GREEN** | [science-trust-gate] OK — 132 cards: machine JSON == human card == fresh derivation (field-for-field); research states verified against research_state |
| 12 | source citations resolve | **GREEN** | site-walk: all links + anchors resolve; index completeness; copy integrity |
| 13 | negative/inconclusive findings preserved | **GREEN** | discovery status_counts ACCRUING 18, INCONCLUSIVE 1, OPEN 7, REGISTERED 7, SUPERSEDED 4; questions insider-directional RETIRED, reversal-coherence OPE |
| 14 | language rails pass | **GREEN** | language rail (pages + README + COMPARISON + architecture + CHANGELOG) + leak sweep (private denylist) + no-forms + header layout (badge == package ve |
| 15 | user comprehension test passes | **MANUAL_REVIEW** | consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist |
| 16 | stranger-machine reproduction passes | **GREEN** | External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0 — registered sentence "stranger-machine reproduction p |
| 17 | G1 copy-consistency (canonical blocks byte-identical) | **GREEN** | [copy-consistency] OK — 8 target blocks byte-identical to their canonical sources (MISSION-VISION: sha256 c3b3d26ca94f, LOOKAHEAD: sha256 34ff23ecbef0 |
| 18 | G2 version (package = badge = capabilities = index = llms = README = PyPI metadata) | **GREEN** | [release-manifest] OK — G2 version 8.0.0 on 9 surfaces + 98 badge pages |
| 19 | G3 base URL (capabilities = index = llms = release_manifest.public_base_url) | **GREEN** | [release-manifest] OK — G3 base https://yuclaw.ca (77 URLs, zero github.io) |
| 20 | G4 endpoints (declared set = generated set; static 200/type/schema; wildcards by discovery) | **GREEN** | [release-manifest] OK — G4 22 endpoints declared on 3 surfaces, 31 representatives local-resolved and schema-valid |

Evidence reused with explicit applicability: gate-6 fresh bound replay (pinned calendar; inputs unchanged; no repeat), restage measurement (packaged/preview content identical), tripwire
observations (nothing published since), the V8-006 rehearsal re-run (wheel bytes identical; its Tier-2 fixture used the 7.x composer, now corrected, not re-run). The current D1/D2-dependent
state remains blocked after the repair: `policy_correspondence` is non-empty until D1 + D2 are recorded, and gate 14 needs the freeze-day render. That is the honest outcome.

## 4. Roadmap reconciliation — 213 original tasks (`roadmap_reconciliation.json`, `roadmap_reconciliation.md`)

Source: `v8/scope/v8-backlog.json` via the scope index (213 tasks, 20 workstreams, planning date 2026-09-14; every historical status `todo`); all IDs and descriptions preserved; the
roadmap is not replaced by the 8.0.0 feature matrix. Statuses rest on code inspection and automated behavioural evidence unless the basis column says otherwise; no human review,
prospective study, public release or paid-user validation exists, and none substitutes for another.

| Set | Denominator | COMPLETE | PARTIAL | UNBUILT | UNVERIFIED | CANCELED |
|---|---|---|---|---|---|---|
| Full original roadmap | 213 | 30 | 57 | 125 | 1 | 0 |
| Selected first-release deliverables (scope enabled / enabled-minimal) | 86 | 30 | 55 | 0 | 1 | 0 |

These are task counts with their denominators, not effort-weighted percentages: **an effort percentage is not yet available** (the backlog carries no workload estimates). Orders completed,
green gates and test counts are not a percent of v8 work. No task is CANCELED: the owner's backup cancellation is a sub-requirement of INT-09/INT-12 and does not cancel their remaining
retention, security and operations requirements. Authentication, independent checkpoints, multi-tenancy, accessibility (UX-11 UNVERIFIED), scientific benefit, customer adoption and human
studies are not marked complete; the experimental Shield module is UNBUILT even though the core's ordinary security exists.

## 5. Decision documents (complete; nothing recorded, selected or drafted on the owner's behalf)

`D1_allocation_8.0.0_PROPOSED.json` (document id `V8-ALLOC-2026-09-16-P2`, revision 2, still PROPOSED; states what changes on acceptance) · `D2_gate15_decision_package.md` (actual route A
requirements, actual route B requirements and disclosures, hold; no route selected; no owner statement invented) · `designation_proposal.md` (the corrected source state and the exact
change; separate from freeze and from authorization) · the optional A1.2 note stays in `v8/V8-007/A1_2_calendar_note_PROPOSED.md`, unapplied · `owner_ui_checklist.md` (functional review with
a blank observation column; start instructions in `v8/V8-006/START.md`; not Gate #15 evidence).

## 6. Checks run this order (focused; no full application suite or browser journeys)

Composer tests (10), v7 composer regression (5), publisher suite (15) and download-proof suite (7); pyflakes and Python 3.10 compilation of the changed tools and tests; the explicit-staging
bump with G2 and header-layout checks; one preliminary build with twine 7; the real weekly-note renderer and checker in staging (exit 0, reconciled); the release-state generator twice.

## 7. Resolved · still blocking · owner decisions and the next action after each

**Resolved**: TB-1 (8.0.0 notes now compose and bind to a recorded policy; the sentinel is gone); the proposed state now includes the repair with the same version patch and identical
artifacts; explicit staging replaces `git add -A`; the 213-task roadmap has a status per task with counts and denominators.

**Still blocking release (facts, not decisions)**: gate 14 RED as staged until the freeze-day render in the frozen checkout; `policy_correspondence` non-empty until D1 + D2 are recorded;
the final artifact set does not exist (built or adopted from the authorized commit); Gate #15 MANUAL_REVIEW.

**Owner decisions**:
1. **Designate** — order the version patch applied (Step 1 of `designation_proposal.md`; patch-id and rebuilt bytes must match). Not designating → everything stays as staged.
2. **D1** — edit the P2 document to `D1-ACCEPT` (or `D1-AMEND: …`); recordable only together with D2 through the publisher's policy stage after the freeze.
3. **D2 / Gate #15** — route B (supply dated 8.0.0 wording → bind into the publisher → tests + rehearsal re-recorded), route A (study first) or hold; next action per option in the package.
4. **A1.2 note** (optional) — record the registry addendum or leave it; gate 6 is GREEN either way.
5. **Owner functional review** — run the UI checklist and record observations in your own words; it does not change Gate #15.
6. **Authorization** — only after 1–3 and the freeze: the sentence in the required form naming the frozen sha and tree; then the publisher builds or adopts the one final set.

Targets stay September 19 evening acceptance, September 20 freeze and September 21 release readiness (Asia/Shanghai), conditional on actual completion and these decisions.
Private record: `internal/v8/v8_008_…/` (staging worktree with the candidate and the staging-only render commit, staging build + identity + twine log, bump log, weekly-note runs,
generator evidence/logs/manifests/notes for both runs, the TB-1 repair diff, the full version patch, review diff). Research and education only. Not investment advice.
