# YUCLAW — Getting Started

A five-minute introduction. Install, run a few commands, subscribe to the
signal channel, optionally point it at a paper-trading account. **For
research and education only — not financial advice.**

---

## Try it in 3 minutes

The fastest way to understand YUCLAW v4 — two commands from nothing:

```bash
pip install yuclaw
yuclaw demo
```

`yuclaw demo` is a guided 3-minute journey on a real, frozen signal: the structured
signal and its drivers, the full research memo with every claim linked to an SEC filing
(`accession_number` + `ledger_hash`), a deterministic point-in-time replay, and an
independent verification against the public, git-anchored Verified Research Ledger.

Then explore the same signal yourself:

```bash
yuclaw why   AMD --as-of 2026-05-20   # structured signal (research classification, never buy/sell)
yuclaw why   AMD --as-of 2026-05-20 --include-score   # opt in to the raw composite score
yuclaw memo  AMD --as-of 2026-05-20   # full research memo
yuclaw verify AMD --date 2026-05-20   # re-verify the integrity hash against the public ledger
```

Every response carries a required compliance block and explicit limitations; a missing
ticker returns a `status: "no_data"` envelope, never a fabricated signal.

---

## What YUCLAW is

- An **open-source AI signal generator** for a 39-ticker universe.
- A **local LLM** (Llama 3.1 70B via Ollama on NVIDIA DGX Spark GB10)
  scores news and synthesizes daily briefs without sending anything to a
  cloud model provider.
- A **tamper-evident audit trail** — selected signal-decision hashes are
  anchored on Ethereum Sepolia testnet so anyone can confirm a decision
  existed at a given block height.
- A **paper-trading bridge** to Alpaca with seven layered safety nets.
- A **live dashboard** that refreshes every 30 minutes from cron.

## What YUCLAW is not

- It is **not a trading robot**. It computes signals; you decide what to do.
- It is **not financial advice**. Past performance does not predict future
  returns and AI signals can be wrong.
- It does **not** make zero-knowledge proofs of strategy correctness. The
  hash anchor proves a payload existed on a given block — nothing more.
- It does **not** trade real money by default. Paper-trading via Alpaca's
  testnet is the only broker path; live trading is intentionally not wired.

---

## 5-minute quickstart

```bash
pip install yuclaw
yuclaw today
```

Sample output:

```
YUCLAW Daily Brief — 2026-05-16

MARKET: RISK_ON (85% confidence)
   Overweight equities
   Reduce bonds/gold

TOP BUY SIGNALS:
   INTC   STRONG_BUY   score:+0.676 price:$115.93
   DELL   STRONG_BUY   score:+0.657 price:$247.89
   AMD    STRONG_BUY   score:+0.638 price:$449.70

PORTFOLIO ACTION:
   Open-source signal output. Consult a licensed advisor before trading.
```

The three commands most people start with:

```bash
yuclaw today      # Today's market regime + top signals + portfolio note
yuclaw signals    # Raw top-15 signals with scores and prices
yuclaw regime     # Just the macro regime (CRISIS / RISK_OFF / RISK_ON)
```

Browse the full command surface with:

```bash
yuclaw --help
```

A few useful extras:

```bash
yuclaw watchlist            # All current signals with action labels
yuclaw portfolio            # Kelly-weighted allocation for your capital
yuclaw track                # Forward track record (day N from cron)
yuclaw brief                # Latest LLM-written market synthesis
yuclaw ask "explain LUNR"   # Local LLM answers a question with current context
yuclaw verify LUNR          # Look up the on-chain anchor for a ticker's hash
yuclaw sector               # One-day sector rotation snapshot
yuclaw news                 # Sentiment-scored news for top tickers
yuclaw earnings             # This week's earnings calendar
yuclaw learn kelly          # Plain-English explainer for a finance concept
```

---

## Signal channel — Telegram subscribe

A best-effort broadcast feed mirrors the dashboard.

**Channel**: [t.me/yuclaw_signals](https://t.me/yuclaw_signals)

What subscribers receive:

- **Daily digest** at 09:35 ET on weekdays (US market open + 5 minutes):
  top-5 STRONG_BUY tickers, current macro regime, sector flow snapshot,
  this week's earnings reporters.
- **Alerts** when:
  - A ticker enters the top-10 for the first time (`SIGNAL_NEW`).
  - A signal score moves by more than 0.20 (`SIGNAL_CHANGE`); smaller
    moves are filtered to keep noise out of your phone.
  - The macro regime flips (`REGIME_CHANGE` — RISK_ON ↔ CRISIS, etc.).

The bot is rate-limited to five sends per hour and is idempotent (a
duplicate broadcast for the same payload is detected and skipped). All
broadcasts are appended to a local audit log.

---

## Reading the dashboard

**Live**: [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain)

Top stat cards:

| Card | Meaning |
|---|---|
| Buy Signals | Count of tickers classified BUY or STRONG_BUY this cycle |
| Assets | Total universe size (39 tickers after the leveraged-ETF blocklist) |
| Tok/s | Live-measured local LLM generation speed on the last cron fire |
| Signal cycle | Wall-clock seconds for the score-regeneration pipeline |

Other panels:

- **Oil Intelligence** — WTI / Brent / EIA inventory + the two largest
  US energy equities. Refreshed hourly.
- **Macro Regime** — colored gradient (green = RISK_ON, red = CRISIS).
- **Live Order Flow** — top-15 signals with the green **V** badge marking
  prices that were Finnhub-verified at fetch time.
- **Sector Velocity** — 1-day vs prior close for 14 ETF sectors.
- **LLM Sentiment** — local LLM scoring of recent news headlines.
- **ATROS Alerts** — recent first-sight + score-change + regime-change events.
- **AutoDream Memory** — daily LLM synthesis (1-2 dense sentences).
- **Backtest Results** — placeholder pending live-computed methodology;
  see the methodology page for what is and isn't claimed today.

The green pill at the bottom of the Backtest Results card reads
**Hash-Anchored — Ethereum Sepolia**. Hover (desktop) for the longer
explanation: it confirms a decision payload existed at a given block
height — not a cryptographic proof of strategy correctness.

---

## Paper trading via Alpaca

YUCLAW includes a broker bridge to [Alpaca's paper-trading API](https://alpaca.markets).
No live trading is wired; the broker host is hard-checked against the
paper endpoint at startup.

```bash
export ALPACA_API_KEY=...        # paper account, not live
export ALPACA_SECRET_KEY=...
export ALPACA_BASE_URL=https://paper-api.alpaca.markets

yuclaw paper                     # show account + positions
yuclaw paper BUY MU 20           # market-buy 20 shares — blocked >$10k notional unless --force
yuclaw paper SELL MU 20 --force  # override the notional cap
```

Seven safety nets that run before any order leaves the machine:

1. **Paper-URL guard** — refuses to start if `ALPACA_BASE_URL` is not the
   paper endpoint.
2. **Validation ping** — pings `/v2/account` at init; 401 → halt with
   "regenerate keys".
3. **Market-hours check** — `/v2/clock` confirms market is open; rejects
   off-hours orders unless explicitly forced.
4. **$10k notional cap** — single-order ceiling, override with `--force`.
5. **First-run consent** — interactive prompt records your acknowledgment
   to `~/.yuclaw/paper_consent.json` before any order is allowed.
6. **Audit log** — every order attempt (submitted, rejected, errored) is
   appended to `~/.yuclaw/orders.jsonl`.
7. **Drawdown kill switch** — HALT at -3% intraday, LIQUIDATE at -8%
   against Alpaca's `account.last_equity`.

If you'd rather try the in-process $100K simulator with no broker
integration at all, use `yuclaw trade` instead.

---

## Methodology and limitations

Before you read any single accuracy number, Calmar figure, or top-signal
score: read the methodology page.

[docs/methodology/backtest.md](https://github.com/YuClawLab/yuclaw-brain/blob/main/docs/methodology/backtest.md)

In short:

- Strategy backtest in `output/backtest_all.json` uses historical
  close-to-close returns. It does **not** model transaction costs,
  slippage, bid/ask, or partial fills.
- Forward track record in `output/track_record/dayN.json` captures
  entry-price-at-signal-time and current price. Same caveats.
- The dashboard's "Backtest Results" card is currently a placeholder
  pending the live-computed methodology pass.

---

## Disclaimer

YUCLAW is open-source research and educational software. It is **NOT**
financial advice, investment advice, or a recommendation to buy, sell, or
hold any security. All signals, scores, and analyses are generated by
automated AI models and may contain errors.

Past performance does not guarantee future results. Trading involves
substantial risk of loss. You are solely responsible for your own
investment decisions. Consult a licensed financial advisor before making
any investment.

YuClawLab, its contributors, and affiliates accept no liability for any
losses arising from use of this software.

**For educational and research purposes only. MIT Licensed.**

---

| | |
|:---|:---|
| Dashboard | [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain) |
| Telegram | [t.me/yuclaw_signals](https://t.me/yuclaw_signals) |
| PyPI | [pypi.org/project/yuclaw](https://pypi.org/project/yuclaw) |
| GitHub | [github.com/YuClawLab](https://github.com/YuClawLab) |
| Methodology | [docs/methodology/backtest.md](https://github.com/YuClawLab/yuclaw-brain/blob/main/docs/methodology/backtest.md) |
| Full disclaimer | [DISCLAIMER.md](https://github.com/YuClawLab/yuclaw-brain/blob/main/DISCLAIMER.md) |
