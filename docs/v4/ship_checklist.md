# YUCLAW v4.0.0 — Ship Checklist

**Ship date:** 2026-06-03 (Wednesday morning) · **Branch:** `v3.0-evidence` → `main` · **Tag:** `v4.0.0`

Run top to bottom. The daily page-refresh cron is **kept** — its rendered output was rebranded to
v4 on 2026-06-01 (commit `53328586` on `main`), so it now auto-publishes the v4 dashboard. No disable
needed (see Step 4a).

---

## ⚠️ Pre-flight decisions (resolve BEFORE Step 4)

These three are not yet decided. Each blocks part of the sequence.

1. **PyPI name.** `yuclaw` 2.3.0 already exists on PyPI. Publishing `yuclaw` 4.0.0 supersedes it
   (intended — the README says `pip install yuclaw`). Confirm you own the PyPI project and want the
   major-version replacement. *(If not: rename the package and update every `pip install yuclaw`
   reference first — bigger change, not recommended for this ship.)*

2. **Landing page — RESOLVED (2026-06-01).** Keep the auto-refreshing dashboard; the renderer
   `~/yuclaw/v3/web/render_landing.py` was rebranded to v4 (title/brand/version/features, canonical
   `COMPLIANCE_NOTICE` embedded) and pushed to `main` (commit `53328586`). The live page at
   https://yuclawlab.github.io/yuclaw-brain/ now serves the v4-branded 79-signal dashboard. No cron
   disable, no minimal-landing merge. See Step 4a.

3. **Merge strategy.** Merge-commit (preserves the 10-day history) vs squash (one clean `main` commit).
   Recommendation: **merge-commit** — the granular history is part of the story.

---

## Step 0 — Grade distribution sanity (start of ship day)
The daily 17:00 cron already refreshes `signal_snapshots` with anatomy+grades, but re-run it at ship
time so the launch reflects the freshest data, and confirm the distribution hasn't regressed from the
2026-06-01 baseline (**7 B · 24 C · 48 Insufficient**, all 79 with anatomy).
```bash
cd ~/yuclaw-v3 && python3 -m v3.signal.snapshot_writer      # full universe; ~minutes
psql "dbname=yuclaw_events" -c "
WITH latest AS (SELECT DISTINCT ON (ticker) ticker, composite_confidence c,
  COALESCE(array_length(evidence_event_ids,1),0) ev,
  (SELECT count(*) FROM events e WHERE e.event_id = ANY(s.evidence_event_ids) AND e.llm_confidence>=0.7) strong
  FROM signal_snapshots s WHERE is_backfill=false ORDER BY ticker, signal_time DESC)
SELECT CASE WHEN coalesce(c,0)>=0.75 AND strong>=3 THEN 'A' WHEN coalesce(c,0)>=0.55 AND ev>=1 THEN 'B'
            WHEN coalesce(c,0)>=0.30 THEN 'C' ELSE 'Insufficient' END grade, count(*)
FROM latest GROUP BY 1 ORDER BY 1;"
```
Expect: **all 79 carry anatomy**, with ≥~30 at Grade C or better (B+C). YELLOW launch is fine; if it
**regressed** (e.g. anatomy NULL again, or B+C collapses toward 0), STOP and investigate before shipping.

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
> `docs/index.html` is **cron-owned on `main`** (auto-rendered v4 dashboard). On `v3.0-evidence` it
> was repurposed to the same v4 render, so the merge should be clean. **If git still flags a
> `docs/index.html` conflict, always take `main`'s version** (it's the live, freshest cron output):
> `git checkout --theirs docs/index.html 2>/dev/null || git checkout main -- docs/index.html`.

### Step 4a — Page-refresh cron: KEPT (no disable needed)
The cron `0 17 * * 1-5` (the v3 pipeline) ends with `refresh_v3_pages.sh`, which renders
`v3.web.render_landing` → `docs/index.html` and pushes it to `main`. **As of 2026-06-01 that renderer
emits the v4-branded dashboard** (commit `53328586`), so the auto-refresh now publishes v4. Nothing to
disable — the dashboard stays live and self-updating at 17:00 weekdays.
```bash
# Confirm the live renderer is the v4 one (run anytime):
grep -c "YUCLAW v4.0" ~/yuclaw/v3/web/render_landing.py    # expect >= 1
curl -s https://yuclawlab.github.io/yuclaw-brain/ | grep -oE '<title>[^<]*</title>'  # YUCLAW v4.0 …
```
Rollback (if the v4 rebrand ever breaks rendering): `git -C ~/yuclaw revert 53328586 && git -C ~/yuclaw push origin main` — the next cron run republishes the prior v3.0 page.

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
Open https://yuclawlab.github.io/yuclaw-brain/ (allow ~1 min for Pages to rebuild). Expect the
**v4.0-branded** auto-refresh dashboard: title "YUCLAW v4.0 …", the features line, the 79-signal
table, canonical compliance, 0 buy/sell.
```bash
curl -s https://yuclawlab.github.io/yuclaw-brain/ | grep -oE '<title>[^<]*</title>'        # YUCLAW v4.0 …
curl -s https://yuclawlab.github.io/yuclaw-brain/ | grep -ciE 'STRONG_BUY|STRONG_SELL|Sepolia'  # expect 0
```

## Step 7b — Telegram daily resume (auto, from Thursday)
The daily 09:35-ET cron was restored 2026-06-01 (date-guarded to first fire **Thu 2026-06-04**) and its
format is now **v4** (main commit `90bf0770`): 8 locked labels, live `signal_snapshots`, evidence grade
+ ledger hash, canonical compliance — 0 buy/sell. The Wednesday **launch** broadcast is a separate
manual send (one-liner in [`telegram_bot.md`](telegram_bot.md)).

**Thursday 2026-06-04 ~07:36 ET — manual verification (do this):** open `@yuclaw_signals` and confirm
the auto-post is the **v4 format** (header "🦞 YUCLAW Research Signals", per-signal Grade + filing count
+ `ledger …`, canonical compliance line) and **not** the old `STRONG_BUY top 5` v2.3 format. If it
didn't post, check `/tmp/yuclaw_telegram.log`. Optional pre-check anytime:
```bash
cd ~/yuclaw && set -a && . ~/.yuclaw_env && set +a && python3 -m yuclaw.telegram.broadcast_bot daily --dry-run
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
`drafts/v4.0.0_telegram.md` (Telegram). Not automated. Both now carry the **YELLOW evidence-transparency
caveat** (X tweet 4/8; Telegram line above the compliance footer) — keep it in; it's the honest framing,
not an apology.

## Step 12 — End of ship day: confirm Thursday auto-fire still date-guards
The daily Telegram cron is set to first fire **Thu 2026-06-04 07:35 MDT** in the **v4 format**. Before
logging off ship day, confirm the guard is intact so nothing posts early and the resume is the v4 format:
```bash
crontab -l | grep "broadcast_bot daily"          # exists, guarded >= 20260604, \% escaping intact
for d in 20260602 20260603 20260604; do echo "$d: $( [ "$d" -ge 20260604 ] && echo FIRES || echo blocked ); done
cd ~/yuclaw && set -a && . ~/.yuclaw_env && set +a && python3 -m yuclaw.telegram.broadcast_bot daily --dry-run | head -6
```
Expect: one guarded line; 06-02/06-03 blocked, 06-04 FIRES; dry-run shows the v4 header + grade-first
signals. Then verify the real post on **Thu ~07:36 ET** per Step 7b.

---

## Rollback notes
- PyPI release is **not** deletable (only yankable): `twine` is the point of no return — do Steps 1–7
  and Step 9-on-local-wheel first, treat Step 8 as the commit point.
- A bad `main` merge is revertable (`git revert -m 1 <merge-sha>`); re-enable the cron if you reverted
  decision (A).
- The tag can be moved before the GitHub release exists; avoid moving it after.
