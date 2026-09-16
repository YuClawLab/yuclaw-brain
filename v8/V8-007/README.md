# V8-007 — provenance resolved, coherent candidate assembled, weekly note reconciled in staging (nothing published; decisions pending)

Recorded 2026-09-16. Branch `codex/v8-integration`; base HEAD when this order started `ab2c5c88` (tree `1d1273f9…`); implementation candidate with browser and installed
evidence **`d70edd02`** (unchanged — no packaged code changed by V8-006 or V8-007). Nothing pushed, tagged, deployed, uploaded or messaged; `release_authorized`
stays **false**; Gate #15 stays MANUAL_REVIEW / NOT SATISFIED; human benefit **PENDING**; the production checkout, the live refresh chain and production state were
not touched. **Release readiness is NOT reported**: the owner decisions and one release-tool blocker in section 8 are open.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

## 1. Artifact provenance — resolved (`provenance.json`)

The V8-006 sentence "staged 8.0.0 wheel byte-identical to the publisher rehearsal's independently bumped build" (reported as "the V8-003 rehearsal wheel") was ambiguous.
Resolution: **ambiguous wording, correct bytes.** The comparison object was the **V8-006 re-run** of the rehearsal test that V8-003 introduced, not the historical V8-003 artifact.

| Record | When (UTC) | Real candidate | Rehearsal / staged commit · tree | Wheel sha256 · size | Sdist sha256 · size | Role |
|---|---|---|---|---|---|---|
| V8-003 historical rehearsal (`publisher/rehearsal_result.json`, sha `7d7e7ee3b7ef…`) | 2026-09-16T02:23:32Z | `9efdd52d88a3` | `9509480ef4d0` · `fa0a20e9460f` | `ad07972ece8dac51…` · 795,262 B | `0e0fa3fe2b787dbc…` · 4,945,800 B | pre-SCI build; retained as the V8-003 record; NOT the comparison object |
| V8-006 re-run of the rehearsal test (`release_v8_0_0/rehearsal_result.json`, sha `e76182822afc…`) | 2026-09-16T04:59:18Z | `2cc7a7b9743e` | `9923712ebd03` · `1abc5d5ee1b0` | `aa988727055aa81f…` · 849,964 B | `32d553736ec13b6d…` · 4,992,065 B | the build the V8-006 README compared against; wheel and sdist installed and verified (7/7 v8 journeys, abuse matrix, exact transcript, v7 journeys) |
| V8-006 staged pair (SUPERSEDED, retained) | 2026-09-16T05:04:07Z | base `2cc7a7b9` | `ca50b42efd83` · `587fbb2a41c1` | `aa988727055aa81f…` · 849,964 B | `bc974991c5e12433…` · 4,992,067 B | source lacks the V8-006 tool corrections and tracks a stray `output/output` symlink (unpackaged) |
| **V8-007 coherent pair (current proposed set)** | 2026-09-16T06:22:18Z | base `ab2c5c88` | `479a5aef6feb` · `027c43ead253` | `aa988727055aa81f…` · 849,964 B | `bc974991c5e12433…` · 4,992,067 B | PRELIMINARY development build; twine 7 strict PASSED; identical bytes to the V8-006 staged pair |

Build configuration for every row: `python3 -m build --sdist --wheel`, `SOURCE_DATE_EPOCH=1580601600`, hatchling 1.32.0, build 1.4.2, Python 3.12.3, no `PYTHONPATH`; the rehearsal rows add
the rehearsal-only bump (98 pages / 98 badges) on a disposable clone. Invocation lines and hashes of the records and logs are in `provenance.json`.

**Staged artifacts accounted for against their declared source** (`git show <commit>:<path>` byte comparison): wheel 261 members = 255 identical to the tree + 6 generated dist-info (0 differ,
0 outside the tree); sdist 1,176 members = 1,175 identical + generated `PKG-INFO` (0 differ, 0 outside). Version metadata `8.0.0` (Metadata-Version 2.5); entry point `yuclaw = v4.cli:main`;
`v8/workbench/{dataset,server,store,export,…}.py`, `v8/workbench/sci/*` (6 modules) and `resources/sci/*` (7 files) present; no order records, tests or `internal/` in either artifact.
The wheel's 255 non-metadata members are byte-identical to the 7.0.1-labelled V8-005 development wheel: the bump changes dist-info only. **No artifact is relabelled**: the 7.0.1-labelled
development demonstrations stay bound to their original artifacts; the V8-006 staged set is retained and marked superseded; a dated correction line was appended to `v8/V8-006/README.md` §2 (the original sentence stays).

## 2. One coherent proposed candidate (`coherent_candidate.json`, `designation_procedure.md`)

- Private staging worktree at `ab2c5c88` (implementation + V8-005/V8-006 records + the V8-006 corrections to `tools/yuclaw_v8_clean_install.py` and `tests/test_v8_workbench_packaging.py`)
  + the version-surface patch produced by the reviewed bump script → staged commit **`479a5aef6feb`** (tree `027c43ead253`). The patch is the SAME content as V8-006's
  (stable patch-id `27267a974a72…`, 108 files); G2 OK on 9 surfaces + 98 badge pages; header layout OK. History preserved: the V8-006 staging worktree and commit `ca50b42e` remain registered.
- Differences from the reviewed implementation `d70edd02`, by kind: **packaged code — none**; release tooling — the two V8-006 files above (not packaged); generated pages — 98 badge pages,
  `docs/preview/capabilities.vnext.json`, `README_PYPI.md`, README transcript; version metadata — 8 files; evidence records — `v8/V8-005/`, `v8/V8-006/` (excluded from artifacts by pattern).
- Differences from the V8-006 staged commit: 15 paths — the two tool/test corrections and 13 V8-006 record files added, the stray `output/output` symlink absent; **artifact bytes identical**.
- Declared inputs recorded: bump script sha256 `471c5b94dfa6…`, `output/` mirrored from the branch checkout's untracked state, full patch sha256 `7a008d387b30…`.
- Focused installation this order (no journeys; the identical wheel bytes were demonstrated 7/7 in the V8-006 re-run): fresh venvs from the wheel and from the sdist → `yuclaw 8.0.0`,
  workbench modules import from site-packages, kernel identity `5b3e0d221c2200b2…`, 7 SCI resources, 9 fixture files, console script present, `python -m v8.workbench status` on a new workspace.
- **Designation is pending**: applying the patch to the branch is the owner's order (procedure, identity checks and the three distinct approvals in `designation_procedure.md`).

## 3. Weekly-note reconciliation in isolated staging (`weekly_note_reconciliation.json`)

- **Dependency**: the renderer `tools/yuclaw_weekly_note.py` and the checker `tools/check_weekly_note.py` derive every path from their own checkout (`Path(__file__).resolve().parents[1]`); inputs are that
  checkout's `docs/evidence_changes/*.json` and `registry/protocols.jsonl` plus the live evidence store (read-only SELECT). There is no hardcoded production path, so **no path change was needed**;
  "production render" means the note that ships must be rendered in the checkout that is frozen (its `as_of` is the generation time; the recount is live).
- **Runs in the staging worktree** (production note untouched, sha `9576196c…` before and after; refresh chain not run):
  A. checker on the committed note → exit 1: `· events: note 245+8=253 vs store 327+11=338`.
  B. real renderer → exit 0: window 2026-09-10 → 2026-09-16, `as_of` 2026-09-16T06:22:25.969342Z (generated-at), 47 filings from the staged archive, badge v8.0.0; output only `<staging>/docs/weekly_note.html` (sha `ecd05882bcf2…`).
  C. checker on the rendered note → exit 0: `[note-gate] reconciled: 269 events (264/5), 0 protocols, 0 runs, 0 supersessions for 2026-09-10..2026-09-16 (contract v3, generated at 2026-09-16T06:22:25.969342Z; live recheck)`.
  D. every gate-14 component on the staged tree: language rail 0, no-forms 0 (323 html files), header layout 0 (98 pages, badge v8.0.0), leak sweep 0 (private denylist supplied as a gitignored symlink, the V8-006 pattern), weekly note 0 — all exit 0.
  E. the release-state generator on the staged tree with the rendered note (staging-only render commit `30a5cf4eb1aa`, not proposed for designation): **gate 14 GREEN**.
- Not forced: every number is the real tool's result at that moment; the staged note's archive counts come from the branch's committed archive (production's note for 2026-09-09→15 reports
  108 filings and 337 events from its own inputs). The result expires with the next evidence-store change and the freeze-day render in the frozen checkout replaces it.
- Policy-dependent fields: **none in the weekly note**. They live in the Tier-2 release notes (allocation decision / document id / sha256 prefix; Gate #15 route with the verbatim exception text or the accepted gate input; activation lines) — see TB-1 below.

## 4. Preserved unchanged
Gate-6 superseding correction with its fresh bound replay (`v8/V8-006/gate6_correction.json`; no replay repeated; carried into the generator evidence); the A1.2 note stays unapplied
(`A1_2_calendar_note_PROPOSED.md`); the adoption path (clean-install `--artifacts`, publisher `adopt`) as validated on the V8-005 pair; the tripwire observations (2026-09-16T04:54:53Z, pre GREEN);
both mocked rehearsals with their own identities; the 7.0.1-labelled development demonstrations; approved logo bytes, canonical mission/vision blocks, English-only product content with YUCLAW
on public surfaces, backup cancellation and existing data. COM/PRC/SHD/EVO remain absent; deferred work stays outstanding; calendar/2028/release-replay findings stay in the separate release queue.

## 5. Decision documents (complete; nothing recorded)
| File | What it is | What its approval permits | What it does not permit |
|---|---|---|---|
| `D1_allocation_8.0.0_PROPOSED.json` (document id `V8-ALLOC-2026-09-16-P2`) | allocation scope + every activation INACTIVE, bound to the coherent candidate | the allocation half of `policy_valid`, once recorded by the policy stage together with a route | no route, no designation/freeze, no authorization, no activation |
| `D2_gate15_decision_package.md` | Gate #15 status, verbatim rules, three options, next action per option | a recorded route satisfies `policy_valid` (route B only after the owner's wording is bound; route A only after a study) | no authorization; Gate #15 stays MANUAL_REVIEW |
| `designation_procedure.md` | identity and diff of the coherent state; steps; the three distinct approvals | the owner's designation order applies the patch locally | nothing external; `release_authorized` unchanged |
| `A1_2_calendar_note_PROPOSED.md` (optional) | the proposed registry addendum text with its governing rules | a registered statement of the first read's replay calendar | no guard change, no re-pin, no 2028 claim |
| `owner_ui_checklist.md` | the owner's own browser walk-through (21 lines) | owner acceptance in the owner's words | nothing recorded as human review; not a Gate #15 study |

## 6. Gate preparation on the coherent staging (`gates.json`; real definitions, no forced results)
Generator: `tools/yuclaw_release_state_v6.py --evidence <record>/gates/evidence_v8_candidate_coherent.json` (no `--release-policy`: none recorded), run on `30a5cf4eb1aa`
(= the candidate + the staging render). Result **{'GREEN': 19, 'MANUAL_REVIEW': 1}**; tripwire (pre-publish) GREEN; `release_authorized` False.

| # | Gate | Result | Evidence (truncated) |
|---|---|---|---|
| 1 | P0 registrations valid | **GREEN** | bace258b0bbb + 74c9a12a60e3 LOCKED; module METHOD_HASH == registry; A1 file sha256 == line-81 method_hash |
| 2 | chain verifies | **GREEN** | Registry.verify_chain on load: 82 lines, tip ac51ddfe97eb709a |
| 3 | zero unexplained ledger breaks | **GREEN** | docs/ledger 84 blocks 2026-05-20..2026-09-14; sessions without a block: 0; evidence-changes gate rc=0 |
| 4 | point-in-time guard | **GREEN** | as_of endpoint hash + twice-run identity (evidence-changes gate); u350 isolation proven by attempted writes |
| 5 | no v1 historical silent rewrite | **GREEN** | chain file byte-identical to base 696d871e: True; v1 evidence_geometry.json identical to base: True (last changed 0f10c2ec 2026-07-31); Phase-6 canonical artifact identic |
| 6 | dependency calculations reproducible | **GREEN** | the registered structural first-read computation reproduced byte-identically from frozen inputs (fresh NO-WRITE replays this session) |
| 7 | truncation ledger reconciles | **GREEN** | [truncation-gate] OK — 13 ledger entries (schema + anchors verified), detector clean over v3/tools (allowlist v1, 10 constants) |
| 8 | hypothesis/discovery lineage reconciles | **GREEN** | [discovery-gate] OK — 37 hypotheses <-> 37 protocol lines (bijection both directions), 33 families locked, artifact byte-identical to chain-derived rebuild; status_counts |
| 9 | sequential methods pass registered fixtures | **GREEN** | anytime gate + registered fixtures selftest |
| 10 | research-state derivation reproducible | **GREEN** | [research-state-gate] OK — 132 names render registered artifacts only; byte-identical rebuild; platform C6 verdict verbatim |
| 11 | machine JSON agrees with human page | **GREEN** | [science-trust-gate] OK — 132 cards: machine JSON == human card == fresh derivation (field-for-field); research states verified against research_state.json directly; sequ |
| 12 | source citations resolve | **GREEN** | site-walk: all links + anchors resolve; index completeness; copy integrity |
| 13 | negative/inconclusive findings preserved | **GREEN** | discovery status_counts ACCRUING 18, INCONCLUSIVE 1, OPEN 7, REGISTERED 7, SUPERSEDED 4; questions insider-directional RETIRED, reversal-coherence OPEN, reversal-structur |
| 14 | language rails pass | **GREEN** | language rail (pages + README + COMPARISON + architecture + CHANGELOG) + leak sweep (private denylist) + no-forms + header layout (badge == package version) + weekly-note |
| 15 | user comprehension test passes | **MANUAL_REVIEW** | consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist |
| 16 | stranger-machine reproduction passes | **GREEN** | External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0 — registered sentence "stranger-machine reproduction passes" (requires rep |
| 17 | G1 copy-consistency (canonical blocks byte-identical) | **GREEN** | [copy-consistency] OK — 8 target blocks byte-identical to their canonical sources (MISSION-VISION: sha256 c3b3d26ca94f, LOOKAHEAD: sha256 34ff23ecbef0, REPLICATION-SENTEN |
| 18 | G2 version (package = badge = capabilities = index = llms = README = PyPI metadata) | **GREEN** | [release-manifest] OK — G2 version 8.0.0 on 9 surfaces + 98 badge pages |
| 19 | G3 base URL (capabilities = index = llms = release_manifest.public_base_url) | **GREEN** | [release-manifest] OK — G3 base https://yuclaw.ca (77 URLs, zero github.io) |
| 20 | G4 endpoints (declared set = generated set; static 200/type/schema; wildcards by discovery) | **GREEN** | [release-manifest] OK — G4 22 endpoints declared on 3 surfaces, 31 representatives local-resolved and schema-valid |

## 7. Checks run this order (focused; no full suites or journeys — no packaged module changed)
Member accounting of both artifacts; version-patch identity (patch-id); build from the coherent commit; twine 7 strict; focused installs from wheel and sdist; the five gate-14 components;
the weekly-note renderer and checker (before/after); the release-state generator once on the staged tree. Reused with their original identities: V8-005 demonstrations, V8-006 gate-6 replay,
restage measurement, tripwire, rehearsal results, adoption run.

## 8. Resolved · technical blockers · owner decisions · next action after each decision

**Resolved**: the provenance ambiguity (section 1); the staged artifacts' accounting; the stray-symlink defect in the V8-006 staged commit (absent from the coherent candidate); the
weekly-note dependency question (no production-checkout dependency in the tools) with a real staged reconciliation; gate 14 GREEN on the coherent staging; one coherent candidate with identical artifact bytes.

**Technical blockers (release queue)**:
- **TB-1 — 8.x notes composition** (`gates.json`): the generator composes the policy-bound Tier-2 notes (feature account, activation lines, release-policy disclosure) only for versions starting
  with `7.`; for 8.0.0 it records `policy_correspondence = ['not a 7.x release']`, and `publish_v800.py authorize` stops on a non-empty value. Present in the V8-006 staged run too (not called out then).
  Smallest reviewed change: an 8.x composition path carrying the reviewed draft's 8.0.0 account (`v8/V8-006/release_notes_8.0.0_DRAFT.md`) with the same correspondence check — release tooling only; proposed, not applied.
- Freeze-day renders (weekly note and the 7.0.1-pattern pages) happen in the frozen checkout; the final sdist will differ from `bc974991…` by those pages; the wheel is expected to stay `aa988727…`.
- The final artifact set does not exist: the publisher builds or adopts it from the authorized commit; the preliminary pair's identity record binds `479a5aef`, so `adopt` will refuse it for any other sha/tree by design.

**Owner decisions** (each with its next action):
1. **Designate** — order the version patch applied to the branch → Step 1 of `designation_procedure.md` (cherry-pick / apply; patch-id and rebuilt bytes must match) → then Step 2 at the freeze.
   Not designating → the staging worktree, pair and records stay; nothing else moves.
2. **D1** — edit the proposal to `D1-ACCEPT` (or `D1-AMEND: …`) → it is recorded only together with D2 by `publish_v800.py policy …` after the freeze.
3. **D2** — choose route B (supply dated 8.0.0 wording → bind into the publisher → tests + rehearsal re-recorded), route A (study first) or hold → `D2_gate15_decision_package.md` § next action.
4. **A1.2 note** (optional) — record the addendum line in the production registry, or leave it; gate 6 is GREEN either way.
5. **TB-1** — approve the reviewed release-tool change so the generator can compose and bind the 8.0.0 notes; without it authorization is refused by the tooling.
6. **Authorization** — only after 1–3 (and 5) and the freeze: the sentence in the `AUTH_TEMPLATE` form naming the frozen sha and tree; then the publisher builds or adopts the one final set and verifies it.

Private record: `internal/v8/v8_007_20260916T062115Z/` (staging worktree with the candidate and the staging-only render commit, staging build + identity + twine log, focused-install probes,
weekly-note runs and the rendered note, gate-14 logs, generator evidence/log/manifest/notes, full version patch, review diff). Research and education only. Not investment advice.
