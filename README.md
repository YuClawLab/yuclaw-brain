<div align="center">

# YUCLAW

**Open-Source Evidence-First Financial Research Platform**

![License MIT](https://img.shields.io/badge/License-MIT-green)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyPI yuclaw 5.0.0](https://img.shields.io/badge/PyPI-yuclaw%205.0.0-orange)
![Hardware DGX Spark GB10](https://img.shields.io/badge/Hardware-DGX%20Spark%20GB10-76B900)
![Ledger git-anchored](https://img.shields.io/badge/Ledger-git--anchored-blue)

Composite research signals tied to SEC filings, time-machine replay across a 90-day
evidence window, and a public git-anchored Verified Research Ledger for tamper evidence.

**Research and education only — not investment advice.**
Signal labels are research classifications, not buy/sell recommendations.

[Live Dashboard](https://yuclawlab.github.io/yuclaw-brain) ·
[Validation Lab](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html) ·
[Quickstart](#quick-start) ·
[Methodology](docs/methodology/backfill.md) ·
[**⚠️ Disclaimer**](#-disclaimer) ·
[PyPI](https://pypi.org/project/yuclaw)

</div>

---

## What YUCLAW does

Most financial AI tells you *what* it thinks. YUCLAW shows you *why* — and lets anyone
check the receipt. Every signal traces back to a verifiable SEC filing or a deterministic
supply-chain cascade, every daily snapshot is content-hashed into a public ledger, and any
signal can be recomputed as of a past date with point-in-time filtering. No opaque
"the model said so."

---

## Quick start

```bash
pip install yuclaw
yuclaw why NVDA
```

```text
NVDA composite score: +0.299  (signal label: NEUTRAL)

Components (score × weight × confidence):
  C1 Momentum        +0.46   (weight 0.12)
  C2 Volume          +0.00   (weight 0.08)
  C3 Sector          -0.15   (weight 0.12)
  C4 Macro           +0.60   (weight 0.15)
  C5 Oil/Rates/FX    -0.47   (weight 0.05)
  C6 Event Impact    +0.16   (weight 0.18)
  C7 Peer Corr       +0.95   (weight 0.10)
  C8 Cascade         +0.00   (weight 0.12)
  C9 Model Trust     +0.00   (weight 0.08)

Top contributing events (last 7 days):
  ↑  +0.02  2026-05-14  M_AND_A_CLOSE (d1 cascade)
              CASCADE d1 via HPE→NVDA (supply, w=0.15) from HPE: H3C divestiture
              source: https://www.sec.gov/Archives/edgar/data/1645590/...

Compliance: Research only. Not financial advice. Not a registered investment advisor.
```

### Command surface

```bash
yuclaw why TICKER                  # Composite signal + ranked evidence w/ SEC source URLs
yuclaw replay TICKER --date DATE   # Point-in-time signal at end of date
yuclaw validation                  # In-sample event validation + forward tracking ledger
yuclaw brief                       # Personalized digest (uses ~/.yuclaw/profile.json)
yuclaw watch add TICKER            # Manage local watchlist
yuclaw verify TICKER --date DATE   # Verified Research Ledger integrity check
yuclaw profile show                # Local preferences
```

**Public signal vocabulary:** `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`,
`WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`.
There is no `SELL` or `SHORT` label — these are research classifications, not trade directions.

---

## How it works

```
SEC EDGAR (Form 4 / 8-K / 10-Q / 10-K / 6-K)
        │
        ▼
Local Llama 3.1 70B (Ollama)  +  SourceLock Guard   ← every extraction validated against source text
        │
        ▼
events table  (the evidence layer)
        │
        ▼
9-component composite  (C1..C9 — C6 event impact carries the highest single weight, 0.18)
        │
        ▼
signal_snapshots  (content-hashed)
        │
        ├──▶  Verified Research Ledger  (git-anchored, public)
        ├──▶  Forward Tracking Ledger   (outcomes vs SPY at 1 / 5 / 20 days)
        ├──▶  Live landing + Validation Lab pages
        └──▶  SDK / REST / MCP server
```

---

## Core capabilities

**Evidence-first composite signals.** The 9-component composite — momentum, volume,
sector velocity, macro regime, oil/rates/FX, event impact, peer correlation, supply-chain
cascade, model trust — is confidence-weighted. C6 event impact carries the highest single
weight (0.18), by design: evidence is meant to correct price-only signals, not echo them.

**SEC EDGAR ingestion + SourceLock Guard.** Form 4 / 8-K / 10-Q / 10-K / 6-K filings are
ingested via local Llama 3.1 70B. A deterministic SourceLock Guard validates every LLM
extraction against the source text before any signal sees it.

**Time-machine replay.** Any signal can be recomputed as of a past date with point-in-time
filtering (`available_as_of <= as_of`). Leak-audited and reproducible via the `replay` CLI,
the REST `/replay` endpoint, or the MCP `yuclaw_replay` tool.

**In-Sample Event Validation + Forward Tracking Ledger.** Two clearly separated panels:
in-sample is replay-reconstructed (~1,000 snapshots over a 90-day window); forward is
live-emitted from launch onward. Hit rates are always reported alongside their *n* — never
a headline percentage alone.

**Verified Research Ledger.** Each day's signal hashes are committed to a public git repo
(`yuclaw-trust`). Run `yuclaw verify TICKER --date DATE` to independently confirm a signal
hasn't been edited since publication. This verifies record integrity and timing — not
investment merit.

**Multi-surface access.** Python SDK (`pip install yuclaw`), REST API, FastMCP stdio server
(7 tools), and CLI.

**Local LLM inference.** Llama 3.1 70B (Q4_K_M, ~42 GB) via Ollama on NVIDIA DGX Spark GB10.
Zero cloud LLM dependency for extraction. SEC EDGAR is the only external data source for the
evidence layer.

**~80-ticker universe.** Equities + sector ETFs + broad ETFs + macro instruments.

---

## Signal Validation Lab

A Fama–French-style decile-cohort event study of whether YUCLAW's composite score carries
forward information — built from feedback by **Prof. Deng Shijie (Georgia Tech)**.

It is research cohort analysis, not portfolio management: cohorts are grouped by score decile
or signal label (never by trade direction), tracked as equal-weighted research cohorts, and
only derived statistics (returns, spreads, drawdowns) are shown — never raw prices. Two panels
are kept strictly separate: a look-ahead-free **Forward (OOS)** panel and an **In-Sample Replay**
panel (which carries an explicit parametric look-ahead disclosure). The forward window is still
early and is labelled *"not yet statistically meaningful."*

🔬 **Live:** [Signal Validation Lab](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html)
· **Methodology:** [docs/methodology/validation_lab.md](docs/methodology/validation_lab.md)

*Hypothetical research illustration — not investment advice, not performance advertising.*

---

## v5 — ClawFactory (in development)

v5 "ClawFactory" is an eleven-layer evidence-extraction architecture in development.
**Layer 0** (the durable, multi-node evidence job queue) is complete and public on branch
[`v5-layer0-foundation`](https://github.com/YuClawLab/yuclaw-brain/tree/v5-layer0-foundation) —
proven on a 281-filing real-data backfill (281/281 succeeded, 0 dead-letter). Target: **July 1**.
No v5 feature beyond Layer 0 is built yet. Full roadmap (all eleven layers + the three locked
values) is in the [ClawFactory announcement](docs/clawfactory_announcement.md).

---

## Methodology & honest limitations

Full methodology lives in [docs/methodology/backfill.md](docs/methodology/backfill.md).
The honest limits, stated up front:

- **In-sample is replay reconstruction, not a live backtest.** The In-Sample Event Validation
  panel was materialized after the fact by the replay engine — not emitted live.

- **Fresh-data pipeline (v4.2).** C1 momentum, C3 sector velocity, C5 (sector input), and C7
  peer correlation read live `price_history` (a daily yfinance feed restored 2026-06-10), so the
  price-derived components are current rather than reading a frozen cache. **C4 macro regime is
  temporarily frozen as of 2026-05-18 with a staleness disclosure**, pending macro-engine
  restoration — its only upstream is the retired v2.3 macro engine, and it cannot be price-derived
  without changing the component's math. C6 event impact, C8 cascade, and C9 model trust remain
  point-in-time exact. On historical replays the price-derived components still carry point-in-time
  caveats.

- **Forward Tracking Ledger starts at n=0.** Launch is Day 0. 1-day outcomes mature next trading
  day; 5-day a week later; 20-day a month later. The forward panel looks sparse for the first few
  weeks — correct, not a bug.

- **Extreme labels are rare by construction.** `STRONG_BULLISH` and `BEARISH_WATCH` require broad
  component agreement plus at least one material non-insider event. Day-0 OOS 99th percentile sits
  at +0.531, just below the +0.55 `STRONG_BULLISH` floor. See backfill.md §8 for the full
  reachability analysis.

- **No table of headline % returns appears in this README.** Hit rates in both panels are reported
  alongside their *n*; small-*n* panels are tagged "preliminary." See the
  [live validation page](https://yuclawlab.github.io/yuclaw-brain/validation.html) for current numbers.

---

## System architecture

```
v3/
  signal/      9-component composite (C1..C9), supply-chain graph, cascade engine
  sources/     SEC EDGAR poller + backfill + Form 4 deterministic parser
  extract/     LLM extraction + SourceLock Guard
  replay/      Time-machine replay engine
  track/       price_history + outcome_updater + In-Sample Validation panels
  proof/       Verified Research Ledger writer + verifier
  radar/       Change detector + Telegram / Email / Slack adapters
  api/         FastAPI REST server
  mcp/         FastMCP stdio server (7 tools)
  cli/         why / replay / validation / brief / watch / verify / profile
sdk/           yuclaw — public SDK (pip install yuclaw)
docs/methodology/backfill.md   Methodology + limitations + leak audit
```

---

## Operations — what's actually scheduled

The live cron table. Frequencies are read from `crontab -l`, not aspirational.

| Engine | Frequency | What it does |
|---|---|---|
| Daily pipeline | weekdays 17:00 MDT | healthcheck → snapshot_writer → outcome_updater → radar → proof.ledger → refresh_v3_pages — single chained pipeline, `&&` short-circuits on failure |
| Telegram broadcast | daily 07:35 MDT | daily signal digest to `@yuclaw_signals` |
| Ollama check | every 30 min | sanity ping to local Ollama |
| Health monitor | every 30 min | `/tmp/yuclaw_health.log` |
| Sentiment archive | every 4 hours | `output/sentiment/*.json` (research-side, orthogonal to the signal pipeline) |
| Oil intelligence | hourly | `output/oil/YYYY-MM-DD_brief.json` (research-side) |
| Oil brief | nightly 23:00 MDT | LLM oil synthesis (research-side) |
| Swarm debate | nightly 23:00 MDT | Bull / Bear / Oracle LLM debate (research-side) |
| PyTorch check | daily 22:00 MDT | dependency sanity |

The daily signal pipeline runs from the canonical `main` checkout. In addition to the scheduled
07:35 digest, `v3.radar.run` posts to `@yuclaw_signals` when material changes are detected.

---

## Hardware

- **GPU:** NVIDIA Grace Blackwell GB10 (128 GB unified memory)
- **LLM:** Llama 3.1 70B (Q4_K_M, ~42 GB on GPU, 80 layers) served via Ollama, with a
  financial-analyst system prompt. This is the active production path — the only model used for
  extraction.
- **Measured generation speed:** ~2.2–2.7 tok/s on 50-token completions (rendered live in the
  dashboard's TOK/S stat card; `output/inference_stats.json` is rewritten by every nightly cron run).
- **Signal cycle:** ~39 s end-to-end for the score-regeneration pipeline.

---

## OpenClaw integration

```bash
# As an OpenClaw skill
bash <(curl -s https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/yuclaw/openclaw/install.sh)

# Or as an MCP server
python3 yuclaw/openclaw/mcp_server.py     # listens on port 8002
```

---

## Community

| | |
|---|---|
| **Dashboard** | [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain) |
| **Twitter** | [@Vincenzhang2026](https://twitter.com/Vincenzhang2026) |
| **GitHub** | [YuClawLab](https://github.com/YuClawLab) |
| **PyPI** | [pypi.org/project/yuclaw](https://pypi.org/project/yuclaw) |
| **Methodology** | [docs/methodology/backfill.md](docs/methodology/backfill.md) |

---

## ⚠️ Disclaimer

YUCLAW is open-source research and educational software. It is **NOT financial advice,
investment advice, or a recommendation to buy, sell, or hold any security.** All signals,
scores, and analyses are generated by automated AI models and may contain errors.

Past performance does not guarantee future results. Trading involves substantial risk of loss.
You are solely responsible for your own investment decisions. Consult a licensed financial
advisor before making any investment.

YuClawLab, its contributors, and affiliates accept no liability for any losses arising from use
of this software.

For educational and research purposes only. See
[docs/methodology/backfill.md](docs/methodology/backfill.md) and
[DISCLAIMER.md](DISCLAIMER.md) for the long-form versions.

---

<div align="center">

**Released under the MIT License — free for everyone.**

Built on NVIDIA DGX Spark GB10 · Llama 3.1 70B via Ollama · Local inference · Git-anchored Verified Research Ledger

`pip install yuclaw`

</div>
