# YUCLAW v4.1 Backlog — Evidence Freshness & Coverage

**Origin:** v4.0 launch-readiness investigation, 2026-06-01.

After the 17:00 cron refreshed all **79** signals with `component_anatomy` + `composite_confidence`
(the prior 76 were stale pre-anatomy rows from the 2026-05-29 cron, which predated the anatomy code
in commit `c196ad00`), the Evidence Quality Grade distribution is:

| Grade | Count | composite_confidence |
|---|---|---|
| A | 0 | — |
| B | 7 | 0.55–0.65 |
| C | 24 | 0.31–0.54 |
| **Insufficient** | **48** | 0.18–0.30 |

**Key observation:** **44 of the 48 Insufficient tickers sit at conf 0.20–0.30** — a hair below the
grade-C cutoff (0.30). This is a *calibration cliff*, not an evidence void. The confidence values
cluster tightly (e.g. 0.298 for XOM/COP/WFC/MS), which points at a shared upstream input — the stale
market-data dependency below.

---

## 0. Reconcile `v3.0-evidence` and `main` branches  — ⭐⭐ TOP PRIORITY (target: within 1 week of v4.0 ship)

**Why:** v4.0 shipped 2026-06-02 by tagging `v3.0-evidence` (the canonical v4 tree) — the merge into
`main` was **deliberately deferred** because a `--no-ff` merge produced **120 conflicts**. main and
v3.0-evidence diverged for ~2 weeks (123 vs 22 commits off base `ef570aa5`): v3.0-evidence archived the
whole v2.3 tree to `archive/v2/`, while main kept it live, accrued daily cron commits, and received
three v4 operational commits **made directly on main**. PyPI + the live dashboard already serve v4;
only main's default-branch *view* lags. No functional impact — purely a repo-structure inconsistency.

**Specific decisions required (do not auto-resolve):**
1. **Permanent home of `yuclaw/telegram/broadcast_bot.py`** — the live v4 Telegram broadcaster the daily
   cron imports as `yuclaw.telegram.broadcast_bot`. On v3.0-evidence the whole `yuclaw/` package is
   archived to `archive/v2/`, so a naive merge would **archive the live broadcaster and break the cron**.
   Decide: keep it at `yuclaw/telegram/` (partial-archive exception), or move to a v4 path (e.g.
   `v4/telegram/`) and update the cron.
2. **Permanent home of `v3/web/render_landing.py`** — the dashboard renderer the page-refresh cron runs.
   Currently main-only (not on v3.0-evidence). Decide its canonical location and keep the cron working.
3. **Canonical post-v4 directory structure** — what stays at root, what lives under `archive/v2/`.
4. **Cron continuity** — guarantee both the dashboard refresh cron (`refresh_v3_pages.sh` →
   `v3.web.render_landing`) and the Telegram daily cron (`yuclaw.telegram.broadcast_bot`) keep importing
   and running through *any* restructure.

**Strategy:** fresh branch off `main`; cherry-pick v3.0-evidence's changes selectively; resolve each
conflict by **explicit written policy** (v4 doc rewrites → take v3.0-evidence; `docs/index.html` →
keep main's cron-owned page; legacy tree → archive; live operational files → keep at a working,
importable location); **full smoke-test of every cron** before push; **Gemini architectural review**
of the reconciliation plan before merge.

**Target:** within 1 week of v4.0 ship. **Risk if delayed:** ongoing visible inconsistency between
`main` and PyPI/dashboard, but **no functional impact** (all live crons run from their current
locations on the un-merged main). A `MAIN_BRANCH_NOTICE.md` is committed at main root pointing users to
the v4.0.0 tag / PyPI / `v3.0-evidence` in the meantime.

---

## 1. Repoint stale market-data components  — ⭐ HIGHEST PRIORITY (target: land within 2 weeks of v4.0 ship)

Components **C1/C3/C4/C5/C7** (price momentum, sector velocity, macro regime, oil/rates/fx, peer
correlation) read `~/yuclaw/docs/data/dashboard_state.json` via
`v3/signal/data_loader.py::load_v2_state` (`v3/signal/composite.py:96`). That file is **frozen at
2026-05-20** — the v2.3 `refresh_dashboard` cron that maintained it is retired. So 5 of 9 components
compute from ~12-day-old market data, depressing their per-component confidence and dragging
`composite_confidence` to ~0.28–0.30 for the ~44 borderline tickers — right under the grade-C cliff.

**Dual benefit — this is why it's #1:** fixing it (a) lifts many of the 44 borderline tickers over
0.30 → C, materially improving the grade distribution AND (b) restores actual **signal freshness** —
today 5 of 9 components run on 12-day-old prices/momentum/macro (only the C6 evidence layer is live).
It is the single highest-leverage post-launch fix: it improves both the headline grade story and the
underlying signal quality.

**Concrete first task (the investigation, before any rebuild):**
1. Determine **why** the `dashboard_state.json` refresh stopped — find the retired cron/script
   (start: `~/yuclaw/refresh_dashboard.sh`, `engines/run_screener.py`, the v2.3 pipeline) and when/why
   it was removed (crontab history, git log, the v2.3 retirement during the v4 cleanup).
2. **Document the original mechanism** end-to-end: what wrote `dashboard_state.json`, on what schedule,
   from what data source (yfinance? cached prices?), and which fields C1/C3/C4/C5/C7 actually consume.
3. **Propose 3 implementation paths** with effort/risk for each:
   - (a) **Restore** the v2.3 refresh cron (fastest; re-couples to retired v2.3 code).
   - (b) **Repoint** the 5 components to a live source / small fresh-price service (clean separation).
   - (c) **Compute live** inside the components from cached EDGAR/price data (most self-contained;
     biggest change).

**Effort:** medium. **Target:** within 2 weeks of v4.0 ship.

## 2. Broaden EDGAR event coverage

Only **34/79** tickers have accepted events in the last 30 days (the C6 lookback); 45/79 within 90
days. Grade B requires `conf≥0.55 AND ≥1 evidence`, so event-less tickers cap at C regardless of
confidence. **Options:** widen ingested filing types (more 8-K items, 10-Q/10-K, 6-K), extend the C6
lookback, or improve extraction recall. **Effort:** medium.

## 3. Dashboard "as of" staleness note  — optional transparency

Until #1 lands, label the price-derived components "as of `<date>`" on the dashboard so the staleness
is explicit to viewers. ~5-min change. **Flagged for approval; not executed.**

## (Considered, deferred) Grade-threshold calibration

`composite_confidence` is an **un-normalized** weighted-confidence mass (`composite.py:142`, `den`),
so it clusters ~0.28–0.30 for a typical signal; the 0.30 C-cutoff bites at the mode of the
distribution. Re-calibrating the thresholds (or normalizing the confidence) would shift the
distribution — but `Confidence.grade_for` (`v4/api/schema.py:162`) is the **canonical v4 rule** shared
by the REST API, dashboard, share card, memo, and the Telegram broadcaster. Any change must be
deliberate and tested, not a launch-eve tweak. **Sequence:** fix #1 (data freshness) first, re-measure,
*then* decide whether the thresholds need re-calibration.
