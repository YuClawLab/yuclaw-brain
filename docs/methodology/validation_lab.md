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

## Academic analytics — formal definitions

The PRO Lab adds five cross-sectional analytics on top of the cumulative-cohort
curves. Each is computed **separately for the forward (OOS) and in-sample
panels** and displayed in clearly tagged panels — never blended. All are
**descriptive statistics**; none is significance-tested on the forward window.
Engine: `v3/lab/analytics.py` (read-only; reuses the cohort engine's
point-in-time return convention).

**(a) Full decile spectrum.** At each rebalance the universe is sorted by
composite `total_score` and partitioned into ten equal buckets, **D1 = highest
score … D10 = lowest**. Each bucket's equal-weighted next-period return is
computed, then **pooled (averaged) across rebalances** to give the decile
spectrum bar. The academic test is **monotonicity**: a skilful score yields
returns that decrease monotonically from D1 to D10. We report **Spearman ρ
between score-decile order and mean return** (ρ ≈ +1 = perfectly monotone in the
expected direction; ρ ≈ 0 = no cross-sectional separation), the D1−D10 spread,
and the count of monotone-decreasing steps (out of 9).

**(b) Information coefficient (IC).** For each rebalance, the IC is the
**Spearman rank correlation between composite score and the next-period return**
across all ~79 names (tie-corrected average ranks). We report the IC time-series,
**mean IC**, **IC>0 hit-rate**, and **ICIR = mean(IC)/stdev(IC)** — a descriptive
consistency ratio, *not* an annualized information ratio and *not* a
significance test. N (number of rebalances) is shown on every IC chart.

**(c) Event study.** Event time is reset to 0 each time a name **enters** a
decile (present in the decile at rebalance *t* but not at *t−1*). For each entry
we track the **cumulative return relative to SPY** (cohort name minus benchmark,
compounded from the entry date) over the following ≤20 trading days, then average
across all entries. The shaded band is **±1 cross-event standard deviation**
(dispersion across events, *not* a confidence interval). Top-decile entries and
bottom-decile entries are shown as separate curves.

**(d) Top-minus-bottom spread + drawdown.** The chained cumulative **D1 − D10**
cohort-return spread, drawn with **underwater (drawdown) shading** beneath its
running peak and the **maximum drawdown** annotated. This is the same research
spread statistic defined above — a descriptive transparency measure, explicitly
**not** a position and not tradeable.

**(e) Cohort turnover & persistence.** Per rebalance, **turnover** = the fraction
of the prior top-decile cohort that is no longer in the top decile at the next
rebalance (set difference ÷ cohort size). **Persistence** = the average number of
consecutive rebalances a name remains in the top decile. These quantify how
*reactive* vs. *stable* the score is over time. They are presented purely as
**research transparency** on cohort composition — not a product, not an index, and
not a trading rule.

**Honest-statistics discipline.** On the forward window **no t-statistics and no
significance claims are reported** — the sample (≈16 trading days, ~14 evaluable
rebalances) is far too small for inference, and we say so on the page. In-sample
analytics carry the parametric look-ahead disclosure (below) and are
systematically optimistic. Nothing is annualized or extrapolated. Where a result
is weak or non-monotonic, **it is shown as-is** rather than replaced by a
flattering cut.

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

## Toward an open index methodology (long-horizon direction — not a current product)

The transparency analytics above — particularly the **turnover and persistence**
statistics and the **fully documented, fixed construction rules** — are the same
building blocks a **rules-based research index** would require. We note this
direction explicitly and honestly: a long-horizon possibility is that YUCLAW's
cohort construction could one day be published as a **transparent, reproducible,
rules-based research index methodology** — every rule disclosed, every figure
recomputable from a public ledger, in the open-methodology spirit of the academic
factor literature (Fama–French and its successors). The stability and turnover
metrics matter precisely because any credible index methodology must be auditable
for how often its constituents change.

To be unambiguous: **this is a research direction, not a current product.** There
is **no index product, no investable vehicle, and no index brand** today, and
nothing on the Lab page is offered as one. Any future move toward an
index-branded or investable artifact is **explicitly gated on legal/compliance
review** — it would not be published under an index name, marketed, or framed as
investable until counsel has reviewed it. Until then these remain **descriptive
research statistics** presented for transparency and academic discussion only.
This subsection documents intent and guardrails; it does not announce a product.

## Reproducibility

Engine: `v3/lab/cohort_engine.py` (cohort curves, spreads) and
`v3/lab/analytics.py` (decile spectrum, IC, event study, turnover); charts are
rendered by `v3/web/chartkit.py` (self-contained inline SVG, no external
libraries). All constants are module-level and fixed; every module is read-only
on `signal_snapshots` and `price_history`. Every number on the page recomputes
deterministically by running the renderer (`v3/web/render_validation_lab.py`)
against the database.
