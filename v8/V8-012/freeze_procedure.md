# V8-012 — one coordinated freeze procedure for 8.0.0 (PREPARED, not executed)

Research and education only. Not investment advice. Nothing here was run against a remote. `release_authorized=false`.
Each step names the actual command and path. `F` is the **one** frozen source commit (full sha + tree).

## The rule that keeps this from becoming circular

`F` is the branch tip at the freeze, the commit that is pushed to the branch, the commit the hosted run reports, the
commit the pair's identity record names, the commit the release-state manifest names and the commit in the owner's
authorization sentence — the same full sha every time. **After `F` exists nothing is committed on the branch until the
release is complete.** Everything produced after `F` is private and untracked by design, so it cannot change `F`:

| Produced after `F` | Where it lives (gitignored / outside the tree) |
|---|---|
| hosted CI result | the GitHub Actions run whose `headSha` equals `F` |
| verified pair + `artifact_identity.json` | `~/yuclaw/internal/v8/<freeze record>/clean_install/dist/` |
| accepted allocation document (D1) | `~/yuclaw/internal/release_v8_0_0/` (a private copy of the PROPOSED document, edited by the owner) |
| policy record | `~/yuclaw/internal/release_v8_0_0/release_policy_v8.0.0.json` (publisher `policy` stage) |
| policy-bound notes + manifest | `~/yuclaw/internal/release_notes_v8.0.0_PUBLIC.md`, `release_state_manifest_v8.0.0.json` |
| authorization | recorded into that manifest by the publisher `authorize` stage |

A tracked order record (a `v8/V8-*` directory) is committed **before** `F` or **after** the release, never between.
A pair whose identity record names another commit is never adopted, even when its bytes are identical: the publisher's
`adopt` stage and `tools/yuclaw_v8_clean_install.py --artifacts` both stop on a commit or tree mismatch.

## The window (actual schedule, read from the production crontab and the publisher)

- The refresh that pushes `main` is `0 17 * * 1-5` in America/Edmonton = **23:00 UTC Mon–Fri** = 07:00 Asia/Shanghai
  Tue–Sat; its commits land 23:01–23:05 UTC. It does not run on Saturday or Sunday (last 40 refresh commits: none on a
  weekend). Observed once in this order: `origin/main` = `5edb9e7e8502a11727b6174b8cc62f47107a6a91` at
  2026-09-20T02:30:59Z — unchanged since Friday's refresh, and an ancestor of the branch.
- The publisher itself refuses every public write, and every stage while the production checkout is detached, within
  60 minutes of that firing (`nightly_clearance`).
- The weekly-note check recounts the evidence store for the note's own window; new filings change the store on US
  business days from about 10:00 UTC (EDGAR opens 06:00 US Eastern).
- **Recommended window: Monday 2026-09-21, 08:30–17:00 Asia/Shanghai (00:30–09:00 UTC)** — before EDGAR opens, about
  14 hours before the next refresh, on the CHANGELOG's release date. Sunday 2026-09-20 is equally quiet if the owner
  prefers it (the CHANGELOG date would then need the owner's decision). The next weekday alternative is any day
  08:30–17:00 Asia/Shanghai: it starts 1.5 h after that morning's refresh and needs step 2 first.
- **No pause of the production refresh is needed or proposed.** If the owner ever wants one anyway, it is a separate
  approval: comment out the single `0 17 * * 1-5 … refresh_v3_pages.sh` crontab line for that one firing and restore the
  identical line afterwards (`crontab -l` before and after must be byte-identical). Not done, not recommended.

## Steps

**1 — Recheck upstream** (repeat immediately before step 7 and again before step 10; read-only fetch):

    cd ~/yuclaw-v8 && python3 v8/V8-011/check_upstream_ancestry.py --observed 5edb9e7e8502a11727b6174b8cc62f47107a6a91

Exit 0 → skip step 2. Exit 3 → step 2. Never force anything.

**2 — Integrate a moved upstream without rewriting history** (only on exit 3):

    git merge --no-ff --signoff origin/main     # a merge commit with the DCO sign-off; no rebase, no reset

Conflict rules are recorded in `v8/V8-011/upstream_integration.json` (upstream's generation stamps, the branch's 8.0.0
version lines). A merge of `main` always leaves `docs/preview` stale (the refresh never regenerates it) → step 3 in full.

**3 — Weekly note and previews** (identified inputs: `docs/evidence_changes/*.json`, `registry/protocols.jsonl`, the
evidence store read-only; renderer `tools/yuclaw_weekly_note.py`, checker `tools/check_weekly_note.py`):

    python3 tools/check_weekly_note.py --require-contract v3      # rc 0 and no merge in step 2 → nothing to render
    python3 tools/yuclaw_weekly_note.py && python3 tools/check_weekly_note.py --require-contract v3     # otherwise
    python3 -c "import tools.yuclaw_science_trust_cards as c; print(c.write_all())"                     # after a merge
    git status --short        # expect docs/weekly_note.html and, after a merge, docs/preview/** only

Observed in this order: the 2026-09-19 render still reconciles on 2026-09-20 (rc 0, 300 events for 2026-09-13..09-19);
what breaks it is a store change inside the note's window, not the date. Rendering changes a packaged file (the sdist
ships `docs/`), so it always means a new `F` and a new pair.

**4 — Commit the intended source → `F`.** Any tracked record goes in first; then:

    git add -A docs && git commit -s -m "docs: weekly note [and previews] reconciled for the 8.0.0 freeze"      # only if step 3 changed files
    F=$(git rev-parse HEAD); T=$(git rev-parse 'HEAD^{tree}'); git status --porcelain | wc -l                # must print 0

If steps 2–3 changed nothing, `F` is the branch tip already pushed and already run by hosted CI.

**5 — Evidence bound to `F`** (each needs the owner's approval where it writes to a remote):

    git push origin $F:refs/heads/codex/v8-integration                                 # OWNER-APPROVED branch push; non-force; public
    ~/bin/gh run list -R YuClawLab/yuclaw-brain --workflow v8-prerelease-validation --branch codex/v8-integration \
             --json headSha,conclusion,databaseId,event,url --jq ".[] | select(.headSha==\"$F\")"
    python3 tools/yuclaw_v8_clean_install.py --commit $F --out ~/yuclaw/internal/v8/<freeze record>/clean_install \
            --twine ~/yuclaw/internal/release_v6/twine-venv/bin/twine --playwright-spec "playwright==1.62.0" \
            [--sources <private ingestion records>]          # the ONE build; identity record names F and T; --sources adds the real-source replay
    python3 tools/yuclaw_release_state_v6.py --evidence <session-measured facts for F>  # gate pre-pass: 0 RED expected; no policy yet

Remote CI counts only as the hosted run whose `headSha` is `F` with conclusion `success`. Local tables never stand in.

**6 — Owner decisions, in this order, each naming `F`:**
   a. Functional walkthrough (README of this record) — observations are the owner's.
   b. D1: the owner copies `v8/V8-012/D1_allocation_8.0.0_PROPOSED.json` to
      `~/yuclaw/internal/release_v8_0_0/D1_allocation_8.0.0.json`, sets `candidate_this_allocation_refers_to` to `F`, `T`
      and the step-5 pair digests, and sets `decision` to `D1-ACCEPT` (or `D1-AMEND: <note>`). Private file; not committed.

**7 — Production checkout at `F`, policy, policy-bound notes and manifest** (step 1 again first; the publisher reads
`~/yuclaw`, so this is the first step that changes the production checkout — inside the window, ≥ 60 min from a refresh):

    cd ~/yuclaw && git status --porcelain --untracked-files=no -- . ':!output' ':!services'     # must be empty
    git checkout --detach $F
    python3 internal/release_v8_0_0/publish_v800.py policy internal/release_v8_0_0/D1_allocation_8.0.0.json
    python3 tools/yuclaw_release_state_v6.py --evidence <facts for F> --release-policy internal/release_v8_0_0/release_policy_v8.0.0.json
    python3 internal/release_v8_0_0/publish_v800.py dryrun      # reads the notes the generator just wrote; GREEN expected

Required result: 0 RED, gate 15 `REMOVED_BY_OWNER`, `policy_correspondence = []`. With D1 unaccepted this cannot pass:
the notes say "Release policy: NOT RECORDED" and the correspondence is `['no release-policy record']`.
Rollback of this step, if the freeze is abandoned: `git checkout main` in `~/yuclaw` (nothing was written to a remote).

**8 — Separate publication authorization for the actual frozen identity.** The owner writes the publisher's verbatim
sentence naming `F` and `T` into a file; `python3 internal/release_v8_0_0/publish_v800.py authorize <file>` refuses
unless the production HEAD, the manifest candidate, the policy record hash and this publisher file
(identity `5649f289306237eb3a222542af6fac4896240a355bb68a5736f4337cfb9ab829`) all agree. No agent writes that sentence.

**9 — Final pair:** `publish_v800.py worktree`, then **either** `adopt ~/yuclaw/internal/v8/<freeze record>/clean_install/dist`
(only the step-5 pair, whose identity names `F`/`T`; the V8-011 pair names `9d1de81e` and is refused) **or** `build`
(the publisher's single build). Both run the same install-and-journey verification before anything is frozen.

**10 — Publication** (step 1 once more; each stage observes the remote first and stops on UNKNOWN):
`tag` → `push-main` (first public write; stops if `origin/main` ≠ the manifest's base) → `restore-main` → `push-tag` →
`upload-pypi` → `gh-release` → `evidence` → `site` → `download-proof` → `tripwire`. If `push-main` stops because
upstream moved: nothing public was written; return to step 1 — a new `F`, new evidence, new D1 reference, new authorization.
