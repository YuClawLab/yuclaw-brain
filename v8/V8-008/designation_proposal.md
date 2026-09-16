# Candidate-designation proposal for 8.0.0 — revised on the corrected integration state (V8-008; nothing applied)

Research and education only. Not investment advice. This is a proposal for the owner's designation order. It is not a freeze and not a publication authorization; `release_authorized` stays false through designation and freeze. The staging-only weekly-note render commits (`30a5cf4e` in V8-007, `25783e87` in V8-008) are historical staging evidence, never candidates.

## The corrected source state and the exact change it would apply

| Item | Identity |
|---|---|
| Corrected integration state (branch HEAD before this record) | `10d480cdd097ea3a1c508459a9bdc40b9aaf820c` (tree `13d91550…`) = implementation `d70edd02` + V8-005/V8-006/V8-007 records + V8-006 release-tool corrections + the V8-008 TB-1 repair (release tooling only: `tools/yuclaw_release_notes_v8.py`, the generator's version dispatch, `tests/test_release_notes_v8.py`) |
| The exact change designation applies | the version-surface patch: 108 files, stable patch-id `27267a974a724a04805516ca3d9a401b709ae745` (identical to the V8-006 and V8-007 patches); full patch in the private record `candidate_8.0.0_version_surfaces.patch`; produced by `v8/V8-008/candidate_bump_8.0.0.py` with **explicit path staging** (allow-list; refuses anything else; no symlinks) |
| Staged result (private, not on the branch) | commit `3d43089ea31e886a7bcb6033da929477d6b79782`, tree `c5bd485b39ae4e8493ea14bb225101d308c54427`; clean working tree; `output/output` absent |
| Preliminary pair rebuilt from it | wheel `aa988727055aa81f…` (849,964 B), sdist `bc974991c5e12433…` (4,992,067 B): byte-identical to the V8-007 pair, so the V8-007 member accounting and the V8-006 rehearsal re-run's installed demonstration of these wheel bytes apply unchanged (explicit applicability: the repair touches no packaged path); twine 7 strict PASSED |
| Packaged code vs the reviewed implementation | none changed (`d70edd02`) |

Three approvals stay distinct and none implies another: (1) **designation** — the owner orders this patch applied to `codex/v8-integration` (local); (2) **allocation and policy** — D1-ACCEPT + a Gate #15 route, recorded together by the publisher's policy stage; (3) **publication authorization** — the owner's sentence `I, the owner, authorize the 8.0.0 release from source <sha> (tree <tree>). Date 2026-MM-DD.` for the FROZEN commit, the only act that sets `release_authorized=true`.

## Step 1 — designation (owner order; local)
```
cd <branch checkout>                                              # codex/v8-integration, clean, at 10d480cd or a later record-only commit
git cherry-pick 3d43089ea31e886a7bcb6033da929477d6b79782          # or: git apply --index <full patch> && git commit
git diff HEAD~1 HEAD | git patch-id --stable                      # must print 27267a974a724a04805516ca3d9a401b709ae745
git diff HEAD~1 HEAD --summary | grep -c 'mode 120000'            # must print 0 (no symlink)
python3 tools/check_release_manifest.py --only g2                 # version 8.0.0 on 9 surfaces + 98 badge pages
python3 tools/check_header_layout.py                              # badge v8.0.0 == package version
python3 tools/yuclaw_v8_clean_install.py --commit HEAD --out <private dir> --twine internal/release_v6/twine-venv/bin/twine --playwright-spec "playwright==1.62.0"
```
Identity check: the patch-id must be `27267a97…` and the preliminary build from the designated commit must reproduce wheel `aa988727…` and sdist `bc974991…` exactly. If either differs, stop: the designated state is not the reviewed state.

## Step 2 — freeze-day renders and freeze (owner order; the checkout that is frozen; 7.0.1 pattern)
- Render the weekly note with the real generator and reconcile it (`tools/yuclaw_weekly_note.py`, then `tools/check_weekly_note.py --require-contract v3`); render any other page the 7.0.1 pattern renders at the badge; commit with explicit paths. Neither staging render commit is carried over.
- Record D1 + D2 (`publish_v800.py policy …`), then regenerate the release-state manifest at the frozen commit with `--release-policy`: the 8.0.0 composer composes the policy-bound notes and reports correspondence; `notes.policy_correspondence == []` only when the record is accepted and complete.
- Expected artifact effect: the wheel stays `aa988727…`; the sdist changes because `docs/` (including the weekly note) ships in it. The preliminary pair is therefore NOT adoptable for the frozen commit (the publisher's `adopt` binds commit and tree); the clean-install tool builds the frozen commit's pair and writes its identity record.

## Step 3 — authorization and the one final set (owner sentence; nothing here)
```
publish_v800.py authorize <sentence file>            # 0 RED, valid policy, corresponding notes, clean worktree at the frozen sha/tree
publish_v800.py adopt <clean-install dist dir>       # or: build — one final set; identity bound to the authorized sha/tree; bytes verified
publish_v800.py verify-retry / status
```
No network stage is part of this order; each is refused while `release_authorized` is false.

## What designation preserves unchanged
Gate-6 correction and fresh historical-calendar replay (no repeat), the unapplied A1.2 proposal (`v8/V8-007/A1_2_calendar_note_PROPOSED.md`), the adoption path validated on the V8-005 pair, the tripwire observations, the V8-003 and V8-006 rehearsal records under their own identities, the 7.0.1-labelled development demonstrations, the approved logo bytes, the canonical mission/vision blocks, backup cancellation and existing data.
