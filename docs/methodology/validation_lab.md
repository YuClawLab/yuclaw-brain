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

## Construction rules (fixed, documented constants)

- **Rebalance:** at every distinct signal date in the panel.
- **Weighting:** equal-weight within each cohort.
- **Holding:** each cohort is held from its rebalance date to the next rebalance
  date (chained into a cumulative series); the final period runs to the last
  available price date.
- **Decile fraction:** 10% (`DECILE_FRACTION = 0.10`).
- **Benchmark:** **SPY** — a broad-market reference present in `price_history`
  over the study window. SPY is a benchmark for context only.
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

- **In-sample:** signal dates 2026-02-18 → 2026-05-13 (13 rebalances), evaluated
  against prices through 2026-05-20 — a real ~65-trading-day window.
- **Forward:** signal dates 2026-05-20 → 2026-06-10 (16 rebalances), now
  evaluable against fresh `price_history` (the daily feed was restored
  2026-06-10). **Early forward period — ~16 trading days, NOT yet statistically
  meaningful**: a window this short cannot support inference and is shown only as
  a directional illustration that accrues as the forward record lengthens. This
  caveat is rendered prominently on the forward panel.

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
