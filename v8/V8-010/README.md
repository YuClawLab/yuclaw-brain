# V8-010 — selected product scope finished; 8.0.0 release candidate prepared for the owner

Order V8-010 (prepared 2026-09-16; run 2026-09-18 after 18:00 Asia/Shanghai). Branch `codex/v8-integration`, local only.
**release_authorized = false. Nothing was pushed, tagged, uploaded, deployed or published. Human benefit: PENDING.**
Gate #15 stays REMOVED_BY_OWNER (owner decision 2026-09-16) — a removed requirement, never a passed study.
Research and education only. Not investment advice.

## What a user can do now, and what still prevents release

A researcher installs one package, starts one local server and — entirely in the browser — registers an exact source
passage (typed, or pasted from the bounded ingestion tool's record), freezes a typed revenue commitment, compares the
original and revised ranges, recomputes the disclosed outcome against each range separately, replays history at any
cutoff, records adjudications and research notes, inspects dataset coverage, replays a science journal, builds a
rights-filtered export and verifies it in a fresh workspace. A refused form comes back with its reasons and the entries
kept; every unresolved or rejected state names the next action; the in-app **Help** page lists every function with its
address and shows the packaged operator guide (start/stop, the two workspaces, interrupted-write recovery, limits).

**Nothing technical blocks the candidate** (19 GREEN / 0 RED / 1 REMOVED_BY_OWNER; clean installs and journeys green).
What remains is the owner's: **(1) D1 allocation acceptance** and **(2) the freeze and publication authorization**
(with the mechanical steps those decisions trigger — see "Exact remaining owner action"). No further investigation
order is needed.

## 1. Identities

| Item | Value |
|---|---|
| Start of order | `cf2ec08c8002507d699f1885c96ff8a0603627fa` (tree `2c36d108d7b75c8377c9dbe29d38c517be29a1f4`); rule-change commit `e84e6730dff1df8fca50606ec730ef8f7078e378` (tree `12dd57eca35975ad3a128b3992e47d5c387fc2c4`) |
| **Candidate source** | commit `93274e7d7cb9e4c38583e976e94f7fe4874e39ce`, tree `3349b0643fe3c5c8e84c3d7424f10bb9d41807db`, version 8.0.0 |
| Candidate wheel (pre-release-review, not final) | `yuclaw-8.0.0-py3-none-any.whl` · sha256 `319ce0b55a4460001a9acdf4110521671185f6d17d95dd7baf03036a67ad5117` · 867,864 B |
| Candidate sdist (pre-release-review, not final) | `yuclaw-8.0.0.tar.gz` · sha256 `3290240cb5080f44ca49f5d96c4cfa936544a444802d6652079ffda98a812274` · 5,008,566 B |
| Build inputs | one build by `tools/yuclaw_v8_clean_install.py` from a clean detached worktree at the candidate commit; SOURCE_DATE_EPOCH 1580601600; Python 3.12.3, build 1.4.2, hatchling 1.32.3; twine 7 check PASSED |
| Later commits | evidence-only records (`v8/V8-010/…`, unpackaged): packaged source is byte-identical to the candidate |

Commits of this order, oldest first: `88568678` usability · `073cd117` first-release gaps · `1acacb00` packaging ·
`dfabb6ea` notes composer · `36a27b41` version-surface tool + CHANGELOG entry · `cc55aac9` rollback rehearsal tool ·
`232b561b` **version surfaces 8.0.0 + weekly note** · `51f9c9ae` two defects found during verification ·
`93274e7d` **candidate source** (packaged guides corrected) · then evidence records. Every commit carries the DCO
sign-off CONTRIBUTING.md requires (earlier v8 commits on this branch do not; they were left as they are).
Reviewable diff: `git diff cf2ec08c 93274e7d -- v8/workbench tools tests pyproject.toml` (19 files, +1,167 / −90);
version surfaces: `git show 232b561b --stat` (108 files, the same path set as the reviewed patch — `version_surfaces.json`).
Two pairs built earlier in this order (from `232b561b` and `51f9c9ae`) are superseded private records; neither is
relabelled as the candidate (`packaging.json`). Historical digests `aa988727…` / `bc974991…` belong to an earlier tree.

## 2. Selected-release gap list (`selected_release_gaps.json`)

Derived from the existing reconciliation (`v8/V8-008/roadmap_reconciliation.json`; the 213 rows were not rebuilt). For
each of the 56 selected rows that were not COMPLETE it records the narrower 8.0.0 deliverable under the cited scope
boundary, what this order completed, what remains, and the broader clause the agreed scope defers.

- **Status changes (3):** DAT-10 PARTIAL→COMPLETE (replay never duplicates a source or replaces a kept original; failures
  explicit), TIM-10 PARTIAL→COMPLETE (time-boundary, backdated-metadata and export tests), UX-11 UNVERIFIED→COMPLETE
  (verified by automated browser inspection and journeys; see §3 for what that is not).
- **Original-roadmap task counts** (counts, not effort or percentages): full 213 — 30/57/125/1 → **33 COMPLETE / 55
  PARTIAL / 125 UNBUILT / 0 UNVERIFIED**; selected 86 — 30/55/0/1 → **33 COMPLETE / 53 PARTIAL / 0 UNBUILT / 0 UNVERIFIED**.
  53 rows stay PARTIAL because their broader clauses are deferred by the scope (each cites its boundary); the narrower
  8.0.0 deliverable of every one of them is complete except the four below.
- **Remaining 8.0.0 obligations (4):** TIM-08 known limit (no in-place correction of a wrong availability time on an
  already-registered passage — stated in the packaged guides; a correction event is not built); INT-11 remote CI (cannot
  run while nothing is pushed); REL-02 freeze-day surface review; REL-06 final artifact set from the authorized commit.
  The last three follow the owner's decisions; none needs a new order.
- **Missing input (not software):** no SEC issuer meets the recorded corpus criteria (NO_ELIGIBLE_ISSUER), so GOV-03,
  DAT-04 and SET-01 stay PARTIAL; 8.0.0 ships a fictional demonstration and one retrospective NOT ELIGIBLE replay.
- Nothing deferred or experimental was implemented: COM/PRC/SHD/EVO stay absent and default-off; CTL/RES, full RIV/ACT,
  RND, multi-tenancy, accounts, billing and the pilot stay deferred.

Demonstrated defects fixed in this order are listed at the end of `selected_release_gaps.json` (eleven, two of them in
the private publisher).

## 3. Usability (UX-11) — what was checked, and what was not

`tools/yuclaw_v8_ui_inspect.py` (Chromium): 19 real pages at 1280×900 and 375×800 — programmatic label on every form
control, scoped header cells, every table in a named keyboard-scrollable region, main landmark / skip link / named
navigation / one h1 / heading order, Tab reaches every focusable element in document order with a visible focus
indicator, no page-level horizontal scroll at 375 px, coloured status elements carry text, error/notice blocks carry a
role and a text cue, a refused form returns with its entries. **131 findings before, 0 on the candidate**
(`ui_inspection.json`). Screenshots were inspected directly at both widths (that inspection caught per-character table
wrapping the script had passed). The browser journey adds keyboard-only operation and recovery through the browser.
**Not done and not claimed:** a human usability review, a screen-reader session, contrast measurement, an accessibility
certification. No users were recruited; this is not a substitute for the removed Gate 15 requirement.

Error behaviour reviewed on the affected routes — empty workspace, missing field, unresolved outcome, incompatible
input, disputed review, ingestion failure, export rejection: each explains the problem and a valid next action, keeps
the user's entries where a form exists, and writes nothing. One-way freezing and append-only amendments are unchanged.
Probing time boundaries and a sweep of every form route with hostile values found two request-killing inputs (an
impossible timestamp such as 30 February; an over-long packaged-example name); both are fixed and the sweep is kept as
`tests/test_v8_workbench_route_fuzz.py`.

## 4. Startup and navigation (installed package)

The packaged guide is `v8/workbench/resources/OPERATOR_GUIDE.md` (also `python -m v8.workbench guide`, and **Help** in
the running workbench). Working commands for the installed entry point:

```
python3 -m venv ~/yuclaw-venv && ~/yuclaw-venv/bin/pip install <yuclaw-8.0.0-py3-none-any.whl>
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/research --port 8765   # research
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/fresh    --port 8766   # fresh verification
```

Stop with Ctrl-C (every recorded action is already durable); start again with the same command. Direct addresses:
`http://127.0.0.1:8765/` workspace · `/source` 1 Source (+ ingestion-record import, as-of view) · `/claim/new` 2 Typed
claim · `/claim/<id>#comparison` `#calculation` `#history` `#notes` `#adjudication` `#export` steps 3–7 and notes ·
`/notes` · `/dataset` (`/dataset.json`) · `/sci` (`/sci/S1`…) · `/journal` · `/help` (`/help/data` data dictionary) ·
`http://127.0.0.1:8766/verify` fresh-workspace verification. Interrupted write: every page becomes the integrity page;
press **Run recovery** (or `python -m v8.workbench recover --workspace …`); the torn bytes are kept in a side file, no
durable event changes, a RECOVERY event is recorded. After startup the seven steps and the fresh-workspace verification
need no command line. Binding stays 127.0.0.1 with Host/Origin/session/CSRF checks, null-Origin refusal, inert source
rendering, bounded imports and uploads, rights filtering and safe archive paths; `Cache-Control: no-store` is now
actually sent. No new network exposure, no backup subsystem, no destructive migration.

## 5. Verification of the one integrated candidate

| Check (all on candidate `93274e7d`, the identified pair) | Result |
|---|---|
| Full repository test suite on the candidate tree | 297 passed, 0 failed (of which the v8 workbench, notes-composer and gate-15 suites: 106 — incl. 8 usability, 4 time-boundary, 1 route sweep, store and ingestion replay) |
| Wheel and sdist member inspection | ok — guides present; `v8/V8-*`, `v8/scope`, `v8/policy` absent (the policy record had shipped in the wheel since V8-009) |
| PyPI long description (both artifacts) | text/markdown, no picture element, no relative brand path, mission/vision markers present; twine check PASSED |
| Version surfaces | G2: 8.0.0 on 9 surfaces + 98 badge pages; canonical README blocks identical (G1); installed-command transcript exact (publisher verification) |
| Clean install, wheel (fresh venv outside the checkout, no editable install, no PYTHONPATH) | module inside venv, resources equal the source tree, CLI ok; **fixtures 7/7**, **real-source 7/7** |
| Clean install, sdist | same; **fixtures 7/7**, **real-source 7/7** |
| Features in the installed fixtures journey (85 assertions, 0 failed) | research notes, dataset, scientific replay, usability — DEMONSTRATED |
| Python floor | Python 3.10.21: every module compiles, export verifies SUCCESS and recomputes, scientific example replays, all pages 200 |
| Rollback rehearsal | 8.0.0 → published 7.0.1 → 8.0.0: workspace bytes untouched, same chain tip, export verifies |
| Approved logo bytes | unchanged (the three sha256 values in the scope file) |

Feature by feature (positive and negative cases, installed wheel): **Source** passages, availability vs observation vs
action time, later source hidden at an earlier cutoff, unknown availability blocks · **Typed claim** freeze, missing
fields listed, second freeze refused · **Comparison** side by side; basis change INCOMPARABLE · **Calculation** the
fictional original 110–120 million and revision 105–115 million with actual 112 million are **two separate IN_RANGE
calculations** with the no-inference statement (no accuracy-improvement claim); unit/period mismatch never passes ·
**History** replay before amendment / after amendment / after disclosure; later knowledge never appears at an earlier
cutoff; corrections retained · **Adjudication** simulated reviewer only; undisputed differing label refused · **Export**
fresh-workspace SUCCESS with recomputation; changed payload MISMATCH; unsafe paths refused; rights-withheld excerpts ·
**Research notes**, **dataset snapshot**, **scientific replay** (supported computation or explicit refusal; recomputed in
the fresh workspace) · **Microchip** stays a retrospective replay, NOT_ELIGIBLE under the original corpus criteria; the
original-source 1.020 vs revision-description 1.025 discrepancy is preserved; actual 1.0755 billion is outside both
recorded ranges (OUT_OF_RANGE / OUT_OF_RANGE); press-release excerpts withheld; existing source records reused.
Simulated adjudications stay simulated; no human reviewer, prospective validation, investment benefit or broader AI
protection is claimed. Earlier 7/7 records (V8-002 … V8-005) keep their original identities.

**Failures that remain:** none in the checks above. Known limits are listed in §2 and in the D1 proposal.

## 6. Release state, publisher rehearsal, notes, D1

- **Gates** (`gates.json`, exact generator output): 19 GREEN / 0 RED / 1 REMOVED_BY_OWNER; tripwire (pre) GREEN;
  remaining technical blockers: none; `policy_correspondence = ['no release-policy record']` (kept explicit — D1 is not
  accepted); release_authorized false. Gate 6 correction and the historical-calendar replay are preserved; calendar
  research was not reopened and the optional A1.2 note was not applied. Weekly note rendered in this checkout at
  2026-09-18T14:31:43Z and reconciled (242 events); it is point-in-time — a later evidence-store change needs a final
  refresh before the freeze, which creates a new source identity.
- **Publisher rehearsal** (`publisher_rehearsal.json`): focused, in a disposable home with synthetic allocation and
  authorization records and fake destinations — V8-009 rule (`policy <allocation>` alone; NOT_REQUIRED bound to the
  decision record; routes A/B, the actual PROPOSED D1 and a stale MANUAL_REVIEW manifest refused), adoption of the real
  pair (wrong commit, changed bytes and this order's superseded pair refused), interruption and resume (verification
  STOP → verify-retry; interrupted PyPI upload → only the missing file), every stage refused without authorization. The
  publisher's **real** verification block then ran once on the adopted pair: 16/16 checks (install, version, abuse
  matrix, claim smoke, D3 matrix, exact transcript, v7 journeys, v8 workbench 7/7 — wheel and sdist).
  **It found a release-path defect:** `gh-release` checked 8.0.0 notes with the 7.x composer and would have stopped a real
  release *after* push-main, push-tag and the PyPI upload. Fixed in the private publisher (version-dispatched composer,
  checked before the first public write; unit test added; 23 publisher tests pass). Publisher identity changed
  `a71782d8…` → `5649f289…`; no authorization was bound to the old identity.
- **Draft notes** (`release_notes_8.0.0_DRAFT.md`): two tiers; Tier 2 is the generator's exact composition for this
  candidate (notes/dataset/scientific features, Gate 15 removal without a study-pass claim, retrospective source status,
  rights limits, absent optional modules, the backup disclosure verbatim, benefit PENDING). `CHANGELOG.md` carries the
  matching 8.0.0 entry.
- **D1** (`D1_allocation_8.0.0_PROPOSED.json`, document `V8-ALLOC-2026-09-18-P3`, revision 4): complete current contents
  against this candidate — selected capabilities, inactive optional programs, publication ineligibility, backup
  cancellation, remaining limitations. **PROPOSED.** This order manufactures no acceptance; the rehearsal confirms the
  policy stage refuses the document as it stands.

## 7. Exact remaining owner action

Only allocation and publication decisions remain:

1. **D1** — read `D1_allocation_8.0.0_PROPOSED.json`; to accept, set `decision` to `D1-ACCEPT` (or `D1-AMEND: <note>`)
   and record it: `python3 internal/release_v8_0_0/publish_v800.py policy <that file>` (Gate 15 NOT_REQUIRED is recorded
   automatically).
2. **Freeze and authorize** — choose the commit to freeze (this branch HEAD unless a final weekly-note refresh is
   needed), re-run the generator there with `--release-policy`, confirm 0 RED and corresponding notes, then issue the
   verbatim authorization sentence for that commit and tree. The publisher then adopts a pair whose identity binds
   exactly that commit and tree (a 2-minute `tools/yuclaw_v8_clean_install.py --commit <frozen>` run produces it; the
   wheel and sdist are expected to be byte-identical to the candidate pair because later commits are unpackaged) or
   builds once. A calendar date never authorizes a release.

## 8. Risks to the schedule (19 Sept evening acceptance · 20 Sept freeze · 21 Sept release, Asia/Shanghai)

- The weekly note is LIVE_RECHECK: the store changes with the nightly chain, so gate 14 will need a final render at the
  freeze (2 minutes, but it changes the frozen commit and therefore the pair identity — do it before authorizing).
- This branch is 8.0.0 on top of base main `696d871e`; origin main is 4 commits ahead of that base (`a3b3ed2e` observed
  read-only). `push-main` is ancestry-checked and non-force, so those commits must be integrated before the freeze;
  that changes the frozen commit and the pair identity and was not part of this order — the largest unmeasured risk to
  the 21st.
- Remote CI has never run on this branch (nothing pushed).
- No human has used the workbench; acceptance on the 19th is the first human pass. The earlier full publisher
  rehearsal cannot run unchanged now that the branch itself is 8.0.0; the focused rehearsal replaced it.
- The packaged ingestion tool identifies to the SEC with the maintainer's contact by default (as the published v3
  sources already do); `SEC_USER_AGENT` overrides it and the operator guide says so. Owner's call whether that default
  should remain in a public package.

## Record files

`selected_release_gaps.json` · `capability_matrix.json` · `scorecard_fixtures.json` · `scorecard_mchp.json` ·
`journey_*/journey_log.json` · `packaging.json` · `python_floor.json` · `rollback_rehearsal.json` · `ui_inspection.json` ·
`version_surfaces.json` · `weekly_note_reconciliation.json` · `restage_measurement.json` · `tripwire_observations.json` ·
`gates.json` · `publisher_rehearsal.json` · `release_notes_8.0.0_DRAFT.md` · `D1_allocation_8.0.0_PROPOSED.json` ·
`changelog_entry_8.0.0.md` · `apply_version_surfaces_8.0.0.py` · `evidence_index.json`. The private record
(screenshots, installs, artifacts, publisher diff, superseded builds) is `internal/v8/v8_010_20260918T140309Z/`.
Review packages stay outside the shipped application: `v8/V8-*` is excluded from the wheel and sdist by pattern.
