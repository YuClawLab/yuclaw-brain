# V8-003 — real-source integration and release-candidate preparation (local implementation and evidence only)

Recorded 2026-09-16. Branch `codex/v8-integration` (base v7.0.1 `696d871e`; V8-002 end `4a5c7794`). Candidate for this
record: **`9efdd52d88a3`** (tree `92fe238d09c8`). Nothing in this order pushes, tags, deploys, uploads, edits published assets, sends messages
or sets `release_authorized` (it stays **false**). Version surfaces are still **7.0.1** (development label): the bump to 8.0.0 is a freeze-day step.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

Commits of this order (oldest first), all local and unpushed:
- `9efdd52d` v8: Python 3.10-compatible expressions in the claim-page source lookup and the clean-install summary (minimum-Python gate)
- `71b958cc` v8: candidate repairs from the first clean-install and real-source runs — sdist excludes the v8 record directories (the builder picked up their README
- `1ab96298` v8: real-source path and boundary repairs — bounded ingestion tool (host allow-list, https only, bounded body, no cross-host redirect, EDGAR acceptanc
- `c924cdee` v8: V8-002 review attribution corrected — the journey's adjudications were automated test actions, neither owner nor independent review; evidence unch

## Status per section of the order

| § | Requirement | Status | Where |
|---|---|---|---|
| 1 | Close the real-data gap: Microchip Q1 FY2026 through the bounded ingestion path; verify period, metric, basis, availability, passage, identity, rights; observation times apart; retrospective label; eligibility re-run; separate browser scorecard | COMPLETE — three sources ingested; **NOT ELIGIBLE under the V8-001 criteria**; replay **RETROSPECTIVE**; scorecard **7/7** | `sources/`, `real_data_selection.json`, `scorecard_mchp.json`, `journey_mchp/` |
| 2 | Review the implementation boundaries; fix demonstrated defects with regression evidence; null Origin stays rejected | COMPLETE — 3 defects found and fixed, 12 boundary regressions | `tests/test_v8_workbench_boundaries.py`; server/store repairs |
| 3 | Correct review attribution | COMPLETE — V8-002 README and scorecard corrected (`c924cdee`); the journey runner labels its adjudications as simulated test actions | `v8/V8-002/`, `v8/workbench/journey.py` |
| 4 | Prove the workbench ships: wheel/sdist, clean installs outside the checkout, installed browser workflow and export verification, evidence bound to commit and hashes; earlier 7/7 preserved | COMPLETE on **development builds** (7.0.1-labelled); journeys **7/7** / **7/7** from the wheel and **7/7** / **7/7** from the sdist | `packaging.json`, `tools/yuclaw_v8_clean_install.py` |
| 5 | Publisher and branding: typed authorization, one build/same bytes, 6.0.x/7.0.0/7.0.1 tripwires, journal operation identifiers, mocked rehearsal; PyPI long description fixed; README canonical blocks and logo bytes preserved | COMPLETE as a draft publisher + rehearsal; PyPI description generated and validated | private record `publisher/`; `README_PYPI.md`, `tools/yuclaw_readme_pypi.py` |
| 6 | Release gates and evidence package; Gate 15 actual status; human benefit PENDING; release_authorized false | COMPLETE as a record — generator run: **18 GREEN / 1 RED / 1 MANUAL_REVIEW**, tripwire(pre) **RED**; blockers below | `gates.json`, `release_notes_8.0.0_DRAFT.md`, `evidence_index.json` |

Fixture validation, real-data quality and human benefit remain three separate questions; passing one establishes none of the others.

## §1 — Microchip: what was verified, and the limits that stay explicit

| source | form · identifier | filed | available as of (basis) | observed by the workspace | rights | passage digest |
|---|---|---|---|---|---|---|
| original guidance | 8-K EX-99.1 · `0000827054-25-000061` | 2025-05-08 | `2025-05-08T20:17:05Z` (EDGAR acceptance time (SEC submissions feed)…) | `2026-09-15T10:27:12Z` | SEC_PUBLIC_FILING | `d7e97b2b48c54038…` |
| revision | press release (GLOBE NEWSWIRE via ir.microchip.com) · `IR:ir.microchip.com:1315` | 2025-05-29 | `2025-05-30T03:59:59Z` (publisher dateline 'May 29, 2025 (GLOBE NEWSWIRE)' and page …) | `2026-09-15T10:28:25Z` | COMPANY_PRESS_RELEASE | `a584cfdd883abee6…` |
| actual | 8-K EX-99.1 · `0000827054-25-000132` | 2025-08-07 | `2025-08-07T20:20:13Z` (EDGAR acceptance time (SEC submissions feed)…) | `2026-09-15T10:29:11Z` | SEC_PUBLIC_FILING | `55b697c56b1c9536…` |

- **Source lead confirmed against the passages**: original USD 1.020–1.070 billion, revised 1.045–1.070 billion, actual 1.0755 billion. The May 29 press
  release restates the May 8 lower bound as **1.025** where the May 8 filing says **1.020**: both are registered verbatim and the amendment carries a
  `source_discrepancy` note that the workbench displays as "preserved verbatim, not corrected" and exports unchanged. Neither source was rewritten.
- **Period, metric, basis**: June 2025 quarter = fiscal Q1 2026 (2025-04-01..2025-06-30), consolidated net sales, USD; the outlook table names GAAP and
  Non-GAAP columns and lists Net Sales as a single unadjusted line, so the typed claim records basis GAAP (recorded in `real_data_selection.json`).
- **Availability vs observation**: EDGAR acceptance times for the two filings; for the press release the publisher dateline at end of day
  America/New_York (no clock time is stated; nothing is shown earlier than it was). Every source was first observed on 2026-09-15 — after the outcome
  was public — so the claim page carries the **RETROSPECTIVE REPLAY** banner and the as-of views are reconstructions, not contemporaneous records.
- **Eligibility (criteria applied as written, not loosened)**: **NOT_ELIGIBLE_UNDER_V8_001_CRITERIA** — criterion 1 fails (not in the v7 evidence corpus), criterion 3 as
  written fails (the comparable actual is an ingested source, not a corpus filing), criterion 4 is retrospective; criteria 2, 5 and 6 hold. Nothing was
  added to the corpus, no crawler runs, no dataset product is claimed.
- **What the separate scorecard shows** (`scorecard_mchp.json`, 7/7, 18 positive + 9 negative assertions in Chromium 151.0.7922.34): accepted real-source
  behaviour of the workbench — passages registered by typing with UI digest == ingestion digest; typed claim frozen; revision with the preserved discrepancy
  (COMPARABLE, RAISED, low +25,000,000); actual 1,075,500,000 **OUT_OF_RANGE against both ranges** (distance outside +5,500,000), never presented as
  IN_RANGE; as-of 2025-05-01 / 05-20 / 06-15 replays under the retrospective label; a simulated adjudication (runner identity) and a refused undisputed
  contrary label; export built, downloaded, verified in a fresh workspace (SUCCESS; recomputed OUT_OF_RANGE; the press-release excerpt withheld by rights,
  digest kept) and a tampered copy refused. Publication eligibility: NOT ELIGIBLE.

## §2 — Boundary review: findings

Reviewed and unchanged: loopback bind; Host allow-list; POST requires same-origin `Origin` (null Origin → 403, nothing written; regression kept),
`Sec-Fetch-Site`, the HttpOnly SameSite=Strict session cookie and its HMAC token; bounded bodies; exports served only by a fixed id pattern; uploads
verified in memory within fixed archive bounds (traversal, symlinks, member count, compression ratio); inert rendering of passages and imported packets;
export recomputation (a forged comparison block fails recompute); the ingestion tool is never imported by the server and the server has no network client.

Defects demonstrated by new tests and fixed on this branch (each with the regression that first failed):

1. **Refused requests did not close the connection** — a 413/403/400 left the unread body on the socket, so pipelined bytes could be parsed as the next
   request. Now every refusal sends `Connection: close` and the handler stops; proved on a raw socket with a pipelined request that is never answered.
2. **A torn tail was reported but pages still served** — reads now surface the integrity page with the recovery form on every GET until `/recover`
   runs; writes were already refused. Proved over HTTP: torn → refused freeze → recovery (303) → integrity OK → freeze, browser resubmit lands once.
3. **Concurrent retries of one operation could race** between the unlocked prior-event read and the locked append (one thread saw "already frozen"
   instead of the idempotent duplicate). The whole read-decide-append sequence of every write now runs under one re-entrant lock (threads) around the file
   lock (processes). Proved with 16 threads behind a barrier, three rounds.

Also fixed while producing evidence: the claim page now shows when the workspace first observed each cited source (kept apart from the action time);
two expressions were rewritten for Python 3.10 (the minimum-Python gate caught them).

## §3 — Attribution

The V8-002 evidence's adjudications were automated Playwright actions; they are neither owner review nor independent review, whatever identity the
form carried. Corrected in `v8/V8-002/README.md` and `scorecard.json` (`c924cdee`); the 7/7 evidence for `a41dc39e` is unchanged and not relabelled.
The journey runner now records its reviewer identity as "journey-runner (automated test action; not a human review)" and writes an attribution line
into every log.

## §4 — Packaging: the workbench ships (development builds)

Built ONCE from a clean detached worktree at `9efdd52d88a3` with `SOURCE_DATE_EPOCH=1580601600` (hatchling 1.32.0), installed into fresh virtual
environments outside the checkout (non-editable, no PYTHONPATH), then the journeys ran from the INSTALLED package with Playwright pinned to the cached
Chromium and every export was verified through the installed command line.

| artifact | sha256 | bytes | members ok | long description | installed module inside venv | fixtures | real-source | verify-export |
|---|---|---|---|---|---|---|---|---|
| `yuclaw-7.0.1-py3-none-any.whl` | `76089ec48b392482ef5c954cadfd790620af6124cc71d53c1d755986e985fc0f` | 795,263 | True | True | True | 7/7 | 7/7 | 2 SUCCESS / 3 refused |
| `yuclaw-7.0.1.tar.gz` | `360ac54672125ea9b1104cdf0e52d3b6938287aab9c313b0c211e2ca231d9779` | 4,945,804 | True | True | True | 7/7 | 7/7 | 2 SUCCESS / 3 refused |

These are **development builds labelled 7.0.1** (the tree's version surfaces): evidence that the workbench ships from this commit, not release
candidates. `twine check --strict`: PASSED for both. Packaged resources (schema + fixtures) are byte-identical to the source tree. Two packaging defects
were found by the first run and fixed: the sdist builder picked up the order-record READMEs (now excluded) and the disposable environments received a
newer browser driver than the cached Chromium (now pinned). The final 8.0.0 artifacts are built once by the publisher from the frozen commit (plan below).

## §5 — Publisher and branding

- **`publish_v800.py`** (private, `internal/release_v8_0_0/`; identity `4466c4746206a1da…`) is derived from the 7.0.1 publisher by 61 counted replacements
  (`derive_publish_v800.py`; review surface `publish_v800.review.diff`, 393 lines). Preserved unchanged: the typed authorization sentence bound to
  sha + tree, policy-record hash and publisher identity; `precondition()` before every network write; one build / same bytes; typed remote observation with
  resume by name + hash + length; the `download-proof` record-then-acknowledge repair. Changed: 8.0.0 identities; **inverted tripwires for every published
  release (6.0.0, 6.0.1, 7.0.0, 7.0.1)** from their frozen artifact records; **Gate #15 route B closed** until the owner issues 8.0.0 wording (the 7.0.1
  exception is not inherited; binding the wording changes the publisher's identity); an **operation identifier on every journal line** (deterministic over
  release, step and content, so a retry is the same operation); the **v8 workbench browser journey against the installed artifact** added to verification.
- **Tests**: 20 passed (failure paths, transitions, resume by hash, partial uploads, closed route B, journal identifiers, tripwire rows for all four prior
  releases with a mutated prior turning its row RED; `download-proof` journal resume).
- **Rehearsal** (local and mocked destinations only): a disposable clone of candidate `9efdd52d88a3` plus a REHEARSAL-ONLY commit
  (`9509480ef4d0`) putting every gate-checked surface at 8.0.0 (98 pages, 98 badges; README transcript regenerated from a throwaway
  8.0.0 wheel), then the REAL build — `yuclaw-8.0.0-py3-none-any.whl` `ad07972ece8dac51…` (795,262 B), `yuclaw-8.0.0.tar.gz`
  `0e0fa3fe2b787dbc…` (4,945,800 B) — G2 over the built artifacts, 16 verification checks (install, version, abuse matrix,
  check-claim smoke, D3 matrix, exact transcript, v7 journeys, **v8 workbench 7/7 from the wheel and 7/7 from the sdist**), then tag, push-main,
  restore-main, push-tag, upload-pypi with an interruption and resume, gh-release, the evidence overlay (exactly 3 allowlisted paths) and the site
  stage against in-memory PyPI/GitHub/Pages. The rehearsal artifacts are not retained and bind to the rehearsal commit only.
- **PyPI long description**: `README_PYPI.md` is generated from `README.md` with only the approved-logo picture block removed (canonical MISSION-VISION,
  LOOKAHEAD and REPLICATION-SENTENCE blocks byte-identical); `pyproject.toml` points the package readme at it; it renders with readme_renderer without
  a picture element or relative brand path; `twine check` passes on the built artifacts. The approved logo bytes and the GitHub README are unchanged;
  nothing was published early.

## §6 — Release gates (actual output on `9efdd52d88a3`)

Generator: `tools/yuclaw_release_state_v6.py --evidence <V8-003 record>/gates/evidence_v8_candidate.json` in the worktree, no `--release-policy`
(none exists for 8.0.0). The generator names the run after the pyproject version (7.0.1).

| # | requirement | result |
|---|---|---|
| 1 | P0 registrations valid | **GREEN** |
| 2 | chain verifies | **GREEN** |
| 3 | zero unexplained ledger breaks | **GREEN** |
| 4 | point-in-time guard | **GREEN** |
| 5 | no v1 historical silent rewrite | **GREEN** |
| 6 | dependency calculations reproducible | **GREEN** |
| 7 | truncation ledger reconciles | **GREEN** |
| 8 | hypothesis/discovery lineage reconciles | **GREEN** |
| 9 | sequential methods pass registered fixtures | **GREEN** |
| 10 | research-state derivation reproducible | **GREEN** |
| 11 | machine JSON agrees with human page | **GREEN** |
| 12 | source citations resolve | **GREEN** |
| 13 | negative/inconclusive findings preserved | **GREEN** |
| 14 | language rails pass | **RED** |
| 15 | user comprehension test passes | **MANUAL_REVIEW** |
| 16 | stranger-machine reproduction passes | **GREEN** |
| 17 | G1 copy-consistency (canonical blocks byte-identical) | **GREEN** |
| 18 | G2 version (package = badge = capabilities = index = llms = README = PyPI metadata) | **GREEN** |
| 19 | G3 base URL (capabilities = index = llms = release_manifest.public_base_url) | **GREEN** |
| 20 | G4 endpoints (declared set = generated set; static 200/type/schema; wildcards by discovery) | **GREEN** |

Tripwire (pre-publish): **RED** — PyPI, GitHub latest release, live badge and origin/main are all at 7.0.1, which equals the
candidate's pyproject version; that is the version-surfaces blocker, not a remote change.

Blockers and carried facts:

1. **Gate 14 RED = weekly-note reconciliation only** (rc 1; the branch carries the 7.0.1 render of the note while the live store moved on). Language
   rail, leak sweep, no-forms and header layout all passed on this tree. Resolves with the production render at the freeze.
2. **Version surfaces at 7.0.1** (tripwire pre RED): bump to 8.0.0 on every gate-checked surface is a freeze-day step in production (plan below).
3. **Gate 6 GREEN on carried hashes**: the frozen inputs (digest `5a7a5058…`) and the replay tool are unchanged since the base, so the 7.0.1 candidate's
   replay hashes were reused. A fresh NO-WRITE replay was attempted three times (DB blocked) and **refused by the tool's own guard: calendar file hash
   mismatch** — `v3/u350/market_calendar.py` changed on 2026-09-14 (`49495fd1`) after the first-read manifest froze its identity, so no tree since then
   (including the published 7.0.1) can replay fresh. Owner-level protocol matter before a fresh gate-6 measurement.
4. **Gate 5 restage facts carried** from the 7.0.1 candidate evidence (the v8 branch changed no preview, registry, output or chain producer; the generator
   itself confirms chain file, evidence_geometry and the Phase-6 artifact identical to the base). Re-measure at the frozen candidate.
5. **Gate 15 MANUAL_REVIEW — NOT SATISFIED**; no 8.0.0 exception issued; the 7.0.1 exception is not inherited. **Human benefit PENDING.**
6. **Release policy NOT RECORDED** (D1 allocation, D2 Gate #15 route); the public notes are a draft.

## Checks run (this order)

| Check | Result |
|---|---|
| `pytest tests` on the candidate tree | 242 passed |
| `pyflakes` v8/workbench, new tools and tests | clean |
| `tools/check_leak_sweep.py` (tracked + staged) | OK; 93 pre-existing box-identifier warnings, unchanged |
| `tools/check_copy_consistency.py` · `check_no_forms.py` · `check_dual_copy.py` · `check_schemas.py` · `check_header_layout.py` · `check_py_minimum.py` | OK |
| `tools/check_release_manifest.py --dist <development dist>` (G2/G3/G4 local) | OK at 7.0.1 (12 surfaces + 98 badge pages; wheel and sdist metadata) |
| `tools/cli_transcript.py --check` · `tools/yuclaw_readme_pypi.py --check` (with a Markdown renderer) | OK |
| Language rail (pages mode) on README_PYPI.md, V8-002 README, this README and the notes draft | OK |
| CJK scan on every new or changed file | none |
| Browser journeys on the checkout (Chromium 151.0.7922.34) | fixtures 7/7 (22+18 assertions); real-source 7/7 |
| Clean install (wheel, sdist) | PASS — see §4 |
| Publisher suites · rehearsal | 20 passed · 1 passed (real build, 16 checks, fakes) |
| Release-state generator | 18 GREEN / 1 RED / 1 MANUAL_REVIEW; tripwire(pre) RED — see §6 |

Not run: live network gates (`--live`/`--pypi` on the release manifest; deploy-verify), the production render, any push.

## Candidate-freeze plan (2026-09-20, Asia/Shanghai) — consistent 8.0.0 versioning and final-byte verification

1. Owner decisions recorded first: the 8.0.0 allocation document (D1) and the Gate #15 route (D2 — route A needs a GREEN gate input; route B needs the
   owner's own 8.0.0 wording, which is then bound verbatim into `publish_v800.py`, changing its identity). The 7.0.1 exception is not inherited.
2. In the production checkout, the version bump on every gate-checked surface, exactly as rehearsed: `pyproject.toml`, `release_manifest.json`,
   `docs/capabilities.json`, `docs/evidence_index.json`, `docs/llms.txt`, `CITATION.cff` (version + date), `README.md` (current version, release link,
   candidate-checkout sentence, transcript block regenerated from the release-candidate wheel), `CHANGELOG.md` (the reviewed notes), every page rendered
   at badge v8.0.0 by the site refresh chain (98 shared-header pages; this also refreshes the weekly note and today's evidence block — never render those
   in a worktree), `README_PYPI.md` regenerated. Then `check_release_manifest.py --only g2`, `check_header_layout.py`, `cli_transcript.py --check`,
   `yuclaw_readme_pypi.py --check` GREEN.
3. Re-measure at the frozen tree: the gate-6 replay (after the calendar-identity decision), the gate-11 restage trees, the read-only tripwire
   observations; regenerate the release-state manifest and the two-tier notes with `--release-policy`; gate table with zero RED and Gate 15 on its
   recorded route.
4. Freeze the commit. Re-run both browser journeys (fixtures and the Microchip retrospective replay) on the frozen commit from the checkout, and the
   clean-install tool on the frozen commit (its build reproduces the publisher's bytes: same `SOURCE_DATE_EPOCH`, same commit).
5. Owner's authorization sentence naming the frozen sha and tree. Publisher: `dryrun` → `policy` → `authorize` → `worktree` → `build` (ONCE; freezes
   wheel/sdist sha256 + length; 16 verification checks including the v8 workbench journey from both installed artifacts). **Final-byte verification**: the
   publisher's frozen digests must equal the clean-install tool's digests for the same commit; any difference stops the release before the first public
   write. Journeys for Gate B (2026-09-19 evening) bind to that frozen commit only; the a41dc39e and 9efdd52d88a3 evidence is not relabelled.
6. Release day (2026-09-21, subject to the concrete decision): tag → push-main → restore-main → push-tag → upload-pypi → gh-release → evidence → site →
   `download-proof` → `tripwire` (all four prior releases must stay untouched). Nothing in this order performs any of these.

## Start the workbench and reproduce the evidence

```
python3 -m v8.workbench serve --workspace <dir>/research --port 8765        # loopback only; a second workspace on 8766 for verification
python3 -m v8.workbench.ingest --url <allow-listed https URL> --kind filing --form "8-K EX-99.1" --accession <acc> --cik <cik> --pattern '<regex>' --rights SEC_PUBLIC_FILING --out <dir> --label original
<playwright venv>/bin/python -m v8.workbench.journey --out <dir>                                   # fixtures, exit 0 only at 7/7
<playwright venv>/bin/python -m v8.workbench.journey --mode mchp --sources <ingestion records> --out <dir>
python3 tools/yuclaw_v8_clean_install.py --commit <sha> --out <dir> --sources <ingestion records> --playwright-spec "playwright==1.62.0"
```
The ingestion records (`sources/`) carry digests, availability and observation times; the original bytes and the press-release passage text stay in the
private record. Evidence inventory: `evidence_index.json`. Optional modules COM/PRC/SHD/EVO stay absent; backups stay canceled; product content is
English only; the approved logo bytes and the README canonical blocks are unchanged.

Research and education only. Not investment advice.
