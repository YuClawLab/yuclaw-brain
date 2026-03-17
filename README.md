# YUCLAW ATROS — Autonomous Trading & Research Operating System

**AI-powered financial intelligence platform running locally on NVIDIA DGX Spark.**

Nemotron 3 Super (120B parameters) runs on-device — zero API costs, zero data leakage.

## Modules

| Module | Description |
|--------|-------------|
| **Research Engine** | Deep-dive equity analysis with evidence-anchored bull/base/bear cases |
| **Earnings War Room** | Real-time earnings analysis — beat/miss detection, margin trends, management tone |
| **Adversarial Validation** | Red Team stress-tests any strategy against 13 crisis scenarios |
| **Scenario Shock Engine** | Model macro shocks — transmission chains, sector rotation, time horizons |
| **Factor Lab** | Design, backtest, and stress-test quantitative factors |
| **Portfolio Sentinel** | Continuous watchlist monitoring with thesis drift detection |
| **Audit Vault** | Tamper-proof audit trail with cryptographic receipts |

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  YUCLAW CLI                      │
├─────────────────────────────────────────────────┤
│  Research │ Earnings │ Validate │ Shock │ Factor │
├─────────────────────────────────────────────────┤
│              Evidence Graph (DAG)                │
│           Portfolio Memory (SQLite)              │
│            Audit Ledger (SHA-256)                │
├─────────────────────────────────────────────────┤
│         Router → Nemotron 3 Super (local)        │
│              NVIDIA DGX Spark GB10               │
└─────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Prerequisites: NVIDIA DGX Spark with Nemotron 3 Super running on port 8001
pip install -r requirements.txt

# Research
python yuclaw_cli.py research AAPL "investment thesis and margin trends"

# Adversarial validation
python yuclaw_cli.py validate "Buy momentum ETFs, monthly rebalance, 5% stop-loss"

# Earnings analysis
python yuclaw_cli.py earnings NVDA

# Macro shock scenario
python yuclaw_cli.py shock "Fed raises rates 75bps"

# Factor lab
python yuclaw_cli.py factor "best momentum factor for US large-cap ETFs"

# Portfolio watchlist
python yuclaw_cli.py watchlist add AAPL "services margin expansion"
python yuclaw_cli.py scan

# Audit trail
python yuclaw_cli.py audit
```

## Hardware

- **NVIDIA DGX Spark** — GB10 Grace Blackwell, 128 GB unified memory
- **Model**: Nemotron 3 Super 120B-A12B (NVFP4 or via Ollama)
- **Mode**: Fully local — $0/token, all data stays on-device

## Output

All analyses export to Excel files in `output/` with full evidence anchoring and audit receipts.

## License

Proprietary — YuClawLab
