# V8-011 — source-correction and integration gaps closed; corrected 8.0.0 candidate (handoff)

Research and education only. Not investment advice. **Nothing was pushed, tagged, uploaded, deployed or announced.
`release_authorized=false`. D1 is PROPOSED. Gate 15 is REMOVED_BY_OWNER (never PASSED). Human benefit is PENDING.**

## Identity

| | |
|---|---|
| Branch | `codex/v8-integration` (local only; origin has no such branch) |
| Candidate SOURCE commit / tree | `9d1de81ef91d033f9d828e7e4b40753a1f39acd7` / `ba82955d0c3eee9bcd72c4164cfd36b2cf93b0fb` |
| Record HEAD | see `git rev-parse HEAD` — evidence-only commits on top; 0 files outside `v8/V8-011/` differ from the source |
| Wheel | `yuclaw-8.0.0-py3-none-any.whl` sha256 `7c2dd63d5094539c487d2e7fc53edebe36154c79c0d89cacd736f933b3afdc94`, 884,968 B |
| Sdist | `yuclaw-8.0.0.tar.gz` sha256 `9c4fc99ff734aac67b0024fc9792f52f75136db4c16b3c509ae7cc87fbac6d1e`, 5,151,389 B |
| Built | 2026-09-19T11:10:51Z, SOURCE_DATE_EPOCH 1580601600, Python 3.12.3, build 1.4.2, hatchling 1.32.3 — a CANDIDATE pair, not a final set |
| Upstream | `origin/main` `5edb9e7e8502a11727b6174b8cc62f47107a6a91`, observed 2026-09-19T10:31:47Z, unchanged at 11:07:39Z; an ancestor of the candidate |
| V8-010 pair | `319ce0b5…` / `3290240c…` preserved as historical candidate evidence (source `93274e7d`); not a target, not relabelled |

## The three named technical items — all completed

1. **Upstream integrated locally** (`ca96f574`, a merge; history kept). Five commits were missing, not four. Three textual
   conflicts reconciled by intent; the result verified mechanically (187 upstream-only paths byte-equal to upstream, 100
   both-sides paths differing by exactly the 7.0.1→8.0.0 line, 212 v8-only paths untouched). → `upstream_integration.json`
2. **TIM-08** — a wrong availability time is corrected by a linked append-only event, never by editing. The existing
   CORRECTED_SOURCE amendment was inspected first and cannot express it. → `availability_correction.json`
3. **SEC request identity** is the operator's own required setting; the maintainer default is gone. → `sec_request_identity.json`

## What the regressions found (and what I got wrong)

- **Stale previews after the merge.** The restage invariant failed: 345 files under `docs/preview/`. `origin/main` shows the
  same 345 — the nightly refresh never regenerates previews. Regenerated deterministically (`9d1de81e`); re-measured 0.
- **I built too early.** The first pair (source `54977612`) was built before that measurement and is superseded. Its tool
  result was also FAIL because I invoked twine 6.2.0 (cannot parse Metadata 2.5); the pair passes under twine 7.0.0. The
  order of work is now: measure → gate pass → one build. Disclosed in `packaging.json`.
- Three times an assertion of mine expected the wrong refusal message (journey forgery, publisher stop) or mis-measured
  (UI inspector: stylesheet race, URL fragment). In each the product was right; each was verified by direct experiment.

## Verification on the candidate

- Installed from the **wheel** and from the **sdist**, fresh venvs outside the checkout, no editable install, no PYTHONPATH:
  fixtures 7/7 (99/99 assertions, 45 negative) with research notes, dataset, scientific replay, usability **and
  availability correction** DEMONSTRATED; Microchip 7/7 (35/35), retrospective, NOT ELIGIBLE, semantics unchanged.
- Installed CLI: the corrected export verifies (rc 0); the forged counterpart is refused (rc 1); 12/12 packets as expected.
- Full suite 306 passed · focused correction tests 8 · twine 7.0.0 PASSED ×2 · Python 3.10.21 floor incl. the correction path ·
  rollback rehearsal against the published 7.0.1 wheel · UI inspection 21 pages / 0 findings (**automated only** — not a
  human or screen-reader review) · policy/order records absent from both distributions; guides and resources present ·
  logo blobs and both canonical sentences unchanged · English only.
- Gates at the record HEAD: **19 GREEN / 0 RED / 1 REMOVED_BY_OWNER**, tripwire GREEN, `policy_correspondence =
  ['no release-policy record']`. → `gates.json` (and what a green table does not erase)
- Focused publisher rehearsal (local fakes only): new pair adopted and bound; upstream moving after authorization is a
  clear STOP, nothing forced. → `publisher_rehearsal.json`

## Remote CI — NOT RUN

As configured, **no workflow runs on a branch-only push or on a pull request from this branch** (0 files under the path
filters). `compliance-regression` runs only on a push to `main`; a push to `main` also deploys the site (Pages serves
`main:/docs`). Local equivalents passed and are not remote CI. The branch-only push plan is PROPOSED, not executed.
→ `ci_inspection_and_push_plan.json`

## Exact remaining actions

1. **Owner:** decide D1 — `D1_allocation_8.0.0_PROPOSED.json` (`V8-ALLOC-2026-09-19-P4`, PROPOSED).
2. **Owner:** decide remote CI — accept the local equivalents, or order a pre-release workflow (not added here); approve or
   decline the branch-only push.
3. **Before the freeze:** `python3 v8/V8-011/check_upstream_ancestry.py`. The nightly refresh (~23:00 UTC) **will** move
   `main`. On STOP: merge, render the weekly note, regenerate `docs/preview`, commit, build and verify a NEW pair, and point
   D1 at it. Freezing inside one nightly window, or pausing the refresh for the window, is the owner's call.
4. **Freeze:** generator re-run at the frozen commit with `--release-policy`; notes must correspond.
5. **Publication:** only on the owner's verbatim authorization sentence binding the frozen commit and tree.
6. Optional: one line each in the notes composer for the correction and the SEC setting (the GitHub Release body omits them
   today; the CHANGELOG and guides state them). Whether the v3 pollers' identity defaults should change is separate.

## Functional walkthrough — startup path (the candidate wheel, already installed and smoke-tested)

    W=~/yuclaw/internal/v8/v8_011_20260919T110207Z/walkthrough
    $W/venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-011-research --port 8765     # terminal 1
    $W/venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-011-fresh    --port 8766     # terminal 2

Open <http://127.0.0.1:8765/> → **Load a fictional fixture** `003_withdrawal` → **1 Source → Correct a source's availability
time**: choose the withdrawal source (`0000000000-26-000004…`, available 2026-08-04T20:58:00Z), corrected time `2027-03-01T00:00:00Z`, a reason,
an evidence reference, your name → open the claim: recorded result beside the corrected view, *Needs review* → add
`?as_of=2026-09-01T00:00:00Z` to the claim URL: the correction is only *listed as later* → **7 Reproducible export** → upload
the zip at <http://127.0.0.1:8766/verify>. Help is at `/help`. Stop with Ctrl-C.

| Step | Observation (left blank until a person performs it) |
|---|---|
| Start both servers; Help page readable | |
| Load fixture; seven steps make sense | |
| Record an availability correction; refusal messages understandable | |
| Claim page: recorded vs corrected view is clear | |
| As-of view: "later correction" wording is clear | |
| Export verifies in the fresh workspace | |
| Anything confusing, missing or wrong | |
