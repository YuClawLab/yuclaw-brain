# YuClawLab

Open-source AI research stack for quantitative finance. Local LLM
inference, hash-anchored signals on Ethereum Sepolia testnet, Alpaca
paper trading. Built on NVIDIA DGX Spark GB10. MIT licensed.

**Research and education only — not financial advice.**

## What we build

| Repo | Status | What it is |
|---|---|---|
| [yuclaw-brain](https://github.com/YuClawLab/yuclaw-brain) | Active | Signal aggregator, dashboard, broker bridge, LLM scoring |
| [yuclaw-matrix](https://github.com/YuClawLab/yuclaw-matrix) | Research preview | CRT-based concurrent scheduler with an arXiv-style paper |
| [yuclaw-edge](https://github.com/YuClawLab/yuclaw-edge) | Reference implementation | FIX 4.4 client in C++ on ARM64 — not currently in production signal flow |
| [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) | Partial implementation | SHA-256 hash-chain audit log + Circom design spec for a future zk-SNARK compliance circuit |

## Live now

- **Dashboard**: [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain) — refreshes every 30 minutes
- **Signal channel**: [t.me/yuclaw_signals](https://t.me/yuclaw_signals) — daily digest at 09:35 ET weekdays, plus alerts on significant signal/regime moves
- **PyPI**: `pip install yuclaw`
- **Methodology**: [docs/methodology/backtest.md](https://github.com/YuClawLab/yuclaw-brain/blob/main/docs/methodology/backtest.md) — what the backtests do and do not represent

## Honest framing

- The local LLM is **Llama 3.1 70B** (Q4_K_M) served via Ollama. It is
  configured locally as the `nemotron-3-super-local` Ollama tag with a
  financial-analyst system prompt. The actual Nemotron 3 Super 120B is
  wired in `yuclaw/core/router.py` as a dormant OpenRouter fallback path.
- The on-chain anchor is a **SHA-256 hash** of selected signal decisions
  on Ethereum Sepolia testnet — not a Groth16 zk-SNARK proof of strategy
  correctness. The Circom compliance circuit in yuclaw-trust is a design
  spec for that future system.
- The strategy backtest does not currently model transaction costs,
  slippage, bid/ask, or partial fills. See the methodology page before
  drawing inferences from any single Calmar or accuracy number.

Running 24/7 on NVIDIA DGX Spark GB10.

---

⚠️ Research and educational software. Not financial advice. AI-generated
signals may contain errors. Past performance does not predict future
returns. MIT Licensed.
