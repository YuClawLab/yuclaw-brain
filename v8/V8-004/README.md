# V8-004 — complete the remaining enabled product functions (local implementation and evidence only)

Recorded 2026-09-16. Branch `codex/v8-integration`, continued from V8-003 (`7db44812`). Integrated candidate with browser
evidence: **`91d9a2110526`**; this record's HEAD `91d9a2110526` (tree `e5460cdfee5c`). Nothing pushed, tagged, deployed, uploaded or messaged; `release_authorized`
stays **false**; Gate #15 keeps its actual status (MANUAL_REVIEW, NOT SATISFIED; no 8.0.0 exception; the 7.0.1 exception is not inherited); human benefit **PENDING**.
The approved 8.0.0 scope controls this order; the 213-task roadmap includes later work and is not completed by it.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

Commits of this order (oldest first), all local and unpushed:
- `91d9a211` v8: journey — feature demonstrations bound to real records: the INCOMPARABLE pair carries amendment notes, fixture claims are looked up by their loaded identifiers, the p
- `f70b7de5` v8: journey — retry demonstration sends the same rendered note form twice with its identical operation identifier (history navigation re-fetches a fresh form under no-sto
- `0788e854` v8: research notes and dataset coverage (V8-004 §3/§4) — append-only RESEARCH_NOTE_RECORDED events with correction chains that change no claim field or digest, retry-safe

## 1. Functions implemented and where they live in the browser

| Function | Browser location | What it does |
|---|---|---|
| Research note (§3) | claim page → section **Research notes — unresolved evidence (separate from amendments)**; index at **Research notes** in the navigation | records an unresolved question or explanation, the next evidence needed, the reason, an actor label (attribution only; a "simulated test action" checkbox marks automated actions), the claim version it refers to and evidence references; corrections are new linked notes that retain the earlier text; a note changes no claim field or digest, resolves no outcome and reopens no withdrawn commitment |
| Notes beside the comparison / calculation | claim page sections 3 and 4 | current research notes are shown beside COMPARABLE and INCOMPARABLE comparisons and beside a missing outcome or a withdrawn commitment; the amendment's own explanation / next-evidence / source-discrepancy notes are now shown in the INCOMPARABLE branch too, each with its version link |
| Honest note timing | claim page as-of replay (`?as_of=`) | notes carry no source availability, so an as-of view shows only notes recorded at or before the cutoff; later notes are listed separately under "Later annotations — NOT contemporaneous" with their actual local action times |
| Dataset coverage view (§4) | **Dataset coverage** in the navigation; machine-readable `/dataset.json` | one row per frozen claim derived from stored records: issuer, metric, fiscal period, stable identifiers, versions and lineage, fictional / retrospective / eligibility status (eligibility = the recorded eligibility note or NOT_RECORDED), original target and revisions, corrections and withdrawals, outcome, computed result, reviewer labels and disagreement, unresolved reasons, availability precision and observation times, rule/units/comparison limits, rights restrictions and withheld excerpts, notes, coverage gaps and known omissions; an empty workspace shows honest empty coverage |
| Reproducible dataset snapshot | Dataset coverage → **Build dataset snapshot export**; verify under **Verify an export** in a fresh workspace | a verifiable zip (rows + the claim content they derive from); the verifier re-derives every row, the counts/gaps and the snapshot identity; earlier snapshots are retained and the view identifies what changed since the last one |
| Export retention | claim export (unchanged workflow) | every claim export now carries `research_notes` (with correction chains), the claim's `dataset_row` and the cited source-registration events; the fresh verifier re-derives notes and the row; exports written before notes existed still verify and are reported as such; unknown schema versions are refused explicitly |

Not built (by order): automated rival generation, action ranking, notification service, a data platform, crawler, paid API, alternate persistence or multi-tenant service.

## 2. Verification of the changed behaviour

| Check | Result |
|---|---|
| `pytest tests` on the candidate tree | 256 passed in 10.67s |
| new regression suites | `tests/test_v8_research_notes.py` (store: create/correct without changing identity, retry once, conflict, torn tail, withdrawn and missing-outcome visibility, as-of timing; export retention + re-derivation, tampered note MISMATCH, pre-notes export SUCCESS, unknown format UNSUPPORTED; server: form, INCOMPARABLE branch, later annotations, inert text, null Origin refused) and `tests/test_v8_dataset.py` (empty coverage, rows across fixture shapes, eligibility/retrospective from records, retained snapshot + diff, dataset export re-derivation + forged row, page empty state, installed resources) |
| Python 3.10 (declared minimum) | every workbench module compiles on a real 3.10 interpreter; three pre-existing PEP 701 f-strings (V8-002/V8-003 code) removed; `test_packaged_modules_compile_on_minimum_python` added (the static gate is a proxy and had missed them) |
| pyflakes, leak sweep, minimum-Python static gate | clean / OK |
| language rail (pages mode) applied to the workbench UI strings | flags the word "proof" in negated phrases ("not causal proof", V8-002 wording; "not proof of independent human review", V8-004 attribution text). The rail governs public pages, not the local UI; wording left unchanged this order and listed for the freeze-day wording review (a rewording changes rendered pages and would need the journeys re-run on the reworded candidate) |
| Browser journey, fixtures, Chromium 151.0.7922.34 on `91d9a2110526` | seven steps **7/7**; research_notes **DEMONSTRATED (7+8 assertions)**; dataset **DEMONSTRATED (6+4 assertions)**; sci **BLOCKED** |
| Browser journey, real-source retrospective replay on `91d9a2110526` | seven steps **7/7**; research_notes **DEMONSTRATED (2+1 assertions)** (eligibility note, discrepancy note, timing); dataset **DEMONSTRATED (1+1 assertions)** (row: real source, RETROSPECTIVE, NOT_ELIGIBLE_UNDER_V8_001_CRITERIA, OUT_OF_RANGE, withheld press-release excerpt) |
| Installed artifacts (development builds, 7.0.1-labelled) | wheel `01966bdc7f2f517e…` (815,780 B): fixtures 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci BLOCKED; real-source 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci BLOCKED · sdist `a397130a951f3010…` (4,965,024 B): fixtures 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci BLOCKED; real-source 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci BLOCKED · twine check rc 0 · result **PASS** |

Unchanged behaviour reuses the passing V8-003 evidence (boundaries, packaging rules, publisher suites, rehearsal, gate run). The full suite was run because the
store, export and server modules changed; the calendar/2028/release-replay finding was not reopened.

## 3. Export and resource compatibility

- Claim exports: format `yuclaw-commitment-export/1` unchanged; the canonical content gains `research_notes`, `dataset_row` and the cited `SOURCE_REGISTERED` events
  (all inside the canonical digest). Exports written before V8-004 verify unchanged; the verifier reports `recompute-notes: not present in this export (written
  before research notes existed)` and `recompute-dataset-row: not present …` instead of reinterpreting them. Any other `format` value is refused as UNSUPPORTED.
- Dataset snapshot exports: new format `yuclaw-commitment-dataset/1` (`dataset.json` + manifest + VERIFY.md + schema copy), verified by the same command and page.
- Journal: one additive event kind `RESEARCH_NOTE_RECORDED`; no migration of existing workspaces is needed and none is performed (no destructive change; backups stay
  canceled).
- Resources: the workbench reads only its packaged resources (schema copy, fixtures); nothing is read from the checkout at runtime (`test_installed_resources_only`).

## 4. Enabled-feature matrix (8.0.0 scope)

| Workstream | Enabled 8.0.0 deliverable | Status | Implementation and interface | Evidence |
|---|---|---|---|---|
| GOV | Scope, baseline, product decisions, gate mapping | **IMPLEMENTED** | scope frozen (`v8/scope/`), v7.0.1 baseline preserved, inherited-gate map (`v8/V8-001/inherited_gates.json`), gate run on the branch (`v8/V8-003/gates.json`); mission/vision unchanged; no scope expansion, no release authorization | V8-001/V8-003 records |
| DAT | Bounded disclosure ingestion; original bytes; source version; passage; availability + retrieval; provenance + rights | **IMPLEMENTED** | `v8/workbench/ingest.py` (allow-list, https only, bounded body, no cross-host redirect, EDGAR acceptance availability); records `v8/V8-003/sources/`; UI step 1 `/source` | V8-003 scorecard_mchp (step 1), `tests/test_v8_workbench_boundaries.py::TestIngestBoundaries` |
| CLM | Typed commitment: range, currency, scale, fiscal period, basis, issuer, version, resolution rule; unknown/incomparable fields block | **IMPLEMENTED** | `v8/workbench/schema.py`, `store.freeze_claim/amend_claim`; UI `/claim/new`, amendments on the claim page | fixtures journey step 2 (DEMONSTRATED), real-source step 2 (DEMONSTRATED); `tests/test_v8_workbench_store.py`, `test_v8_commitment_fixtures.py` |
| Comparison (minimal RIV/ACT) | Original vs revised side by side; basis checks; unresolved explanation + next-evidence notes; no automated rival generation or ranking | **IMPLEMENTED** | `calc.compare_versions`; amendment notes shown in BOTH branches with their version link (V8-004 fix); research notes (`store.record_note`, `/claim/<id>/note`, `/notes`) with unresolved question, next evidence, reason, actor label, evidence refs, corrections | fixtures journey step 3 (DEMONSTRATED) + research_notes feature DEMONSTRATED (7+8 assertions); `tests/test_v8_research_notes.py` |
| CHK | Deterministic unit/basis/period checks and outcome-vs-range calculation with visible inputs and formula | **IMPLEMENTED** | `v8/workbench/calc.py`, `money.py`; claim page section 4; recomputed by the verifier | fixtures step 4 (DEMONSTRATED), real-source step 4 (DEMONSTRATED); `tests/test_v8_workbench_calc.py` |
| TIM | As-of source view, immutable revisions, correction history, reviewer actions; no backdated knowledge | **IMPLEMENTED** | `store.visible` (source availability for source-bearing events; local action time for notes); claim page as-of replay; later annotations listed separately with action times; claim page shows source observation time | fixtures step 5 (DEMONSTRATED), note-timing assertions in research_notes DEMONSTRATED (7+8 assertions); `TestNotesStore.test_note_timing_is_honest_in_as_of_views` |
| SET | Narrow commitments-and-outcomes dataset; row provenance; correction status; deterministic snapshot and export | **IMPLEMENTED** | `v8/workbench/dataset.py` (rows from stored records, empty coverage, snapshot identity without time, diff), UI `/dataset`, `/dataset.json`, `Build dataset snapshot export`; verifier re-derives rows (`export._verify_dataset_export`); per-claim `dataset_row` in every claim export | fixtures dataset feature DEMONSTRATED (6+4 assertions); real-source dataset feature DEMONSTRATED (1+1 assertions); `tests/test_v8_dataset.py`; installed: wheel 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci BLOCKED |
| SCI | Typed adapters to the supported scientific kernel; explicit eligibility; unresolved outcomes | **BLOCKED** | not implemented: the reference bundle (INPUTS.md, MANIFEST.json, five `reference/v4/science/*.py` files from preview base c34e19bf) is not on this host; no placeholder tab, no invented kernel | `v8/V8-004/sci_status.json` (exact missing inputs, searched locations, ready-when-available steps); journey `sci` feature = BLOCKED |
| UX | One connected browser workbench: source, claim, comparison, calculation, history, adjudication, export (+ notes, dataset) | **IMPLEMENTED** | `v8/workbench/server.py`: navigation Workspace · 1 Source · 2 Typed claim · Research notes · Dataset coverage · Verify · Journal; plain HTML forms, CSP no scripts; useful empty states; specific blocking reasons | fixtures 7/7 + features; real-source 7/7 + features; screenshots in the private record |
| INT | Actual v7 adapters, local persistence, transactions, safe (additive) migrations, interrupted-job handling, restricted file/network access, bounded jobs | **IMPLEMENTED** | v7 contracts/storage reuse; append-only digest-chained journal with op-ids and one re-entrant lock; torn-tail recovery; additive event kind `RESEARCH_NOTE_RECORDED` (older exports verified explicitly as pre-notes, unknown formats refused); loopback bind, Host/Origin/CSRF, bounded bodies, in-memory archive checks; packaged resources only | `tests/test_v8_workbench_boundaries.py`, `test_v8_workbench_store.py`, `test_v8_dataset.py::test_installed_resources_only`; installed runs: wheel True, sdist True |
| REL | Publisher repairs, reproducible artifacts, current evidence, accurate notes and branding | **PARTIAL** | publisher `publish_v800.py` drafted and rehearsed with fakes (V8-003); reproducible development builds (this record); draft notes (V8-003) need the V8-004 functions added at freeze; version surfaces still 7.0.1; release policy, Gate #15 decision, gate-6 calendar identity and final artifacts pending | `v8/V8-003/README.md` §5/§6 and candidate-freeze plan; `v8/V8-004/packaging.json` (development builds) |

Experimental, deferred and canceled (unchanged): **COM, PRC, SHD, EVO** — EXPERIMENTAL, absent from the distribution, default-off, not depended on;
**CTL, RES, full RIV/ACT, RND, platform accounts, billing, real-user pilot** — DEFERRED beyond 8.0.0 (no endpoints, tabs or dependencies);
**backup functionality** — CANCELED by the owner (existing data, journals, snapshots and exports preserved). Core access controls, inert rendering, file restrictions
and packet validation stay mandatory without Shield. The seven-step score alone does not establish that every enabled function is finished; the matrix above does.

## 5. Missing inputs and blockers

1. **SCI — BLOCKED.** The reference bundle is absent on this host: no `INPUTS.md`, no `MANIFEST.json`, none of `reference/v4/science/{__init__,contracts,statistics,store,evidence}.py`
   (preview base `c34e19bf` exists locally but carries no `v4/science` tree; the preview modules are uncommitted work). Searched: `internal/v8/`, the worktree and the
   production checkout, the home directory to depth 4. Nothing was faked: no tab, no button, no invented kernel. Steps ready for when the bundle arrives are listed in `sci_status.json`.
2. Release-path items carried from V8-003 (separate queue): version surfaces at 7.0.1, gate-6 calendar identity, gate-11 restage re-measurement, weekly-note render at freeze, release policy (D1/D2) not recorded.
3. Threat to the 2026-09-18 feature-completion target: SCI cannot complete without the bundle; every other enabled function is implemented and demonstrated.

## 6. Next bounded action

Receive and verify the SCI reference bundle (INPUTS.md, MANIFEST.json, digests), preserve the originals in the private record, adapt only the five selected modules,
and deliver the bounded browser report/replay with one supported fictional example and one refused example, then re-run the journeys and the clean-install on that candidate.

## 7. Separate release-preparation checklist (unchanged from V8-003)

1. Owner decisions: 8.0.0 allocation document (D1) and Gate #15 route (D2; route B needs the owner's own 8.0.0 wording bound into the publisher).
2. Calendar-identity decision so gate 6 can be freshly replayed.
3. Freeze day in production: bump every G2 surface to 8.0.0, render pages at the badge (also refreshes the weekly note), regenerate the README transcript and README_PYPI, re-measure gate 6 and the restage, regenerate manifest and two-tier notes (adding the V8-004 functions) with `--release-policy`; zero RED.
4. Re-run both journeys (with feature demonstrations) and the clean-install tool on the frozen commit.
5. Authorization sentence naming the frozen sha and tree; publisher `build` once; frozen digests must equal the clean-install digests for the same commit before any public write; if the candidate changes after acceptance, re-verify the affected behaviour and the exact final bytes.
6. Gate B 2026-09-19 evening on the frozen commit; freeze 2026-09-20; release readiness 2026-09-21 subject to the concrete release decision.

Private record: `internal/v8/v8_004_20260916T033140Z/` (journey screenshots and workspaces, clean-install dist and environments, review diff, checks). Evidence inventory: `evidence_index.json`.
English-only product content; YUCLAW in authored text; approved logo bytes, canonical mission/vision blocks and historical evidence unchanged.

Research and education only. Not investment advice.
