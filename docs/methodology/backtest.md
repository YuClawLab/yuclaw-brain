# YUCLAW Backtest Methodology

> ⚠️ **Read first:** YUCLAW is open-source research software. Numbers on the
> dashboard are not financial advice. See the project [DISCLAIMER](../../DISCLAIMER.md).
> If you are evaluating YUCLAW for any real-money decision, read this entire
> page first and reproduce the figures yourself from the scripts referenced
> below.

## Two layers of "results" exist in this system

YUCLAW produces backtest output in two distinct layers. They are computed by
different scripts, cover different windows, and answer different questions.

### Layer 1 — Strategy backtest (the real engine)

**Script:** `engines/run_backtest.py`
**Output:** `output/backtest_all.json`
**Schedule:** nightly at 18:00 MDT weekdays via `cron/nightly_score_refresh.sh`

This is the load-bearing layer. The engine evaluates **ten momentum strategies**
across the `DAILY_CORE` universe (39 tickers — see `yuclaw/universe.py`),
producing strategy-level summary stats:

| Strategy | What it does |
|---|---|
| `mom_1m_top3`  | Long the top 3 names by trailing 1-month return, rebal monthly |
| `mom_1m_top5`  | Same, top 5 |
| `mom_1m_tight` | Tightest momentum cluster (current best Calmar) |
| `mom_3m_*`     | 3-month lookback variants |
| `mom_6m_*`     | 6-month lookback variants |
| `mom_12m_*`    | 12-month lookback variants |

Output fields per strategy: `calmar` (return-to-max-drawdown), `annret`
(annualized return), `sharpe` (annualized return / annualized vol),
`maxdd` (max drawdown). Today's best is `mom_1m_tight` with Calmar ~2.3,
annual return ~23%, Sharpe ~2.0, max DD ~10%.

### Layer 2 — Per-ticker track record (forward-tracked outcomes)

**Script:** `cron/track_record_builder.sh` (calls into `output/aggregated_signals.json`)
**Output:** `output/track_record/dayN.json` (auto-incrementing N), plus
`output/track_record_latest.json` and `output/track_record/baseline_2026-05-10.json`
**Schedule:** daily at 16:30 MDT via cron

This layer captures per-ticker entry prices and outcome %. It is a
forward-looking measurement against signals that were issued at a snapshot
in time.

### Layer 3 — The dashboard's "BACKTEST RESULTS" headline row

⚠️ **This is currently a fixed reference display, not a live computation.**

The card in the dashboard reading `LUNR +14.68% | ASTS +10.44% | DELL +4.01%`
is **hardcoded HTML** in `rebuild_html.py`. It was added at project launch
as an example reference. It is **not** the live output of either Layer 1
or Layer 2.

The closest available historical comparison file is
`output/track_record_verified.json` (dated 2026-03-24), which shows
different per-ticker numbers (some negative) than the dashboard card.
**The provenance of the dashboard's specific +14.68/+10.44/+4.01 figures is
not currently traceable to a specific recorded backtest in this repo.**

This page exists because that lack of provenance is itself something a
prospective user deserves to know.

## What the live computation actually does

### Universe construction (`yuclaw/universe.py`)

- `DAILY_CORE` — 39 hand-picked single-name equities across semis, AI infra,
  space, nuclear, biotech, fintech sectors
- `FACTOR_UNIVERSE` — DAILY_CORE plus a small set of non-leveraged ETFs
  (SPY, QQQ, GLD, SLV, TLT, XBI, ARKK, IEF)
- `LEVERAGED_ETFS` — explicit blocklist of 16 2x/3x and inverse products
  (SOXL, SOXS, TQQQ, SQQQ, etc.). Filtered out at universe construction so
  they cannot distort momentum-weighted scoring.

### Backtest assumptions

| Assumption | Setting |
|---|---|
| Universe | 39 single-name equities + 8 non-leveraged ETFs |
| Lookback windows | 1-mo / 3-mo / 6-mo / 12-mo |
| Rebalancing | Monthly at start-of-period |
| Position sizing | Equal-weight within each strategy's top-N |
| Cash | Excess held in cash; no short positions |
| Transaction costs | **0 bps** — slippage and commissions are NOT modeled |
| Borrow costs | n/a (long-only) |
| Taxes | not modeled |
| Look-ahead bias | Strategy uses prior-period closes only |
| Survivorship bias | Universe is hand-picked today and applied retroactively — **survivorship bias is present** |
| Data source | Daily OHLCV from yfinance |

### Signal aggregator (v2.4, see commit `928bdae`)

- Combines per-ticker factor score, momentum, ticker-Calmar, RSI health,
  universe-wide best Calmar, portfolio-level VaR via fixed weighted sum
- Detailed weights and rationale in the v2.3.0 release notes and the
  `signal_aggregator.py` module docstring

### Forward track-record builder (`cron/track_record_builder.sh`)

Reads the most-recent `aggregated_signals.json`, fetches current prices via
yfinance, records each ticker's outcome % = (current − entry) / entry,
sign-flipped for SELL signals. Stores per-day snapshots.

**Known issue (as of 2026-05-14):** because the track-record builder reads
the SAME `aggregated_signals.json` that `refresh_dashboard.sh` keeps refreshing
with the day's prices, `entry_price` and `current_price` tend to be identical
and `outcome_pct` reports 0.0. The forward-measurement design needs a separate
entry-price snapshot persisted at signal time. Fix is planned for Day 5 scope.

## Reproducibility

If you want to verify the strategy backtest output yourself:

```bash
git clone https://github.com/YuClawLab/yuclaw-brain
cd yuclaw-brain
pip install -e .
python3 engines/run_backtest.py
cat output/backtest_all.json
```

The numbers you see will use today's yfinance data — they will not exactly
match any specific historical snapshot, by design.

## Limitations to keep in mind

1. **Zero transaction costs.** Real trading incurs slippage and commissions.
   For active strategies that rebalance frequently, costs typically reduce
   annualized return by 50-200 basis points.
2. **Survivorship bias.** The DAILY_CORE universe was chosen in 2026 — names
   that performed poorly enough to drop from coverage aren't included.
3. **No regime conditioning beyond a CRISIS/RISK_OFF/RISK_ON flag.** Real
   strategies might use position sizing tied to volatility regime, etc.
4. **No transaction-level audit.** Each backtest is end-of-day; intraday
   execution effects (gaps, halts) are not simulated.
5. **The "ZKP Verified — Ethereum Sepolia" caption** under the BACKTEST
   RESULTS card refers to cryptographic timestamping of signal hashes on
   the Sepolia testnet via `yuclaw-trust`. It does NOT verify backtest
   accuracy. ZKP only proves "this signal hash existed at this block height" —
   it does not validate the underlying analytical claim.

## Open issues this page is intended to surface

1. Replace the hardcoded dashboard row with live computed figures from
   `track_record_verified.json` or `output/track_record/dayN.json`.
2. Fix the track_record_builder so entry_price is captured once at signal
   time, not re-read on every refresh.
3. Add transaction-cost modeling to `engines/run_backtest.py`.
4. Document each ZKP proof's exact claim more clearly on the dashboard
   (today the "Verified" label can be read as endorsement of accuracy).

These are tracked in the project's open work; the relevant code lives in
`rebuild_html.py` (dashboard rendering), `cron/track_record_builder.sh`
(builder), and `engines/run_backtest.py` (backtest engine).

---

*Last updated: 2026-05-14. If you find a discrepancy between this page and
the live code, open an issue at https://github.com/YuClawLab/yuclaw-brain.*
