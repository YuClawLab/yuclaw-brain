# YUCLAW — Open Financial Intelligence Platform

The open-source financial intelligence OS. Real backtests. ZKP audit. Local AI.

## Install in one command
```bash
pip install yuclaw
yuclaw start
```

## What YUCLAW gives you

- **Real signals** — factor-scored buy/sell for 167+ tickers
- **Real backtests** — Calmar 3.055 from 15 years of actual prices
- **ZKP audit trail** — every decision on Ethereum blockchain
- **Local AI** — Nemotron 120B, zero cloud dependency
- **Market regime** — CRISIS/RISK_OFF/RISK_ON detection
- **30-day track record** — verifiable signal performance

## Quick start
```bash
pip install yuclaw
yuclaw start          # Start all engines
yuclaw signals        # Show current signals
yuclaw regime         # Show market regime
yuclaw brief          # Show institutional brief
yuclaw track          # Show track record
yuclaw dashboard      # Open live dashboard
```

## How it works
```
Market Data -> Factor Library -> Signal Aggregator
     |              |                |
SEC XBRL    Macro Regime      Risk Engine
     |              |                |
Evidence Graph -> Nemotron 120B -> ZKP Proof
     |
Institutional Brief -> Dashboard -> Track Record
```

## Community

- GitHub: https://github.com/YuClawLab
- Dashboard: https://yuclawlab.github.io/yuclaw-brain
- Paper: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418

MIT License — free for everyone.
