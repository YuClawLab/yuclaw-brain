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

## Statistical rigor panel (Panel 3, added 2026-07-05)

Every statistic carries its n and window; the two panels are never blended.

- **Spread tests** — per-rebalance arithmetic spreads (top − bottom decile;
  top decile − equal-weight universe): mean per period, percentile-bootstrap
  95% CI (10,000 i.i.d. resamples of rebalance periods, fixed seed 20260518),
  one-sample t vs 0 with exact Student-t p-values.
- **Information coefficient** — per-signal-date cross-sectional Spearman IC of
  composite score vs realized 1/5/20-day forward returns (track-record
  outcomes, as-of matured), Fama–MacBeth mean across dates. Because
  consecutive daily signal dates share most of a multi-day return window, the
  IC series is serially correlated and the naive t overstates significance:
  t-stats are **Newey–West (Bartlett) HAC-corrected** with lag =
  ceil(horizon / average date spacing) − 1. Horizons whose T provides fewer
  than ~3 independent blocks are flagged descriptive-only.
- **Market model** — OLS of top-decile per-period cohort returns on the
  equal-weight universe and (separately) SPY: alpha per period and annualized
  via the panel's average holding period, beta, t(alpha), R², n. A **power
  note** states the minimum detectable |alpha| (80% power, 5% level) at the
  current n, so "not significant" is quantified rather than asserted.

Honest reading as of first publication: at current sample sizes, no forward
spread, IC, or alpha is significant at 5% once overlap is corrected. That is
the finding, and the panel recomputes daily as the record accrues.

## Reproducibility (replay bundle)

`docs/replay/lab_replay_bundle.json` (regenerated daily) + `tools/replay_lab.py`
(Python ≥3.10, stdlib only) reproduce the Lab's core tables off-box: cohorts are
rebuilt from bundled scores, statistics recomputed (same bootstrap seed), and
every forward snapshot's sha-256 leaf hash is recomputed from disclosed derived
inputs and rolled into daily roots matched against the public yuclaw-trust
ledger. **Compliant data path:** the bundle contains YUCLAW-derived data only —
scores, locked labels, component scores, content hashes, derived period
returns. No raw vendor OHLCV rows are exported (data-provider terms); analyses
requiring raw prices need the user's own licensed feed.

## AI-ETF Evidence module (docs/etf_evidence.html, added 2026-07-05)

Theme-level evidence aggregation + event study on SMH constituents that are
EDGAR filers in the 79-ticker universe (8 of 26 disclosed holdings, ≈50% of
fund weight, holdings as of 2026-07-03). Foreign-domiciled constituents
(20-F/6-K filers) and foreign-holdings ETFs (KORU-class) are out of
methodological scope: no EDGAR event substrate. CARs use two abnormal-return
models shown side by side — a peer model (EW of the other covered
constituents; removes the sector factor) and the classic SPY market model —
with events deduplicated to one observation per (ticker, type, direction, day)
and eras (backfill vs live-detected) never blended. The first published result
is adverse to the "evidence precedes price adjustment" hypothesis at the
current sample and is displayed as measured.

## Lab v2 display protocol (2026-07-05)

- **Rolling charts:** the public spread and label-cohort charts display a
  continuous series through the latest daily build, with the in-sample →
  forward regime boundary marked (dashed line + shaded in-sample region at
  2026-05-18). The forward segment is rebased at the boundary for visual
  continuity ONLY; every statistic remains computed strictly per-regime.
  Range windows (30/60/90 days) are rebased to their window start.
- **Display-layer label neutralization:** on the public Lab pages cohorts and
  signal labels render in research-neutral vocabulary (High/Low-score cohort,
  POSITIVE_RESEARCH / RISK_FLAG). The locked internal signal-label vocabulary
  in snapshots, the ledger, Telegram, and the dashboard is unchanged.
- **Panel 4 (Evidence-Qualified Protocol Candidate):** the decile methodology
  restricted to names qualifying point-in-time on evidence criteria (grade
  A/B, OR ≥1 cited filing, OR a SourceLock-accepted event within 30 days;
  grade "Insufficient" excluded). Evidence-quality fields exist only from
  2026-06-01 (v4.0), so the panel is structurally forward-only. Evidence age =
  days since the last SourceLock-accepted filing event (stale flag >90d).
- **Outage disclosure presentation:** compressed to a one-line integrity card;
  the full text is preserved verbatim in the page's Data Integrity Log.
  Substance never changes; zero retroactive edits.

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

## Evidence-tier boundary (Canada Resources, 2026-07-14)

As of 2026-07-14 the universe file carries a second, **evidence-only tier**: 49
Canada Resources SEC filers (the XEG / ZEO / GDX / URNM core-lens subset of the
Phase-1 feasibility study, `docs/research/canada_resources/`). Evidence-tier
names are ingested (6-K / 40-F / 8-K filings), parsed, classified, and shown on
evidence dashboards — **they are never scored**. They are excluded from
composite scoring, `signal_snapshots`, the decile study, Lab ranking panels,
and the 79-ticker forward-track record.

The boundary is enforced by **positive gating** (`v3/universe_tiers.py`): no
security is scoring-eligible unless its tier is explicitly marked
`scoring_eligible=true`. The scoring tier remains exactly the Deng-reviewed 79;
adding coverage mid-record without this boundary would have been a methodology
event and broken forward comparability. Evidence-tier metadata per name:
`evidence_eligible=true, scoring_eligible=false, lab_universe=false,
coverage_vertical=canada_resources`. One name (Whitecap Resources / WCPRF) is
flagged `listing_quality=low` (OTC proxy line); its price history is not
treated as equivalent to primary US listings.

Full universe expansion, if it ever happens, is a separate, deliberate,
disclosed methodology decision — not an implication of this tier.
