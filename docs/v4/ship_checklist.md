# YUCLAW v4.0.0 — Ship Checklist

**Ship date:** 2026-06-03 (Wednesday morning) · **Branch:** `v3.0-evidence` → `main` · **Tag:** `v4.0.0`

Run top to bottom. Do not skip the ⚠️ pre-flight — there is a daily cron that **republishes
`docs/index.html` to `main`** and will collide with the v4 landing if not handled (see Step 4a).

---

## ⚠️ Pre-flight decisions (resolve BEFORE Step 4)

These three are not yet decided. Each blocks part of the sequence.

1. **PyPI name.** `yuclaw` 2.3.0 already exists on PyPI. Publishing `yuclaw` 4.0.0 supersedes it
   (intended — the README says `pip install yuclaw`). Confirm you own the PyPI project and want the
   major-version replacement. *(If not: rename the package and update every `pip install yuclaw`
   reference first — bigger change, not recommended for this ship.)*

2. **Landing-page collision (the big one).** GitHub Pages serves `main` / `/docs`. A cron republishes
   `docs/index.html` there **daily** — see Step 4a. Decide which page is the live v4 site:
   - **(A) Minimal v4 landing** (what's on `v3.0-evidence` now): static, "pip install && demo" funnel.
     → Requires **disabling the page-refresh cron** (Step 4a), else it gets clobbered / the cron's
     push starts failing on non-fast-forward.
   - **(B) Keep the auto-refreshed v3.0 79-signal page**: already compliance-clean (0 buy/sell,
     0 Sepolia, locked vocab, disclaimer present), richer, but v3.0-branded not v4. → Do **not** merge
     `docs/index.html`; leave the cron running.
   - Recommendation: **(A)** for the clean v4 funnel, with the cron disabled. Revisit a real v4
     dashboard in v4.1 (already tracked in `post_funding_followups.md`).

3. **Merge strategy.** Merge-commit (preserves the 10-day history) vs squash (one clean `main` commit).
   Recommendation: **merge-commit** — the granular history is part of the story.

---

## Step 1 — PHASE A re-verify (clean run)
```bash
cd ~/yuclaw-v3
# No live path-based references to archived dirs (expect only ~/yuclaw + SEC-URL regex hits):
grep -rnE "/home/zhangd2/yuclaw/(data|docs/data)" v3/ v4/ sdk/ --include="*.py" | grep -v __pycache__
# Live processes alive:
tmux ls            # expect edgar_poll_v2 + backfill_signals
ps aux | grep -E "edgar_poll_v2|event_worker" | grep -v grep
tail -2 /tmp/edgar_poll_v2.log /tmp/yuclaw_extract.log
```
Expect: the two `.py` refs resolve to the live `~/yuclaw` repo (both files present), processes alive,
poller sweeping with `ticker_errors: 0`. **No reference to any `archive/v2/` path.**

## Step 2 — Compliance regression 21/21
```bash
cd ~/yuclaw-v3 && PYTHONPATH=$PWD python3 -m pytest tests/test_compliance_regression.py -q
```
Expect: `21 passed`. **Hard gate — do not ship if red.**

## Step 3 — Build wheel + sdist on `v3.0-evidence`
```bash
cd ~/yuclaw-v3 && rm -f dist/yuclaw-4.0.0* && python3 -m build --sdist --wheel
python3 -m twine check dist/*
# sanity: archived v2.x must NOT be in the sdist
tar tzf dist/yuclaw-4.0.0.tar.gz | grep -cE 'archive/|clawhub/'   # expect 0
```
Expect: `Successfully built`, both `twine check` PASSED, archive count `0`.

## Step 4 — Merge `v3.0-evidence` → `main` (merge commit)
```bash
cd ~/yuclaw-v3
git checkout main && git pull origin main
git merge --no-ff v3.0-evidence -m "release: YUCLAW v4.0.0 — Agent Research API"
```
> If pre-flight decision #2 = **(B)**, before committing the merge restore the v3.0 landing:
> `git checkout main -- docs/index.html docs/app.html` so the merge doesn't overwrite it.

### Step 4a — ⚠️ Handle the page-refresh cron (only if decision #2 = A)
The cron `0 17 * * 1-5` (the v3 pipeline) ends with `refresh_v3_pages.sh`, which runs from
`~/yuclaw` on `main` and does `git add docs/index.html docs/validation.html → commit → push origin main`.
**After the v4 landing is on `main`, the next weekday 17:00 run will regenerate the v3.0 page and
either clobber the v4 landing or fail its push (non-fast-forward).** Pick one:
```bash
# Option 1 — drop ONLY the page-publish step, keep the data pipeline (recommended):
crontab -e
#   edit the 17:00 line to remove the trailing:  && /bin/bash /home/zhangd2/yuclaw/cron/refresh_v3_pages.sh
# Option 2 — neutralize the script so it renders but never pushes:
#   comment out the `git push origin main` line in ~/yuclaw/cron/refresh_v3_pages.sh
```
Verify it will no longer publish: `grep -n "git push" ~/yuclaw/cron/refresh_v3_pages.sh` and confirm
the 17:00 crontab line no longer calls `refresh_v3_pages.sh`.

## Step 5 — Tag `v4.0.0` on the merge commit
```bash
git tag -a v4.0.0 -m "YUCLAW v4.0.0 — Agent Research API"
```

## Step 6 — Push `main` + tag
```bash
git push origin main
git push origin v4.0.0
```

## Step 7 — Verify the live site
Open https://yuclawlab.github.io/yuclaw-brain/ (allow ~1 min for Pages to rebuild).
- Decision (A): shows the minimal **v4.0** landing, `pip install yuclaw && yuclaw demo`, 0 buy/sell.
- Decision (B): still the v3.0 79-signal page (compliance-clean), unchanged.
```bash
curl -s https://yuclawlab.github.io/yuclaw-brain/ | grep -ciE 'STRONG_BUY|STRONG_SELL|Sepolia'  # expect 0
```

## Step 8 — Publish to PyPI
```bash
cd ~/yuclaw-v3 && python3 -m twine upload dist/yuclaw-4.0.0.tar.gz dist/yuclaw-4.0.0-py3-none-any.whl
```
(Confirm pre-flight #1 first. Needs a PyPI API token.)

## Step 9 — Fresh-venv smoke test (final verification)
```bash
python3 -m venv /tmp/v4ship && /tmp/v4ship/bin/pip install --upgrade pip
/tmp/v4ship/bin/pip install yuclaw            # from PyPI, not the local wheel
/tmp/v4ship/bin/yuclaw demo --no-pause        # expect exit 0, full Why-AMD journey, VERIFIED
```

## Step 10 — GitHub release
Create a release from the `v4.0.0` tag using `drafts/v4.0.0_release_notes.md`. Attach the wheel + sdist.
```bash
gh release create v4.0.0 dist/yuclaw-4.0.0* -t "YUCLAW v4.0.0 — Agent Research API" -F drafts/v4.0.0_release_notes.md
```

## Step 11 — (optional) Announce — VinZhang's manual call
After watching the dashboard for ~1 hour, post `drafts/v4.0.0_x_thread.md` (X) and
`drafts/v4.0.0_telegram.md` (Telegram). Not automated.

---

## Rollback notes
- PyPI release is **not** deletable (only yankable): `twine` is the point of no return — do Steps 1–7
  and Step 9-on-local-wheel first, treat Step 8 as the commit point.
- A bad `main` merge is revertable (`git revert -m 1 <merge-sha>`); re-enable the cron if you reverted
  decision (A).
- The tag can be moved before the GitHub release exists; avoid moving it after.
