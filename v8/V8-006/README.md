# V8-006 — release preparation for owner review (nothing published; decisions pending)

Recorded 2026-09-16. Branch `codex/v8-integration`; this record's HEAD `2cc7a7b9743e` (tree `14b086ac0941`); implementation candidate with browser and
installed evidence **`d70edd02`** (V8-005; unchanged by this order — no packaged code changed). Nothing pushed, tagged, deployed, uploaded or messaged;
`release_authorized` stays **false**; Gate #15 stays MANUAL_REVIEW / NOT SATISFIED; human benefit **PENDING**. **Release readiness is NOT reported**: required
gates and owner decisions are unmet (section 8).

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

Commits of this order (oldest first), all local and unpushed:
- (none yet)

## 1. Enabled feature scope — confirmed from the existing records (no demonstration re-run)

| Workstream | Enabled 8.0.0 deliverable | Status | Implementation and interface | Evidence |
|---|---|---|---|---|
| GOV | Scope, baseline, product decisions, gate mapping | **IMPLEMENTED** | scope frozen (`v8/scope/`), v7.0.1 baseline preserved, inherited-gate map, gate run on the branch (`v8/V8-003/gates.json`); mission/vision unchanged | V8-001/V8-003 records |
| DAT | Bounded disclosure ingestion; original bytes; passage; availability + retrieval; provenance + rights | **IMPLEMENTED** | `v8/workbench/ingest.py`; UI step 1 `/source`; records `v8/V8-003/sources/` | V8-003 scorecard_mchp step 1; ingestion boundary tests |
| CLM | Typed commitment with range, currency, scale, fiscal period, basis, issuer, version, resolution rule; unknown fields block | **IMPLEMENTED** | `schema.py`, `store.freeze_claim/amend_claim`; UI `/claim/new` | fixtures step 2 DEMONSTRATED; real-source step 2 DEMONSTRATED |
| Comparison (minimal RIV/ACT) | Original vs revised side by side; basis checks; unresolved explanation + next-evidence notes; research notes | **IMPLEMENTED** | `calc.compare_versions`; amendment notes in both branches; research notes (`/claim/<id>/note`, `/notes`) | fixtures step 3 DEMONSTRATED; research_notes DEMONSTRATED (7+8 assertions); `tests/test_v8_research_notes.py` |
| CHK | Deterministic unit/basis/period checks and outcome-vs-range calculation with visible inputs and formula | **IMPLEMENTED** | `calc.py`, `money.py`; claim page section 4; recomputed by the verifier | fixtures step 4 DEMONSTRATED; real-source step 4 DEMONSTRATED |
| TIM | As-of view, immutable revisions, correction history, reviewer actions; honest note timing | **IMPLEMENTED** | `store.visible`; as-of replay; later annotations listed separately | fixtures step 5 DEMONSTRATED; note-timing assertions |
| SET | Commitments-and-outcomes dataset; row provenance; correction status; deterministic snapshot and verifiable export | **IMPLEMENTED** | `dataset.py`; `/dataset`, `/dataset.json`, dataset snapshot export; verifier re-derives rows (and now scientific records) | fixtures dataset DEMONSTRATED (6+4 assertions); real-source dataset DEMONSTRATED (1+1 assertions); `tests/test_v8_dataset.py` |
| SCI | Typed adapters to the supported scientific kernel; explicit eligibility and unresolved outcomes | **IMPLEMENTED** | `v8/workbench/sci/` (kernel adapted from the verified bundle; identity `5b3e0d221c2200b2…`) + `sci/adapter.py`; UI **Scientific report** (`/sci`, `/sci/<id>`), replay form with packaged examples; `SCI_REPLAY_RECORDED` events; records in claim and dataset exports recomputed by the fresh verifier | fixtures sci DEMONSTRATED (6+6 assertions); real-source sci DEMONSTRATED (1+1 assertions); installed wheel 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED · sdist 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED; `tests/test_v8_sci.py` (12 cases) |
| UX | One connected browser workbench (+ notes, dataset, scientific report) | **IMPLEMENTED** | navigation: Workspace · 1 Source · 2 Typed claim · Research notes · Dataset coverage · Scientific report · Verify · Journal; plain HTML forms, CSP without scripts | fixtures 7/7 + features; real-source 7/7 + features |
| INT | v7 adapters, local persistence, transactions, additive migrations, interrupted-write handling, restricted file/network access, bounded jobs | **IMPLEMENTED** | append-only journal with op-ids and one re-entrant lock; additive event kind `SCI_REPLAY_RECORDED`; bounded JSON input, nothing executed/opened/fetched; packaged resources only | boundary/store/sci suites; installed runs wheel True, sdist True |
| REL | Publisher repairs, reproducible artifacts, current evidence, accurate notes and branding | **PARTIAL** | publisher drafted and rehearsed (V8-003); development builds reproducible; version surfaces still 7.0.1; release policy, Gate #15 decision, calendar identity and final artifacts pending (separate release queue) | `v8/V8-003/README.md` candidate-freeze plan; `v8/V8-005/packaging.json` |

Evidence identities are unchanged: V8-002 `a41dc39e` (7/7), V8-003 `9efdd52d` (7/7 + real-source 7/7), V8-004 `91d9a211` (7/7 + notes, dataset), V8-005 `d70edd02`
(7/7 + notes, dataset, SCI from the checkout and from the installed wheel `32dc64ebf06db454…` and sdist `ad1204edb3ee834f…`; fixtures 7/7, real-source 7/7).
COM/PRC/SHD/EVO stay absent experimental modules; CTL, RES, full RIV/ACT, RND, accounts, billing and the real-user pilot stay deferred; backups stay canceled; no human benefit is claimed.

## 2. Usable local candidate and release materials

- **Startup path and navigation** (including Scientific report): `START.md`.
- **Candidate version surfaces prepared in private staging** (not applied to the branch): staged commit `ca50b42efd83` on top of HEAD `2cc7a7b9` carries 8.0.0 on
  every gate-checked surface (pyproject, release manifest, capabilities, evidence index, llms.txt, CITATION.cff, README version/link/transcript from an 8.0.0
  wheel, CHANGELOG entry, 98 badge pages re-pinned, README_PYPI regenerated). Checks on the staged tree: G2 OK on 12 surfaces + 98 badge pages (with `--dist`),
  header layout OK, transcript OK, README/PyPI OK, copy consistency OK. The exact change for review: `candidate_8.0.0_version_surfaces.excerpt.diff` (tracked
  excerpt) and the full patch in the private record (`candidate_8.0.0_version_surfaces.patch`, 108 files). **Applying it to the branch is the candidate designation
  and needs the owner's order (the 7.0.1 precedent).** The production refresh chain was not run and the production checkout was not touched: the weekly note and
  today's-evidence block can only be rendered there, which is why gate 14 stays RED in staging (section 5).
- **Preliminary staged build** (identity only; not a release artifact, not the final set): `yuclaw-8.0.0-py3-none-any.whl` `aa988727055aa81f6fabc267c7acaf9f55cd73d0c0b5585d0ebd4c8ffae30b5c` (849,964 B),
  `yuclaw-8.0.0.tar.gz` `bc974991c5e12433bfd36bb2a38e4fcb2f147b04d92965729f34534196e5f9e9` (4,992,067 B); twine check PASSED; G2 over the pair OK. Reproducibility check against the
  publisher rehearsal's independently bumped build (fixed source-date epoch): wheel byte-identical, sdist different (the staged tree also regenerates the derived preview surfaces, which ship in the sdist).
  **Correction recorded by V8-007 (2026-09-16; the sentence above is left as written):** the comparison object is the V8-006 *re-run* of the rehearsal test introduced in V8-003 (rehearsal commit `9923712e` on `2cc7a7b9`, 2026-09-16T04:59:18Z, wheel `aa988727…`), not the historical V8-003 rehearsal (`9509480e` on `9efdd52d`, wheel `ad07972e…`, a pre-SCI build). The staged commit `ca50b42e` also tracks a stray absolute-path symlink `output/output` swept up by the bump's `git add -A` (not packaged). Both are superseded by the coherent candidate `479a5aef` (branch HEAD `ab2c5c88` + the same version patch, patch-id `27267a97…`), which reproduces the identical wheel and sdist bytes — see `v8/V8-007/provenance.json` and `coherent_candidate.json`.
- Development packages labelled 7.0.1 (V8-003/V8-004/V8-005) remain development builds; none is called an 8.0.0 release candidate.
- **Release notes**: Tier-2 draft `release_notes_8.0.0_DRAFT.md` (adds research notes, dataset coverage, scientific report/replay, export recomputation, packaging; keeps the
  fictional / retrospective / simulated-review / computational-verification distinctions); Tier-1 internal draft in the private record (`gates/release_notes_8.0.0_INTERNAL_DRAFT.md`).

## 3. Gate-6 evidence defect closed (superseding correction; nothing historical changed)

The V8-003 gate-6 statement carried the 7.0.1 replay hashes under the generator's fixed "fresh replays this session" wording. `gate6_correction.json` supersedes it
and preserves the original. A fresh NO-WRITE replay ran three times in a disposable worktree with the manifest-pinned historical calendar taken from trusted
repository history (`v3/u350/market_calendar.py` at `e988084b`, sha256 `c51d05fa334899d6…` = the manifest's pin): exit codes
[0, 0, 0], output sha256 `0b2ac8a5967b13aa…` = the canonical artifact — **REPRODUCED**, bound to tool sha256
`994c27a003d9d4fd…`, method hash `fc2779b55aee5f67…`, frozen inputs `5a7a505814e61c32…`, Python 3.12.3, database blocked.
The current tree's calendar (changed `49495fd1`) is still refused by the guard (exit 1), as registered. No manifest, hash, calendar, artifact or registry line was
altered. If a fresh replay must run from the current tree without the pinned calendar, a protocol note is needed; its concrete comparison and proposed text are in
the correction record for the owner's review — nothing was waived or bypassed, and no wider calendar investigation was made.

## 4. One final artifact set (release logic)

- `tools/yuclaw_v8_clean_install.py` now writes an `artifact_identity.json` (version, commit, tree, names, sha256, sizes, build epoch) next to every pair it builds
  (label PRELIMINARY) and accepts `--artifacts DIR` to adopt an already-built pair: the record must name the requested commit and its tree and every file must
  match by sha256 and size, verified before anything is copied or opened; mismatches STOP. Tests: `test_adopt_refuses_mismatched_identity_or_bytes`.
- `publish_v800.py` gains `adopt DIR`: same preconditions as `build`; the identity record must bind the AUTHORIZED sha and tree and the release version/file names;
  bytes are verified before freezing; the frozen record is marked FINAL and names what it was adopted from; a second adopt or a build after it is refused (one final
  set). Tests: 21 passed (`test_adopt_binds_identity_and_bytes_and_refuses_mismatches` added). Mocked rehearsal re-run on the changed publisher (identity
  `78cc839c52d50295…`): real build, 16 verification checks incl. the v8 workbench 7/7 from both artifacts, fake transition with interruption and resume — passed.
- Real-pair exercise: ADOPTED pair verified byte-for-byte against its identity record (commit `d70edd02062c`, wheel `32dc64ebf06db454…`, sdist `ad1204edb3ee834f…`), installed without a build: wheel 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED / 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED; sdist 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED / 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED; result **PASS**.
- Typed authorization, prior-release tripwires (6.0.0, 6.0.1, 7.0.0, 7.0.1), journal operation identifiers and mocked destinations are unchanged. A local run grants
  no external-write permission.

## 5. Gate preparation on the staged 8.0.0 candidate (actual generator output)

Generator: `tools/yuclaw_release_state_v6.py --evidence <record>/gates/evidence_v8_candidate_staged.json` on the staged tree `ca50b42efd83` (8.0.0 surfaces), no
`--release-policy` (none recorded). Evidence inputs this order: gate 6 = the fresh replay above; restage = **measured** (write_all at chain tip `ac51ddfe97eb…` in a
disposable worktree; live/registry/output trees identical; 0 preview files changed); tripwire = read-only observations 2026-09-16T04:54:53Z (no v8 tags,
GitHub latest v7.0.1, PyPI 7.0.1, live v7.0.1, origin/main 7.0.1, preview links 0).

**18 GREEN / 1 RED / 1 MANUAL_REVIEW · tripwire(pre) GREEN**

| # | requirement | result | evidence |
|---|---|---|---|
| 1 | P0 registrations valid | **GREEN** | bace258b0bbb + 74c9a12a60e3 LOCKED; module METHOD_HASH == registry; A1 file sha256 == line-81 method_hash |
| 2 | chain verifies | **GREEN** | Registry.verify_chain on load: 82 lines, tip ac51ddfe97eb709a |
| 3 | zero unexplained ledger breaks | **GREEN** | docs/ledger 84 blocks 2026-05-20..2026-09-14; sessions without a block: 0; evidence-changes gate rc=0 |
| 4 | point-in-time guard | **GREEN** | as_of endpoint hash + twice-run identity (evidence-changes gate); u350 isolation proven by attempted writes |
| 5 | no v1 historical silent rewrite | **GREEN** | chain file byte-identical to base 696d871e: True; v1 evidence_geometry.json identical to base: True (last changed 0f10c2ec 2026-07-31); Phase-6 canonical artifact identical to base: True; 02A restage  |
| 6 | dependency calculations reproducible | **GREEN** | the registered structural first-read computation reproduced byte-identically from frozen inputs (fresh NO-WRITE replays this session) |
| 7 | truncation ledger reconciles | **GREEN** | [truncation-gate] OK — 13 ledger entries (schema + anchors verified), detector clean over v3/tools (allowlist v1, 10 constants) |
| 8 | hypothesis/discovery lineage reconciles | **GREEN** | [discovery-gate] OK — 37 hypotheses <-> 37 protocol lines (bijection both directions), 33 families locked, artifact byte-identical to chain-derived rebuild; status_counts={'ACCRUING': 18, 'INCONCLUSIV |
| 9 | sequential methods pass registered fixtures | **GREEN** | anytime gate + registered fixtures selftest |
| 10 | research-state derivation reproducible | **GREEN** | [research-state-gate] OK — 132 names render registered artifacts only; byte-identical rebuild; platform C6 verdict verbatim |
| 11 | machine JSON agrees with human page | **GREEN** | [science-trust-gate] OK — 132 cards: machine JSON == human card == fresh derivation (field-for-field); research states verified against research_state.json directly; sequential panel verified against  |
| 12 | source citations resolve | **GREEN** | site-walk: all links + anchors resolve; index completeness; copy integrity |
| 13 | negative/inconclusive findings preserved | **GREEN** | discovery status_counts ACCRUING 18, INCONCLUSIVE 1, OPEN 7, REGISTERED 7, SUPERSEDED 4; questions insider-directional RETIRED, reversal-coherence OPEN, reversal-structure-dominance OPEN; reversal fir |
| 14 | language rails pass | **RED** | language rail (pages + README + COMPARISON + architecture + CHANGELOG) + leak sweep (private denylist) + no-forms + header layout (badge == package version) + weekly-note reconciliation |
| 15 | user comprehension test passes | **MANUAL_REVIEW** | consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist |
| 16 | stranger-machine reproduction passes | **GREEN** | External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0 — registered sentence "stranger-machine reproduction passes" (requires reproduction on an external (stra |
| 17 | G1 copy-consistency (canonical blocks byte-identical) | **GREEN** | [copy-consistency] OK — 8 target blocks byte-identical to their canonical sources (MISSION-VISION: sha256 c3b3d26ca94f, LOOKAHEAD: sha256 34ff23ecbef0, REPLICATION-SENTENCE: sha256 f940a6f509ab) |
| 18 | G2 version (package = badge = capabilities = index = llms = README = PyPI metadata) | **GREEN** | [release-manifest] OK — G2 version 8.0.0 on 9 surfaces + 98 badge pages |
| 19 | G3 base URL (capabilities = index = llms = release_manifest.public_base_url) | **GREEN** | [release-manifest] OK — G3 base https://yuclaw.ca (77 URLs, zero github.io) |
| 20 | G4 endpoints (declared set = generated set; static 200/type/schema; wildcards by discovery) | **GREEN** | [release-manifest] OK — G4 22 endpoints declared on 3 surfaces, 31 representatives local-resolved and schema-valid |

Unmet or manual, left visible: gate 14 RED = weekly-note reconciliation (the note can only be re-rendered by the production chain at the freeze; language rail, leak
sweep, no-forms and header layout pass); gate 15 MANUAL_REVIEW / NOT SATISFIED (section 6); release policy not recorded (D1/D2).

## 6. Decision package (prepared; NOTHING recorded)

- **D1 allocation**: `D1_allocation_8.0.0_PROPOSED.json` — the exact document the policy stage accepts once the owner sets the decision to D1-ACCEPT; every
  activation INACTIVE; scope = the enabled 8.0.0 functions only.
- **D2 / Gate #15**: `D2_gate15_decision_package.md` — actual status, governing rule (route A needs a GREEN gate input from a real study; route B needs the
  owner's own 8.0.0 wording bound into the publisher), evidence, obligations, and three options (owner-authored exception; study first; hold). No route is
  selected, nothing is inherited from v7, and automated adjudication is not treated as a human study.

## 7. Validation this order

Focused: packaging suite 6 passed (adoption rules); publisher suites 21 passed; publisher rehearsal 1 passed (real build, fake destinations); the isolated gate-6
replays (3× exit 0); the restage measurement; the generator on the staged tree; the real-pair adoption run. Unchanged code and evidence reused with their original
identities; no full suite re-run for record-only edits (no packaged module changed).

## 8. Completed · technical blockers · owner decisions

**Completed**: feature scope confirmed from records; startup path and navigation; staged 8.0.0 surfaces with passing surface checks and a reviewable patch;
preliminary staged build identity (reproducible: identical to the rehearsal build); gate-6 correction with a fresh bound replay; restage measured; tripwire
observed; final-artifact-set logic in the clean-install tool and the publisher with tests and rehearsal; both notes tiers updated; D1/D2 packages prepared.

**Technical blockers (release queue)**: gate 14 weekly-note reconciliation needs the production render at the freeze; the notes' "continuing objects" and CHANGELOG
entry are regenerated by the generator with `--release-policy` once D1/D2 exist; the final artifact set does not exist yet (it is built or adopted by the publisher
from the authorized commit after the version-surface commit is applied).

**Owner decisions still needed**: (1) apply the prepared version-surface change to the branch = designate the 8.0.0 candidate (order), then freeze; (2) D1 —
record the allocation document; (3) D2 — choose a Gate #15 route (or hold); (4) optionally record the proposed A1.2 calendar note (gate 6 replays from the pinned
calendar work without it); (5) the authorization sentence naming the frozen sha and tree, after which the publisher builds or adopts the one final set.

Private record: `internal/v8/v8_006_20260916T045031Z/` (gate-6 replays, restage measurement, staging worktree and patch, staged preliminary build, generator manifest and notes,
publisher copy/diff/tests/rehearsal, adoption run). English-only product content; YUCLAW in authored text; approved logo bytes, canonical mission/vision blocks and
historical evidence unchanged.

Research and education only. Not investment advice.
