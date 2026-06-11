# YUCLAW v4.2.0 — Release Notes (DRAFT for review)

## Signal Validation Lab (new)

A Fama–French-style **decile-cohort event study** — built from feedback by
Prof. Deng Shijie (Georgia Tech) — testing whether YUCLAW's composite score
carries forward information. It is **research cohort analysis, not portfolio
management, not a strategy, not trade advice**. Cohorts are grouped by score
decile or signal label (never by trade direction); the market-neutral line is
the *top-decile-minus-bottom-decile cohort spread*, never "long/short". Only
**derived statistics** (returns, spreads, drawdowns) are shown — raw prices are
never displayed or exported.

**Two-panel honesty discipline** (never blended into one curve):

- **Forward (Out-of-Sample)** — look-ahead-free, Day 0 = 2026-05-18.
  > ⚠ **Early forward period — 16 trading days. Not yet statistically meaningful.** A window this short cannot support inference; shown as a directional illustration that accrues as the record lengthens.
  Over the first 16 trading days: top-decile cohort **+6.5%**, bottom-decile
  **−0.8%**, SPY benchmark **+0.4%**, top-minus-bottom cohort spread **+7.1%**.
- **In-Sample Replay** — carries an explicit **parametric look-ahead disclosure**
  (the evidence-extraction model's training cutoff overlaps this window, so
  in-sample results are systematically optimistic — a replay, not a forecast).

## Fresh-data pipeline

The signal components were migrated off a market-data cache that had frozen on
2026-05-18 onto a **live daily `price_history` feed** (restored 2026-06-10). C1
momentum, C3 sector velocity, C5 (sector input), and C7 peer correlation now
compute from current closes. Component math/weights are unchanged — this was a
data-source migration.

> **C4 macro-regime input temporarily frozen as of 2026-05-18 with staleness
> disclosure, pending macro engine restoration.** Its only upstream is the
> retired v2.3 macro engine, and it cannot be price-derived without changing the
> component's math; it is passed through with a disclosure flag until the macro
> engine is restored.

## Reconciled codebase

The long-standing `main` vs `v3.0-evidence` branch split was reconciled: `main`
is now the single canonical branch carrying both the live-serving infrastructure
and the full v4 product (Agent Research API, MCP, demo, SDK). Live paths and the
daily pipeline verified intact post-reconciliation.

## Naming consistency

The install command is now consistently **`pip install yuclaw`** across the
README, docs, and landing page. (An internal SDK packaging-name cleanup is
tracked as a post-flight item; no PyPI changes in this release.)

---

*Hypothetical research illustration. Not investment advice, not performance
advertising, not an offer of any product. Research classifications, not
recommendations. Past results — in-sample or forward-tracked — do not predict
future performance.*
