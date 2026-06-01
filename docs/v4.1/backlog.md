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

## 1. Repoint stale market-data components  — TOP PRIORITY

Components **C1/C3/C4/C5/C7** (price momentum, sector velocity, macro regime, oil/rates/fx, peer
correlation) read `~/yuclaw/docs/data/dashboard_state.json` via
`v3/signal/data_loader.py::load_v2_state` (`v3/signal/composite.py:96`). That file is **frozen at
2026-05-20** — the v2.3 `refresh_dashboard` cron that maintained it is retired. So 5 of 9 components
compute from ~12-day-old market data, depressing their per-component confidence and dragging
`composite_confidence` to ~0.28–0.30 for the ~44 borderline tickers — right under the grade-C cliff.

**Options:** (a) restore/replace the dashboard refresh so `dashboard_state.json` updates daily;
(b) repoint these components at a live source; (c) compute live (cached prices) inside the components.
**Impact:** likely lifts many of the 44 borderline tickers over 0.30 → C, materially improving the
grade distribution. **Effort:** medium.

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
