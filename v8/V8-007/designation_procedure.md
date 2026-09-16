# Candidate-designation procedure for 8.0.0 (V8-007; nothing applied)

Research and education only. Not investment advice. Nothing in this file runs by itself; every step below is an owner order or a step the owner's order triggers. `release_authorized` stays false throughout designation and freeze; only the authorization sentence changes it.

## The coherent state being proposed

| Item | Identity |
|---|---|
| Base (branch HEAD when V8-007 started) | `ab2c5c88d8169c0456080fe36ddac47a3ab8f2be` (tree `1d1273f9…`) = implementation `d70edd02` + V8-005 record + V8-006 record and release-tool corrections |
| Version-surface patch | 108 files, stable patch-id `27267a974a724a04805516ca3d9a401b709ae745`; full patch `internal/v8/v8_007_20260916T062115Z/candidate_8.0.0_version_surfaces.patch` (sha256 `7a008d387b309c28…`); tracked excerpt `v8/V8-006/candidate_8.0.0_version_surfaces.excerpt.diff`; produced by `v8/V8-006/candidate_bump_8.0.0.py` (staging-only guard) |
| Staged result (private, not on the branch) | commit `479a5aef6feb8150802b78653b042cd58d140da5`, tree `027c43ead25342366c9d8f59384c6d116f392994` |
| Preliminary pair built from it | wheel `aa988727055aa81f…` (849,964 B), sdist `bc974991c5e12433…` (4,992,067 B); twine 7 strict PASSED; identical to the V8-006 staged pair; wheel identical to the V8-006 rehearsal re-run wheel |
| Packaged code vs the reviewed implementation | none changed (255/255 non-metadata wheel members identical to the V8-005 development wheel) |

Three approvals are distinct and none implies another:
1. **Local candidate approval (designation)** — the owner orders the version patch applied to `codex/v8-integration`. Local branch state only; nothing external.
2. **Allocation and policy selection (D1 + D2)** — the owner edits `D1_allocation_8.0.0_PROPOSED.json` to `D1-ACCEPT` and chooses a Gate #15 route; both are recorded in one policy record by the publisher's `policy` stage (route B needs the owner's wording bound first).
3. **Publication authorization** — the owner's sentence `I, the owner, authorize the 8.0.0 release from source <sha> (tree <tree>). Date 2026-MM-DD.` for the FROZEN commit; accepted by `publish_v800.py authorize` only with 0 RED, a valid policy, corresponding notes and a clean worktree at that sha/tree. This is the only act that sets `release_authorized=true`.

## Step 1 — designation (owner order; local)
```
cd <branch checkout>                                # codex/v8-integration, clean
git cherry-pick 479a5aef6feb8150802b78653b042cd58d140da5      # or: git apply --index <full patch> && git commit
git diff HEAD~1 HEAD | git patch-id --stable         # must print 27267a974a724a04805516ca3d9a401b709ae745
python3 tools/check_release_manifest.py --only g2    # version 8.0.0 on 9 surfaces + 98 badge pages
python3 tools/check_header_layout.py                 # badge v8.0.0 == package version
python3 tools/yuclaw_v8_clean_install.py --commit HEAD --out <private dir> --twine internal/release_v6/twine-venv/bin/twine --playwright-spec "playwright==1.62.0"
```
Identity check of the designated state: the patch-id must equal `27267a97…`, and the preliminary build from the designated commit must reproduce wheel `aa988727…` and sdist `bc974991…` exactly (the tree differs from `027c43ea…` only by the V8-007 record, which both artifacts exclude). If either differs, stop: the designated state is not the reviewed state.

## Step 2 — freeze-day renders and freeze (owner order; production checkout, 7.0.1 pattern)
- Render the weekly note with the real generator in the checkout that is frozen (`tools/yuclaw_weekly_note.py`), then `tools/check_weekly_note.py --require-contract v3`; render any other freeze-day page the 7.0.1 pattern renders at the badge; commit. The staging render `30a5cf4e` is NOT carried over.
- Record D1 + D2 (`publish_v800.py policy …`), then regenerate the release-state manifest at the frozen commit with `--release-policy` (needs TB-1, the 8.x notes composition path, resolved first; see `gates.json`).
- Expected artifact effect: the wheel stays `aa988727…`; the sdist changes because `docs/` (including `docs/weekly_note.html`) ships in it. The preliminary pair is therefore NOT adoptable for the frozen commit (the publisher's `adopt` binds commit and tree); the clean-install tool builds the frozen commit's pair and writes its identity record.

## Step 3 — authorization and the one final set (owner sentence)
```
publish_v800.py authorize <sentence file>            # binds the frozen sha/tree, the policy record hash and the publisher identity
publish_v800.py adopt <clean-install dist dir>       # or: build — one final set; identity record must name the authorized sha/tree; bytes verified
publish_v800.py verify-retry / status                # verification completion record before any network stage
```
No network stage (`tag`, `push-main`, `push-tag`, `upload-pypi`, `gh-release`, `site`) is part of this order; each has its own precondition check and is refused while `release_authorized` is false.

## What is preserved unchanged by designation
Gate-6 correction and its fresh bound replay (no repeat), the unapplied A1.2 proposal, the tripwire observations, the mocked rehearsals (V8-003 historical; V8-006 re-run), the adoption path validated on the V8-005 pair, the 7.0.1-labelled development demonstrations bound to their original artifacts, the approved logo bytes, the canonical mission/vision blocks, backup cancellation and existing data.
