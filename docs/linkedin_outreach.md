# Outreach Templates

Short templates for sharing YUCLAW with people who might find it useful.
YUCLAW is free, MIT licensed, research-only — these are not paid-pilot
recruitment pitches.

---

## Template 1 — Quant student or self-directed researcher

Subject: YUCLAW — open-source signal-research stack

Hi [Name],

I'm working on YUCLAW — an open-source signal-research stack that runs
locally on NVIDIA DGX Spark and broadcasts a daily digest to a public
Telegram channel.

It's free under MIT and intentionally research-focused: a 39-ticker
universe, hourly oil intelligence, a local LLM (Llama 3.1 70B via
Ollama) that scores news and writes the daily brief, hash-anchored
signal-decision audit on Ethereum Sepolia testnet, and an Alpaca paper-
trading bridge with seven layered safety nets. No live trading is wired.

If you'd find it useful for your own quant work or coursework, the
dashboard and signal channel are public:

- Live dashboard: yuclawlab.github.io/yuclaw-brain
- Signal channel: t.me/yuclaw_signals
- Install: `pip install yuclaw`
- Methodology + limitations: docs/methodology/backtest.md
- Related preprint: papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418

The methodology page is the most important link — it documents what the
backtests do and do not represent before you draw inferences from any
single Calmar or accuracy number.

If you spot something broken or have an idea, GitHub issues and PRs are
welcome.

---

## Template 2 — Engineer interested in the stack

Subject: open-source local-LLM financial research stack

Hi [Name],

I'd be curious for your read on YUCLAW. It's an open-source signal-
research stack with these pieces:

- Local LLM inference (Llama 3.1 70B via Ollama on DGX Spark)
- 6-component signal aggregator over a 39-ticker universe
- Strategy backtest engine, forward track record, risk metrics
- Hash-anchored audit log on Ethereum Sepolia testnet
- Alpaca paper-trading bridge with 7 safety nets
- Dashboard refreshes every 30 min from cron
- Telegram broadcast bot (rate-limited, idempotent)

Source: github.com/YuClawLab/yuclaw-brain
Dashboard: yuclawlab.github.io/yuclaw-brain

The repo also publishes design specs for two adjacent components:
yuclaw-matrix (CRT-based concurrent scheduler with an arXiv-style paper)
and yuclaw-edge (FIX 4.4 client in C++). Neither is currently in the
production signal flow.

MIT licensed, research and education only. Not financial advice.

---

## Template 3 — Generic share

YUCLAW is an open-source signal-research stack with a local LLM, hash-
anchored audit log, and a public dashboard. 39-ticker universe, free
under MIT, research only — not financial advice. Built on NVIDIA DGX
Spark GB10.

📊 yuclawlab.github.io/yuclaw-brain
📨 t.me/yuclaw_signals
📦 pip install yuclaw

---

⚠️ Research and educational software. Not financial advice. AI-generated
signals may contain errors. Past performance does not predict future
returns. MIT Licensed.
