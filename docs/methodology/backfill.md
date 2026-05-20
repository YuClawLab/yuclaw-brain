# Methodology — Backtest + Forward Tracking

**Last updated:** 2026-05-20

This document describes how the two YUCLAW v3.0 panels are produced:

1. **Backtest Results — In-Sample Replay**
2. **Forward Tracking Ledger — Out-of-Sample**

It is the source of truth for anyone reproducing, auditing, or critiquing the numbers shown on `backtest.html`, in the CLI (`python3 -m v3.cli backtest`), or in any future Telegram / social-media post.

---

## 1. Data window

- **Backfill window:** 2026-02-18 → 2026-05-17 (~90 days). All snapshots in the in-sample panel have `signal_date` inside this window.
- **Forward Tracking Day 0:** 2026-05-20.
- **Important:** the backfill window is **not 2023–2026**. It is a single quarter. Older claims are wrong.

Why this window: the SEC EDGAR backfill that populates the `events` evidence layer ran for 90 days ending 2026-05-17 (the Sunday before the v3.0 public surface launched). Anything earlier is currently unevidenced.

---

## 2. LLM look-ahead bias

- **Model:** Llama 3.1 70B (served locally via Ollama as `yuclaw-llm-70b`).
- **Training cutoff (per Meta model card):** December 2023.
- **Backfill window vs cutoff:** the earliest backfill date (2026-02-18) is ~26 months *after* the training cutoff.

Therefore the LLM cannot have parametric look-ahead into any event in the backfill — none of the 2026 filings existed when it was trained. This rules out the most common look-ahead failure mode in LLM-driven backtests.

The Replay engine adds a secondary safeguard: any `as_of` earlier than 2024-07-01 is flagged with an "in LLM training window" warning. The current backfill window does not trigger this flag.

---

## 3. In-sample reconstruction limitation

In-sample signals were **reconstructed via the replay engine**, not emitted live. For each (ticker, Wednesday) pair, we called `v3.replay.engine.replay(ticker, as_of)` which:

1. Filters the `events` and `signal_snapshots` tables to `available_as_of <= as_of`.
2. Runs all nine signal components against that filtered view.
3. Writes a `signal_snapshots` row with `is_backfill=true`.

**Point-in-time filtering was audited** during Day 5 development:
```
replay("AMD", 2026-03-15) fed 12 events to C6;
zero had available_as_of > 2026-03-15.
```
Equivalent audits for arbitrary (ticker, as_of) pairs are reproducible with `v3/replay/engine.py`.

That said, **reconstruction is still weaker than live emission**. A signal that was reconstructed has never been seen by an external party and cannot be challenged in real time. The Forward Tracking Ledger is the answer to that limitation.

---

## 4. Market-component approximation

The nine components split into two categories for point-in-time accuracy:

| Category | Components | Point-in-time? |
|---|---|---|
| Evidence layer | C6 (event impact), C8 (cascade impact), C9 (model trust) | **Exact** — backed by `events`, `signal_snapshots`, `track_record` with `available_as_of` filters. |
| Market layer | C1 (momentum), C3 (sector velocity), C4 (macro regime), C5 (oil / rates / FX), C7 (peer correlation) | **Approximate** — read v2.3.0 dashboard cache which holds only the latest snapshot. On historical `as_of` they self-degrade to confidence 0.3 with a "point-in-time approximation" warning. |

The in-sample backtest therefore **primarily reflects the evidence layer**. The market components contribute at ~⅓ of their live confidence, so their net effect on composite_score is small.

This is by design for v3.0: the v3.0 evidence layer is what's new. v3.1's work is to ingest historical price / macro into a time-series table so the market layer can also run point-in-time.

---

## 5. Forward Tracking Ledger

- **Day 0:** 2026-05-20. Live emissions begin here.
- **Cadence:** the existing `snapshot_writer` cron emits per-ticker snapshots; `outcome_updater` runs daily at 18:30 MDT to compute matured returns.
- **Maturation:**
  - 1-day outcomes mature next trading day.
  - 5-day outcomes mature ~one trading week later.
  - 20-day outcomes mature ~one trading month later (mid-June for Day-0 signals).
- **At launch:** the Forward panel will show all-zero hit rates with `matured = 0`. This is correct, not a bug.

The ledger accumulates indefinitely. There is no end date.

---

## 6. Definitions

- **Trading day:** any date present in the `price_history` table for SPY (which mirrors the NYSE trading calendar).
- **Raw return at horizon N:** `(close[T+N] − close[T]) / close[T]`, where `T+N` is the *N*th trading day strictly after the signal date.
- **SPY return at horizon N:** the same calculation applied to SPY.
- **Excess return:** ticker return minus SPY return.
- **Hit at horizon N:**
  - **STRONG_BUY / BUY:** hit if return > 0
  - **WEAKENING / NEGATIVE_EVENT / DOWNSIDE_WATCH:** hit if return < 0
  - **HOLD / WATCH:** non-directional → `hit_Nd` is `NULL`, excluded from hit-rate denominators
- **Hit rate:** `hits / eligible`, where `eligible` is the count of matured AND directional signals only. **Coverage and skill are never conflated.**
- **Median return:** computed over matured rows only.

---

## 7. Reproducibility

The whole flow is:

```bash
# 1. price history (yfinance, internal use only — never published raw)
python3 -m v3.track.price_history --start 2026-02-01 --end 2026-06-30

# 2. in-sample replay backfill (Wednesdays in window × universe)
python3 -m v3.replay.backfill_snapshots

# 3. live OOS Day 0 snapshots
python3 -m v3.signal.snapshot_writer

# 4. compute outcomes against price_history (idempotent)
python3 -m v3.track.outcome_updater

# 5. aggregate + display
python3 -m v3.cli backtest
python3 -m v3.track.render_html      # → v3/web/backtest.html
```

All inputs are committed to the repo except `price_history` (Yahoo OHLCV redistribution is restricted). The `outcome_updater` cron (added Day 7) keeps the Forward panel current.

---

## 8. Data sources + attribution

- **SEC EDGAR (public domain).** Form 4, 8-K, 10-Q, 10-K, and 6-K filings are ingested from the SEC EDGAR API (`data.sec.gov/submissions/`, `www.sec.gov/Archives/edgar/data/`). YUCLAW honors the SEC's 10 req/sec rate limit (we self-throttle to ~6 req/sec) and identifies itself in every request via the `User-Agent` header per [SEC's programmatic-access guidance](https://www.sec.gov/os/accessing-edgar-data). Filing data is public domain; YUCLAW redistributes only short excerpts (≤ 600 chars) needed to substantiate the evidence trail, with full source URLs to the SEC archive.
- **Yahoo Finance (internal only).** Daily close + volume for outcome computation come from the `yfinance` Python library. This data is **not redistributed** through any v3.0 endpoint, SDK method, or MCP tool — raw OHLCV stays in the internal `price_history` table. Only derived metrics (returns, hit rates, excess returns vs SPY) are published.
- **YUCLAW-generated data (open).** Composite signals, component scores, LLM-extracted SEC event excerpts, supply-chain edges, cascade children, content hashes, daily roots, and backtest aggregations are YUCLAW's own derivative work — MIT-licensed, freely redistributable.

## 9. Disclaimer

Research / education only. Not investment advice. Past results — backtested or forward-tracked — do not predict future performance. YUCLAW is not a registered investment adviser.
