# Signal Validation Lab — Methodology

> **Hypothetical research illustration. Not investment advice, not performance
> advertising, not an offer of any product. Research classifications, not
> recommendations. Past results — in-sample or forward-tracked — do not predict
> future performance.**

This is an **event study** in the Fama–French decile-cohort tradition: it asks
whether YUCLAW's composite signal *score* carries forward information about
subsequent realized returns. It is **research cohort analysis**, not portfolio
management, not a trading strategy, and not a record of any account. Cohorts are
named by score decile or signal label — never by trade direction.

Built from feedback by Prof. Deng Shijie (Georgia Tech) after reviewing YUCLAW
with his class.

## What is measured

At each rebalance date we sort the research universe by composite `total_score`
and form **cohorts**, then measure each cohort's subsequent equal-weighted
realized return from closing prices already in YUCLAW's internal `price_history`.
Only **derived statistics** (period returns, cumulative returns, cohort spreads,
drawdowns) are produced and displayed — **raw prices are never shown or
exported** (data-provider terms). All figures are YUCLAW-generated and
recompute deterministically from the database.

## Cohorts

- **Top-decile cohort (by composite score)** — the highest-scoring ~10% of the
  universe at each rebalance (~8 names in a ~79-name universe).
- **Bottom-decile cohort (by composite score)** — the lowest-scoring ~10%.
- **Top-minus-bottom cohort spread** — the difference between the two decile
  cohorts' returns. This is a *research spread statistic*, **not** a long/short
  position and not tradeable.
- **Bullish-labeled cohort** — names carrying `STRONG_BULLISH` or `BULLISH`.
- **Cautious-labeled cohort** — names carrying `WEAKENING`, `NEGATIVE_EVENT`,
  `BEARISH_WATCH`, or `RISK_ALERT`.

**Label-cohort caveat:** label cohorts have *variable, sometimes very small*
membership (as few as 1 name on some dates). Small-n cohorts are statistically
noisy and shown for illustration only; cohort sizes (min/median/max) are
disclosed alongside every label-cohort figure and thin cohorts are flagged. The
**decile cohorts** (always ~8 names) are the robust primary comparison.

## Universe & inclusion rule (v2 methodology, 2026-07-05)

The research universe is **79 tickers** (`v3/universe.json`): 49 U.S. large-cap
equities, 15 sector ETFs, 5 broad-market ETFs, and 10 macro ETFs/ETNs (rates,
metals, dollar, China/EM, volatility). All 79 are scored daily.

- **Date inclusion:** a signal date enters the decile study only if it scored at
  least `MIN_UNIVERSE_FOR_DECILES = 40` universe tickers. A "decile" of a
  handful of names is meaningless; anomalous partial-universe dates are excluded
  and the exclusion count is disclosed on the page (currently one: 2026-05-31, a
  non-trading Sunday on which an ad-hoc run scored 3 tickers).
- **Ticker inclusion:** within an included date, a ticker contributes to its
  cohort's period return only if closing prices exist at both the entry and the
  exit date. Priced coverage (min/median/max per rebalance) is disclosed.

## Construction rules (fixed, documented constants)

- **Rebalance:** at every distinct signal date in the panel (subject to the
  inclusion rule above).
- **Weighting:** equal-weight within each cohort.
- **Holding:** each cohort is held from its rebalance date to the next rebalance
  date (chained into a cumulative series). The **forward** panel's final period
  runs to the last available price date; the **in-sample** panel's final period
  is **capped at forward Day 0 (2026-05-18)** so the two panels' return windows
  never overlap (without the cap, the replay's last cohort would keep accruing
  forward-era returns).
- **Decile fraction:** 10% (`DECILE_FRACTION = 0.10`) — 8 of 79 names.
- **References:** the **equal-weight universe cohort** (all scored tickers,
  identical rebalance schedule — the like-for-like internal reference) and
  **SPY** (external broad-market context). Both are references only.
- **Returns:** close-to-close, `close[exit]/close[entry] − 1` per name, averaged
  equally within the cohort.

## Two-panel honesty discipline

The two panels are **never blended into one curve**:

1. **Forward (Out-of-Sample)** — `is_backfill = FALSE`, **Day 0 = 2026-05-18**.
   The honest, look-ahead-free panel; it leads the page.
2. **In-Sample Replay** — `is_backfill = TRUE`. **Look-ahead disclosure:** the
   evidence-extraction model (local Llama) has a training cutoff that overlaps
   the in-sample window, so in-sample signals carry an unavoidable parametric
   look-ahead bias (the same disclosure as the backfill methodology). In-sample
   results are a *replay*, not a forecast, and systematically optimistic.

## Metrics shown

Per cohort and for the spread, per panel: **cumulative return** over the window,
**max drawdown** (Prof. Deng's "min return"), **periodic volatility**, and
**hit-rate vs. benchmark** (fraction of rebalance periods the cohort outperformed
SPY). Descriptive statistics only.

**Annualized returns are intentionally omitted.** Annualizing a ~3-month
(≈65 trading-day) window extrapolates a short sample into a misleading
single-year figure; we show the actual cumulative return and the window length
(N trading days) instead.

## Data coverage & the forward window

- **In-sample:** signal dates 2026-02-18 → 2026-05-13 (13 rebalances), return
  window 2026-02-18 → 2026-05-18 (capped at forward Day 0; 63 trading days).
- **Forward:** signal dates from 2026-05-20, evaluated against daily
  `price_history` through the last completed trading day. **Early forward
  period — NOT yet statistically meaningful**: a window this short cannot
  support inference and is shown only as a directional illustration that accrues
  as the forward record lengthens. This caveat is rendered prominently on the
  forward panel, with the current window dates and rebalance count.

## Freshness & regeneration

The page is rebuilt **daily** by the post-close pipeline
(`cron/refresh_v3_pages.sh`, 17:00 MDT chain) and carries a visible freshness
stamp ("Data through <last trading day> · last build <UTC>"). A health-monitor
check alerts if the build is more than 48 hours old (76h allowance across
weekends, since the pipeline runs Mon–Fri). Before 2026-07-05 the page was a
one-time v4.2 artifact and went stale; that failure mode is now structurally
closed.

## Infrastructure outage disclosure (Jun 26 – Jul 3, 2026)

A network outage on the research host interrupted external data feeds. Daily
signal snapshots continued to be written on-box, point-in-time, throughout the
window — but from Jun 26 to Jul 2 their price-derived component inputs were
frozen at Jun 25 closes (the price feed was unreachable), and public pages were
not republished during the outage. Price history and SEC filing ingestion were
restored and backfilled on 2026-07-03, and the filing window was re-checked
against EDGAR on 2026-07-05 (no missing filings). **No snapshot or ledger row
was retroactively edited** — the outage-window snapshots stand exactly as
written, stale inputs and all. Fabricating retroactive point-in-time data would
invalidate the replayable ledger; disclosed staleness is the honest record.

## C4 macro-regime freeze disclosure

As of the v4.2 signal-data migration, the price-derived component inputs (C1
momentum, C3 sector velocity, C7 peer correlation) read live `price_history`.
The **C4 macro-regime input is temporarily frozen as of 2026-05-18 with staleness
disclosure, pending macro engine restoration** — its only upstream is the
retired v2.3 macro engine, and it cannot be price-derived without altering the
component's math. Cohorts in this Lab are formed from the composite `total_score`,
which therefore carries a frozen macro-regime contribution over the forward
window; this is disclosed for full transparency and does not affect the
score-decile ranking's directional interpretation.

## Reproducibility

Engine: `v3/lab/cohort_engine.py`. All constants above are module-level and
fixed; the engine is read-only on `signal_snapshots` and `price_history`. Every
number on the page recomputes by running the engine against the database.
