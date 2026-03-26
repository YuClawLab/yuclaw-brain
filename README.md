# YUCLAW — Open Financial Intelligence Platform

[![Stars](https://img.shields.io/github/stars/YuClawLab/yuclaw-brain?style=flat&color=ffd700)](https://github.com/YuClawLab/yuclaw-brain)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)
[![Model](https://img.shields.io/badge/model-Nemotron%20120B-brightgreen)](https://nvidia.com)
[![Hardware](https://img.shields.io/badge/hardware-DGX%20Spark%20GB10-76b900)](https://nvidia.com)
[![ZKP](https://img.shields.io/badge/ZKP-Ethereum%20Sepolia-purple)](https://sepolia.etherscan.io)
[![SSRN](https://img.shields.io/badge/paper-SSRN%206461418-red)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418)

> The open-source financial intelligence OS. Real backtests. ZKP audit trail. Local 120B AI. Like OpenClaw but built for finance.

## Install in one command
```bash
pip install yuclaw
yuclaw start
```

## Quick commands
```bash
yuclaw signals    # Show current buy/sell signals
yuclaw regime     # Show market regime (CRISIS/RISK_OFF/RISK_ON)
yuclaw brief      # Nemotron 120B institutional brief
yuclaw track      # 30-day verifiable track record
yuclaw zkp        # ZKP cryptographic proofs on-chain
yuclaw dashboard  # Open live dashboard
```

## Live Dashboard

**[yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain)**

Updates every 30 minutes. Real signals. Real risk. Real model.

## Why YUCLAW

| Feature | OpenClaw | Claude | YUCLAW |
|---|---|---|---|
| Real backtests | No | No | Calmar 3.055 |
| ZKP audit trail | No | No | On-chain |
| Real VaR/Kelly | No | No | Historical sim |
| Local 120B model | No | No | Nemotron DGX |
| Verified track record | No | No | 30-day building |
| Adversarial Red Team | No | No | Kills bad strategies |
| Academic paper | No | No | SSRN #6461418 |

## Track Record (Day 3 of 30)

| Signal | Result | Change | ZKP Block |
|---|---|---|---|
| LUNR STRONG_BUY | CORRECT | +14.68% | 10515603 |
| ASTS STRONG_BUY | CORRECT | +10.44% | 10515603 |
| MRVL STRONG_BUY | CORRECT | +6.59% | 10515603 |
| DELL STRONG_BUY | CORRECT | +4.01% | 10515603 |

**Day 3 accuracy: 60% — every signal on Ethereum blockchain**

## How it works

```
Market Data (167+ tickers)
    |
Factor Library (RSI, MACD, Bollinger, Momentum)
    |
Signal Aggregator -> Adversarial Red Team
    |
Nemotron 3 Super 120B (local, 18.9 tok/s)
    |
ZKP Proof -> Ethereum Sepolia Blockchain
    |
Institutional Brief -> Dashboard -> Track Record
```

## What runs 24/7 on DGX Spark GB10

- **Signal loop** — 167 tickers every 30 min
- **Factor engine** — RSI/MACD/Bollinger every 30 min
- **Risk engine** — VaR/CVaR/Kelly every 1 hr
- **Macro regime** — CRISIS detection every 1 hr
- **Nemotron brief** — Institutional analysis every 15 min
- **ZKP vault** — Cryptographic proofs every 1 hr
- **FIX gateway** — Paper trading every 30 min
- **Track record** — Verified performance every 1 hr

## Architecture

```
yuclaw/
  modules/    Signal aggregator, macro regime
  factors/    Factor library (RSI, MACD, Bollinger)
  risk/       VaR, CVaR, Kelly criterion
  finclaw/    Institutional brief, competitive intel
  trust/      ZKP vault, on-chain proofs
  edge/       FIX gateway, execution levels 0-4
  memory/     Portfolio memory, track record
  brain/      Evidence graph, financial NER
  plugins/    Plugin system (like ClawHub)
  api/        REST API for OpenClaw integration
```

## Plugin System
```python
from yuclaw.plugins import register

@register('my_strategy', 'My custom strategy', 'quant')
class MyStrategy:
    def run(self):
        # Your financial intelligence here
        pass
```

## Academic Paper

**CRT Lock-Free Concurrent Scheduler for Financial Systems**
SSRN Abstract #6461418 | DGX Spark GB10 | 1.37ms latency

[Read on SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418)

## Community

- Dashboard: [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain)
- Twitter: [@Vincenzhang2026](https://twitter.com/Vincenzhang2026)
- Paper: [SSRN #6461418](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6461418)
- GitHub: [YuClawLab](https://github.com/YuClawLab)

## Contributing

YUCLAW improves every day — like OpenClaw but for finance.
PRs welcome. Build plugins. Add data sources. Improve factors.

## License

MIT — free for everyone.

---

*Built on NVIDIA DGX Spark GB10 | Nemotron 3 Super 120B | Zero cloud dependency*
