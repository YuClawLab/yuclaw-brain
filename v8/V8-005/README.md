# V8-005 — complete the scientific workbench function (local implementation and evidence only)

Recorded 2026-09-16. Branch `codex/v8-integration`, continued from V8-004 (`9f340ccd`). Integrated candidate with browser and
installed-artifact evidence: **`d70edd02062c`**; this record's HEAD `d70edd02062c` (tree `c581fd5aa319`). Nothing pushed, tagged, deployed, uploaded or messaged;
`release_authorized` stays **false**; Gate #15 keeps its actual status (MANUAL_REVIEW, NOT SATISFIED; no 8.0.0 exception; the 7.0.1 exception is not inherited);
human benefit **PENDING**. Calendar/2028 and other release-path findings stay in the separate release queue (not investigated here, not hidden).

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

Commits of this order (oldest first), all local and unpushed:
- `d70edd02` packaging: exclude every v8 order-record directory by pattern (v8/V8-*) from the wheel and sdist — the V8-004 record shipped in the development build once it was committe
- `b4343989` v8: journey — the claim-page linked-record assertion checks the rendered wording and the unchanged claim result (V8-005)
- `28fc563d` v8: scientific report/replay through the adapted kernel (V8-005) — kernel adapted from the verified owner bundle (paired Brier improvement, Hoeffding-mixture e-value, fro

## 1. Input package

`YUCLAW-V8-005-SCI-inputs.zip` (24,270 bytes) received by SCP into a private staging directory; SHA-256 `194143f33775ab8c547a0f03d8a5d2f9317c7c32612a455c7d400db9a3b31a77` equals the
owner-provided value; extracted with traversal, duplicate-member and symlink checks; every `MANIFEST.json` entry verified by relative path, byte count and SHA-256
with exact membership (10 payload files; the manifest itself excluded as declared). Result: **VERIFIED**. The originals are preserved unmodified
in the private input record. Hash agreement establishes byte identity with these inputs, not source authenticity or scientific validity.

## 2. Kernel adaptation (what was adapted, from which versions)

The five reference modules are snapshots of uncommitted preview work on base `c34e19bffb1a` (the base commit does not contain them).
Adapted into `v8/workbench/sci/` with the supported contract unchanged: unchanged: paired_brier_improvement per unit; log e-value = log mixture over lambdas (1/16, 1/8, 1/4, 1/2, 1) of Hoeffding test supermartingales under a bounded conditional-mean null; threshold -log(alpha) with a frozen family allocation; statuses INVALIDATED / EXPLORATORY_ONLY / CONDITIONAL_EVIDENCE / BUDGET_EXHAUSTED_INCONCLUSIVE / AWAITING_OUTCOME / ACCUMULATING; no new statistical method.

| adapted module | from | change |
|---|---|---|
| `sci/__init__.py` | `v4/science/__init__.py` | same SCHEMA_VERSION; adds ADAPTED_FROM provenance and kernel_identity() (sha256 over the packaged contracts/statistics/store sources) |
| `sci/statistics.py` | `v4/science/statistics.py` | finite, log_e_value, brier_improvement, by_adjust unchanged; isotonic_scores and preference_cycles (diagnostic helpers of the old CLI's diagnose command) not adapted — no product path uses them |
| `sci/contracts.py` | `v4/science/contracts.py` | validation rules, reducer semantics and error messages unchanged |
| `sci/store.py` | `v4/science/store.py` | replay() unchanged; certificate() renamed report() with the same content except the not-advice sentence names a report; the SQLite Journal class and its clock are NOT adapted (the workbench never opens caller-supplied database files; replays persist in the workspace journal); build_events() added as a pure in-memory builder applying the same reducer rules |
| `sci/evidence.py` | `v4/science/evidence.py` | same availability/identity/duplicate rules over the workbench's source records (accession, source_hash, available_as_of) instead of the published EvidenceObject corpus by ticker |
| `sci/adapter.py` | `new (workbench integration)` | bounded strict JSON parsing (size, events, depth, duplicate keys, non-finite numbers), envelope contract, kernel_run, specific ineligibility reasons mapped from kernel refusals plus pre-scan (monetary fields, adjudication claims), link verification against workspace objects, replay status, standing limits |
| `resources/sci/template_manifest.json` | `docs/v8/examples/manifest.json` | byte-identical copy (exploratory synthetic template); the other example journals are fixtures generated from it by the workbench build |
| `tests/test_v8_sci.py` | `tests/test_science_v8.py` | core cases adapted (numerics, contract rejections, ordering/pending/duplicates/clock, tampering/truncation/semantic replay, statuses/crossing/invalidation/budget/exploratory/minimum, evidence inspection); the old CLI, dispatcher, diagnose and SQLite cases are not adapted (missing inputs by design); an in-memory Journal stand-in replaces the database |

Not adapted by design: v4/science/cli.py (old CLI; imports optional/deferred modules unconditionally); SQLite journal persistence; diagnostic helpers isotonic_scores / preference_cycles; COM/PRC/SHD/EVO and deferred modules. License: Apache License 2.0 (reference/LICENSE retained in the private input record; the integration branch is Apache-2.0). Reference digests are recorded in `adaptation.json`.
Installed kernel identity: `5b3e0d221c2200b2f88d14e4efb24d1d8854e27c05c45d8abacbd2fdc31492e1` (sha256 over the packaged contracts/statistics/store sources; shown on every record page).

## 3. Function implemented and its browser entry point

**Scientific report** in the navigation (`/sci`). The page states the supported contract, the kernel identity and the standing limits, lists every recorded
replay, and offers a form: a packaged fictional example or a pasted journal (JSON event list in the kernel's own event format, optionally wrapped with
`expected_root`, `links` to a claim/version/source and `declared` flags), an optional link to a frozen claim, an actor label and a "simulated test action" checkbox.
"Replay through the kernel and record" parses strictly (size ≤ 256 KB, ≤ 2000 events, bounded depth, duplicate keys and non-finite numbers refused; nothing is
executed, opened as a file or fetched), replays the events through the kernel — every hash re-derived, every statistic recomputed; a supplied report is never
trusted — and records the outcome as an append-only `SCI_REPLAY_RECORDED` event under the existing session, CSRF, null-Origin, operation-identifier and lock rules.
The record page (`/sci/S<n>`) shows the input identity, kernel and method identity, the supported metric, per-claim status (pending, inconclusive, invalidated,
exploratory, conditional evidence), the reasons when the input is ineligible, warnings, link verification results and what the computation does and does not
establish. Linked records are listed on the claim page; the claim's own range, digests and result never change.

Specific ineligibility reasons: monetary amounts or ranges supplied as probabilities (`MONETARY_OR_OUT_OF_RANGE_PROBABILITY`, `MONETARY_RANGE_SUPPLIED`), missing
prediction pairs, changed targets (unregistered or re-registered claims; a linked version that has since been superseded is reported as `TARGET_CHANGED`),
unsupported metrics and schemas, integrity and checkpoint failures, timing-rule violations, reused sources, unsupported adjudication claims. Replay status is
`EXPLORATORY_REPLAY`, `PROSPECTIVE_CLAIMED_NOT_VERIFIED` (imported timestamps cannot establish commitment before outcome) or `RETROSPECTIVE_REPLAY` (declared, or
linked to a retrospective financial record such as the Microchip replay); no IN_RANGE result and no retrospective example becomes scientific improvement or
prospective evidence.

## 4. Verification

| Check | Result |
|---|---|
| `pytest tests` on the candidate tree | 268 passed in 11.80s |
| `tests/test_v8_sci.py` | 12 cases: adapted kernel core (numerics incl. exact supermartingale enumeration, contract rejections, ordering/pending/duplicates/clock, tampering/truncation/semantic replay, statuses/crossing/invalidation/budget/exploratory/minimum sample, evidence inspection, kernel identity); strict bounded input; specific reasons on the packaged examples and on integrity, checkpoint, changed-target, adjudication-claim and monetary-field inputs; links and replay status against a workspace; retry-safe persistence and export recomputation (semantic and numerical tampering caught; pre-SCI exports still verify); protected browser surface (null Origin refused, refusals, inert rendering) |
| Python 3.10 (declared minimum) | every workbench module including `sci/` compiles on a real 3.10 interpreter; pyflakes clean; leak sweep OK; CJK none |
| Browser journey, fixtures, Chromium 151.0.7922.34 on `d70edd02062c` | seven steps **7/7**; research_notes **DEMONSTRATED (7+8 assertions)**; dataset **DEMONSTRATED (6+4 assertions)**; **sci DEMONSTRATED (6+6 assertions)** (supported exploratory example, refused monetary and unsupported-metric inputs, prospective-mode fixture linked to the frozen claim with the link verified as bytes, envelope refusal, export with the record verified in a fresh workspace, semantic tamper refused) |
| Browser journey, real-source retrospective replay on `d70edd02062c` | seven steps **7/7**; research_notes **DEMONSTRATED (2+1 assertions)**; dataset **DEMONSTRATED (1+1 assertions)**; **sci DEMONSTRATED (1+1 assertions)** (a replay linked to the Microchip claim is RETROSPECTIVE_REPLAY with the warning; never prospective; the claim's OUT_OF_RANGE results are not units) |
| Installed artifacts (development builds, 7.0.1-labelled) | wheel `32dc64ebf06db454…` (849,966 B): fixtures 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED; real-source 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED · sdist `ad1204edb3ee834f…` (4,992,082 B): fixtures 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED; real-source 7/7 · research_notes DEMONSTRATED, dataset DEMONSTRATED, sci DEMONSTRATED · packaged `sci/` resources present · twine check rc 0 · result **PASS** |
| Language rail wording | narrow copy changes with meaning preserved in rendered strings (`proof` → establish/evidence; `validated` → quality established; the report is not called a certificate); remaining hits are docstrings and the calculator's comparison note that is packed in every export (unchanged so pre-V8-005 exports still recompute) |

## 5. Export and resource compatibility

- Claim exports (`yuclaw-commitment-export/1`) gain `sci`: each linked record with its input, identities, status, reasons, report, links, warnings, kernel identity and
  standing limits, plus the `SCI_REPLAY_RECORDED` events. The fresh verifier re-parses the packed input and recomputes the report or the refusal (`recompute-sci`);
  links are packed data and are not re-verified against the verifying workspace. Exports written before V8-005 verify unchanged and are reported as such; unknown
  schema versions are refused. Dataset snapshot exports carry all scientific records at top level, recomputed the same way; rows are unchanged.
- Journal: one additive event kind; no migration, no destructive change; backups stay canceled.
- Resources: the kernel and the example journals ship inside the package (`v8/workbench/sci/`, `v8/workbench/resources/sci/`); nothing is read from the checkout.

## 6. Enabled-feature matrix (8.0.0 scope)

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

Experimental, deferred and canceled (unchanged): **COM, PRC, SHD, EVO** absent and default-off; **CTL, RES, full RIV/ACT, RND, platform accounts, billing,
real-user pilot** deferred; **backup functionality** canceled. A scientific result grants no trade, training, model change, deployment, publication or other
external action.

## 7. Remaining blockers (release queue, unchanged)

Version surfaces at 7.0.1 (freeze-day bump), gate-6 calendar identity (not investigated here), gate-11 restage re-measurement, weekly-note render at freeze,
release policy (D1/D2) not recorded, Gate #15 NOT SATISFIED; the two-tier notes must add the V8-004 and V8-005 functions at regeneration. The comparison note and
docstring wording flagged by the pages-mode rail is listed for the freeze-day wording review (a change there alters packed method strings).

## 8. Start instructions

```
python3 -m v8.workbench serve --workspace <dir>/research --port 8765        # open http://127.0.0.1:8765/ → Scientific report
python3 -m v8.workbench serve --workspace <dir>/fresh --port 8766           # fresh workspace: Verify an export
python3 -m v8.workbench verify-export <export.zip>                         # offline; recomputes notes, rows and scientific records
```
Private record: `internal/v8/v8_005_20260916T041331Z/` (journeys with screenshots, clean-install dist and environments, review diff, checks); input originals in the private
input record. Evidence inventory: `evidence_index.json`. English-only product content; YUCLAW in authored text; approved logo bytes, canonical mission/vision
blocks and historical evidence unchanged.

Research and education only. Not investment advice.
