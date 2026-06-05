# v4.1 Branch Reconciliation Plan

> ## ⛔ DO NOT EXECUTE WITHOUT VINZHANG + GEMINI REVIEW
> This document is **investigation output only**. Per the three-AI rule, it must
> go to **Gemini for architectural review** and receive **VinZhang's explicit
> approval** before ANY git operation is performed. Nothing in the "Proposed
> sequence" sections has been run. No branch was merged, rebased, committed
> (except this plan in the v5 worktree), or pushed during the investigation that
> produced it.

**Authored:** 2026-06-04 · investigation session, read-only.
**Status:** DRAFT — awaiting review.

---

## 1. Divergence summary

| Worktree | Path | Branch | HEAD (at investigation) |
|---|---|---|---|
| main | `/home/zhangd2/yuclaw` | `main` | `c3241fc5` |
| v3 | `/home/zhangd2/yuclaw-v3` | `v3.0-evidence` | `5bd9931a` |
| v5 | `/home/zhangd2/yuclaw-v5` | `v5-layer0-foundation` | `225a1cf1` |

- **Merge-base:** `ef570aa5` (v3.0 methodology note) — the last common ancestor,
  which itself contains a `Merge branch 'v3.0-evidence'` (089be982). The branches
  have diverged *since* that point.
- **main ahead of v3.0-evidence:** **127 commits**
- **v3.0-evidence ahead of main:** **25 commits**

This is a true two-sided divergence, growing daily (main gains ~1 auto-publish
commit/day). The longer it sits, the larger the eventual conflict set.

## 2. Commit categorization (the 127 on main)

| Category | Count | Reconciliation value |
|---|---|---|
| `auto:` page-refresh / data snapshots | **112** | **Low** — machine-generated `docs/index.html` + `docs/data` + `output/` data. Should NOT be replayed commit-by-commit. |
| `feat(v4):` real code | 3 | **High** — broadcaster v4 format, grade-first ranking, landing rebrand. |
| `feat(extract):` | 1 | High — v2 prompt + R7 fallback. |
| `docs(main):` | 1 | Medium — transparency notice. |
| other (incl. v3.0 launch/docs, the base merge) | 10 | Mixed. |

The **15 non-auto commits** are the real payload on main. The 112 auto commits
are noise that must be collapsed, not merged.

The **25 on v3.0-evidence** are almost entirely the **v4 product build**:
Day 1–10 feature work (Agent Research API unified schema, REST endpoints, MCP v2
+ LangChain/LlamaIndex wrappers, Memo Generator, Cascade History View, API-key
auth + metering, `yuclaw demo`, Share-this-Signal), the **v2.3→`archive/v2/`
archival**, EDGAR per-CIK poller, and the v4.0.1 zero-backend demo + release notes.

**Interpretation:** the two branches have split into two *roles*:
- **`v3.0-evidence` = product source-of-truth** (the v4.0.1 codebase + the
  archival reorg) — but it has **no live-serving/publishing infrastructure**.
- **`main` = the live-serving & publishing branch** (auto-publish page refresh,
  the *newer* v4-format Telegram broadcaster, `v3/web/render_landing.py`) — but
  it **lacks the post-base v4 product evolution** and **never did the archival
  reorg** (keeps the old `yuclaw/` tree live).

## 3. Dirty main working-tree inventory

`/home/zhangd2/yuclaw` has **145 uncommitted entries** — **all under `output/`**:
- 5 tracked-modified (`output/daemon/*.json`, `output/swarm/*.json`, `output/track_record_latest.json`)
- 140 untracked (`output/oil/*`, `output/sentiment/*`, `output/swarm/*`, `output/track_record/*`)

**✅ ZERO uncommitted SOURCE files.** Every change is cron-generated data
artifact. There is no dangerous in-flight source edit. (The pre-existing
`drafts/v4.0.0_telegram_launch.txt` modification noted in prior sessions is in
the **v3 worktree**, not main, and is unrelated to this.)

## 4. The real conflict surface

The June-2 "120 conflicts" = ~6 content + ~114 file-location. The 114 are
mechanical (the archival move). The decisions that actually matter:

| File | On `main` (LIVE) | On `v3.0-evidence` | Live cron dependency |
|---|---|---|---|
| `broadcast_bot.py` | `yuclaw/telegram/broadcast_bot.py` — **v4-format, newer** | `archive/v2/yuclaw/telegram/broadcast_bot.py` — **old, archived** | **YES** — cron L32 runs `python3 -m yuclaw.telegram.broadcast_bot` from main |
| `render_landing.py` | `v3/web/render_landing.py` | **absent entirely** | **YES** — cron L31 runs `python3 -m v3.web.render_landing` from main |
| `rebuild_html.py` | `rebuild_html.py` (root) | `archive/v2/rebuild_html.py` — archived | Indirect (legacy dashboard renderer) |

- **Content divergence on the broadcaster is real:** `main`'s live copy differs
  from `v3`'s archived copy by **201 lines (+72/−129)** — main's is the v4-format
  rewrite. v3.0-evidence has **no live broadcaster at all**.
- **`render_landing.py` exists only on main.** v3.0-evidence cannot render its
  own landing page.

**Crux:** the archival reorg on v3.0-evidence moved *exactly the files main's
live crons depend on*. If v3.0-evidence's tree shape were checked out into the
main worktree as-is, **both the daily Telegram broadcast (L32) and the daily
page refresh (L31) would break** with ModuleNotFoundError (`yuclaw.telegram`,
`v3.web.render_landing` both gone/archived).

## 5. Cron → file → worktree map (YUCLAW entries only; apex_trading crons excluded)

| Cron (sched) | Worktree it runs in | File/module invoked | Notes |
|---|---|---|---|
| `*/30 * * * *` | main | `/home/zhangd2/yuclaw/engines/check_nemotron.sh` | model health |
| `30 16 * * *` | main | `cron/track_record_builder.sh` | |
| `0 23 * * *` | main | `cron/swarm_debate.sh` | |
| `0 2,6,10,14,18,22` | main | `cron/sentiment_archive.sh` | |
| `0 22 * * *` | main | `cron/pytorch_check.sh` | |
| `*/30 * * * *` | main | `cron/health_monitor.sh` | |
| `15 18 * * *` | main | `cron/atros_daily.sh` | |
| `0 * * * *` | main | `cron/oil_engine.sh` | hourly oil |
| `0 23 * * *` | main | `cron/oil_brief.sh` | |
| `0 17 * * 1-5` | **v3** (`cd yuclaw-v3`) then **main** | `v3.signal.healthcheck` → `snapshot_writer` → `v3.track.outcome_updater` → `v3.radar.run` → `v3.proof.ledger` → then `/home/zhangd2/yuclaw/cron/refresh_v3_pages.sh` | **This is the auto-publish engine.** `refresh_v3_pages.sh` (`REPO_DIR=/home/zhangd2/yuclaw`) renders `v3.web.render_landing` + `v3.track.render_html`, `git add docs/index.html docs/validation.html`, commits `auto: v3.0 page refresh`, **`git push origin main`**. |
| `35 7 * * 1-5` (≥2026-06-04) | main | `python3 -m yuclaw.telegram.broadcast_bot daily` | **The daily Telegram signal.** Depends on root `yuclaw/telegram/` (main-only). |

**Live-critical paths that must not break:** root `yuclaw/` package (broadcaster
+ siblings), `v3/web/render_landing.py`, `v3/track/render_html.py`, all
`/home/zhangd2/yuclaw/cron/*.sh`, and the **`main`** branch as the GitHub-Pages
publish target.

---

## 6. Recommended canonical structure (post-v4)

A single canonical branch should hold BOTH the v4 product AND the live-serving
infra, with one unambiguous home per file:

```
<canonical branch>
├── v3/                      # v3 pipeline + web renderers (live)
│   ├── web/render_landing.py        # canonical landing renderer (from main)
│   └── track/render_html.py
├── yuclaw/                  # v4 product package (API, MCP v2, demo, memo, cascade)
│   └── telegram/broadcast_bot.py    # canonical v4-format broadcaster (from main)
├── cron/                    # all *.sh wrappers (from main)
├── docs/                    # GitHub Pages publish dir (generated)
├── archive/v2/              # genuinely-dead v2.3 code ONLY
└── output/                  # gitignored or data-only (see §9)
```

Key principle: **archival should not have swept up files the live system still
imports.** `broadcast_bot.py` and `rebuild_html.py` were archived on
v3.0-evidence but are still live on main → they must be **un-archived** (or the
broadcaster relocated into the v4 `yuclaw/` package and the crons repointed).

## 7. Reconciliation strategy options

### Option A (RECOMMENDED) — main becomes canonical; graft v4 product into it
Make `main` the canonical branch (it is already the publish target and holds all
live infra + the newer broadcaster), and **cherry-pick / merge only the 25
v3.0-evidence product commits** into it, resolving the archival-move conflicts in
main's favor for live files.
- **Pros:** zero cron repointing (all live paths stay where crons expect them);
  the 112 auto-publish commits never need replaying; main's newer broadcaster
  and only-copy `render_landing.py` are preserved natively.
- **Cons:** must replay/curate 25 commits; the v4 archival reorg (`archive/v2/`)
  has to be re-applied selectively (archive only truly-dead files, NOT the live
  broadcaster/rebuild_html).
- **Net:** lowest operational risk; aligns repo to how production already runs.

### Option B — v3.0-evidence becomes canonical; port infra onto it
Make `v3.0-evidence` canonical (it is the product source-of-truth), then port
`render_landing.py`, the v4-format broadcaster, and `cron/*` onto it, un-archive
the live files, and **repoint every cron** + the Pages publish branch.
- **Pros:** keeps the clean archival reorg as the base.
- **Cons:** must port main's newer broadcaster (+72/−129 vs the archived copy),
  recreate `render_landing.py` there, **repoint ~11 crons and the GitHub-Pages
  source branch**, and collapse 112 auto commits. Highest breakage surface.

### Option C — squash-merge main's product delta, keep two roles
Keep `main` as publish branch; periodically **squash** the v4 product delta from
v3.0-evidence into main via a single reconciliation commit (not a full history
merge), then retire `v3.0-evidence` to a tag.
- **Pros:** one clean commit, no 112-commit replay, history stays legible.
- **Cons:** loses granular v4 commit history (mitigated by tagging
  `v3.0-evidence` before retiring).

**Recommendation:** **Option A**, with the archival reorg re-applied
*surgically* (archive only dead v2.3 files, never live ones). Option C is a
strong fallback if commit-by-commit conflict resolution proves too costly.

## 8. Proposed git sequence (PROPOSAL — DO NOT EXECUTE)

Illustrative, for Option A. To be performed in a **throwaway worktree**, never in
a live checkout, and only after review:

```
# 1. Snapshot/escape hatch — tag both branches before touching anything
git tag pre-reconcile/main main
git tag pre-reconcile/v3.0-evidence v3.0-evidence
git push origin --tags                      # off-machine backup

# 2. Fresh isolated worktree off main (does NOT disturb the live main checkout)
git worktree add /home/zhangd2/yuclaw-reconcile -b v4.1-reconcile main

# 3. Bring the 25 product commits in. Prefer a single curated merge so the
#    archival-move conflicts are resolved once, in main's favor for LIVE files:
cd /home/zhangd2/yuclaw-reconcile
git merge --no-commit v3.0-evidence
#    -> resolve ~6 content conflicts; for the ~114 location conflicts, KEEP the
#       live path for broadcaster/rebuild_html, ACCEPT archive moves only for
#       genuinely-dead v2.3 files. render_landing.py: keep main's.
git commit -m "v4.1: reconcile v4 product (v3.0-evidence) onto live main; live paths preserved"

# 4. Validate WITHOUT touching crons (dry runs in the reconcile worktree):
python3 -m v3.web.render_landing            # must still succeed
python3 -m yuclaw.telegram.broadcast_bot --dry-run   # must still import & run
python3 -m pytest                            # product + regression guard

# 5. ONLY after Gemini + VinZhang sign-off: fast-forward main, push.
#    (Separate, explicitly-approved step — NOT part of this session.)
```

No step above is run in this session.

## 9. Dirty-main-worktree resolution

The 145 `output/` artifacts are cron data, not source. Recommended:
1. **Before** reconciliation, add `output/` (and `docs/data/`) to `.gitignore`
   on the canonical branch if not already, so data churn stops polluting status.
2. The 5 currently-tracked `output/*.json` files should be `git rm --cached`
   (untrack, keep on disk) so the working tree goes clean without deleting data.
3. Do **not** stash/clean before reconciling — a stash could collide with cron
   writes mid-flight. Let the reconcile happen in a separate worktree; the live
   main checkout's dirty `output/` is irrelevant to a worktree-based merge.

## 10. Cron continuity plan

- **Freeze window:** pause the two publishing crons (L31 page-refresh, L32
  Telegram) for the reconcile+cutover window only — comment them out, do the
  cutover, re-enable. (Requires a crontab edit → **separate approved step**, not
  this session.)
- **Path invariants:** after reconciliation, verify these still resolve:
  `v3.web.render_landing`, `v3.track.render_html`, `yuclaw.telegram.broadcast_bot`,
  and every `cron/*.sh`. The §8 step-4 dry runs gate this.
- **Publish target unchanged:** GitHub Pages keeps serving from `main` (Option A)
  → no Pages reconfiguration, no DNS/settings change.

## 11. Risk register

| Risk | Likelihood | Impact | Mitigation / rollback |
|---|---|---|---|
| Reconcile archives a live file → cron ImportError | Med | High (silent daily-signal outage) | §8 step-4 dry runs of both publishing entrypoints before cutover; `pre-reconcile/*` tags for instant revert |
| 112 auto commits replayed → history bloat / more conflicts | Med | Med | Merge (not rebase) the product delta; never cherry-pick auto commits |
| Broadcaster content regression (main newer than v3) | Med | High (wrong/old Telegram format) | Resolve broadcaster conflicts in **main's** favor; diff-review the merged file |
| Cron fires mid-cutover → partial/again-divergent push | Low | Med | Freeze L31/L32 during the window |
| Pages serves a half-rendered page | Low | Med | Render+commit atomically; verify `docs/index.html` locally before re-enabling L31 |
| Loss of v4 product history | Low (Option A/B) / Med (C) | Low | Tag `v3.0-evidence` before any retirement |

**Universal rollback:** `git reset --hard pre-reconcile/main` in the reconcile
worktree (or never fast-forward live main until validated). The live main branch
is not mutated until the final, separately-approved push.

## 12. Open questions for Gemini / VinZhang

1. Option A vs C — is granular v4 commit history worth the commit-by-commit
   conflict cost, or is a squash acceptable (with a `v3.0-evidence` tag)?
2. Canonical home for the broadcaster: leave at `yuclaw/telegram/` (live now) or
   relocate into the v4 package layout? (Affects the L32 cron module path.)
3. Should `output/` and `docs/data/` be fully gitignored going forward to stop
   the auto-publish churn that caused this divergence in the first place?
4. Two scripts write `docs/index.html` (`v3.web.render_landing` and legacy
   `rebuild_html.py`) — confirm `rebuild_html.py` is dead and can be archived.
