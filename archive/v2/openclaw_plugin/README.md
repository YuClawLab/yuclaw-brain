# YUCLAW Financial Intelligence Plugin for OpenClaw

Open-source quant-research surface inside OpenClaw — local LLM inference,
hash-anchored audit trail on Ethereum Sepolia, Alpaca paper trading.

**Research and education only — not financial advice.**

## What this gives OpenClaw users

- `/yuclaw regime` — Macro regime classification (CRISIS / RISK_OFF / RISK_ON)
- `/yuclaw signals` — Factor-scored top buy/sell signals (39-ticker universe)
- `/yuclaw brief` — Latest local-LLM synthesis (Llama 3.1 70B via Ollama)
- `/yuclaw risk` — Portfolio risk metrics (VaR, CVaR, Kelly)
- `/yuclaw verify <TICKER>` — Look up signal hash + Sepolia anchor when present
- `/yuclaw paper` — Alpaca paper-trading bridge with 7 safety nets

## Architecture summary

| Component | Implementation |
|---|---|
| Local LLM | Llama 3.1 70B (Q4_K_M) via Ollama on DGX Spark GB10, exposed as the `nemotron-3-super-local` tag with a financial-analyst system prompt |
| Strategy backtest | `engines/run_backtest.py` — historical Calmar metric in `output/backtest_all.json` with documented limitations (no transaction costs, no slippage, no partial fills) |
| Audit anchoring | SHA-256 hash chain; selected hashes anchored on Ethereum Sepolia testnet (not a Groth16 zk-SNARK proof — see yuclaw-trust for honest framing) |
| Risk engine | VaR / CVaR / Kelly via historical simulation |
| Forward track record | `cron/track_record_builder.sh` writes a daily entry to `output/track_record/dayN.json` |

## Install

```bash
openclaw plugins install yuclaw-financial
```

## Dashboard

[yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain)

## Methodology

See [`docs/methodology/backtest.md`](https://github.com/YuClawLab/yuclaw-brain/blob/main/docs/methodology/backtest.md)
in the main yuclaw-brain repo for what the BACKTEST RESULTS panel does and
does not represent.
