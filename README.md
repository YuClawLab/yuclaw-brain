```
 __   __  __  __  _______  __      ___       __  __  __
|  | |  ||  ||  ||   ____||  |    /   \     |  ||  ||  |
|  |_|  ||  ||  ||  |__   |  |   /  ^  \    |  ||  ||  |
|_____  ||  ||  ||  |     |  |  /  /_\  \   |  ||  ||  |
 __   | ||  `--'||  `----.|  | /  _____  \  |  `--'||  |
|  |  | | \____/ |_______||__|/__/     \__\ |______||__|
|__|  |_|
   A T R O S — Adversarial Trading & Research Operating System
```

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Nemotron](https://img.shields.io/badge/LLM-Nemotron%20120B-green.svg)](https://huggingface.co/nvidia)
[![DGX Spark](https://img.shields.io/badge/Hardware-DGX%20Spark%20GB10-76B900.svg)](https://nvidia.com)

**The first adversarial financial intelligence system. Runs locally on DGX Spark at $0/token.**

> Every number from real data. Zero LLM estimation in any quantitative component.

## Live Dashboard

**[FINClaw Dashboard](https://yuclawlab.github.io/yuclaw-brain/)** — real-time market regime, factor signals, strategy backtests, portfolio risk.

## Current Market Regime

**CRISIS (90% confidence)** — detected from live market data.
- Action: Maximum cash, TLT + GLD only, hedge with puts
- Energy OVERWEIGHT (+7.5%), Technology UNDERWEIGHT (-3.5%)

## Real Benchmark Results

### CRT Scheduler ([yuclaw-matrix](https://github.com/YuClawLab/yuclaw-matrix))
| Instruments | Latency | vs Baseline |
|---|---|---|
| 50 | 1.07ms | baseline |
| 1,000 | 1.12ms | +5% |
| 10,000 | 1.37ms | +28% |

### Real Backtests (actual price history, not estimated)
| Strategy | Calmar | Max DD | Annual Return | Sharpe |
|---|---|---|---|---|
| momentum_1m_tight | **2.309** | 9.8% | 22.7% | 1.97 |
| momentum_6m_tight | 1.764 | 12.8% | 22.5% | 1.81 |
| AI infra basket | **6.851** | 16.0% | — | 3.72 |

### Real Financial Data (SEC EDGAR XBRL)
| Company | Revenue | Source |
|---|---|---|
| AAPL | $416B | SEC EDGAR XBRL API |
| MSFT | $282B | SEC EDGAR XBRL API |
| NVDA | $27B | SEC EDGAR XBRL API |

## Architecture

```
YUCLAW ATROS
  yuclaw-brain    — Research, validation, risk, factors, FINClaw product
  yuclaw-matrix   — CRT lock-free scheduler (arXiv paper)
  yuclaw-edge     — C++ FIX 4.4 gateway (ARM64)
  yuclaw-trust    — ZKP compliance circuit (circom)
```

## Running Right Now (7 sessions on DGX Spark)

| Engine | Interval | Output |
|---|---|---|
| Factor scan | 30 min | 49 instruments, 12 real factors |
| Backtest | 45 min | 10 momentum strategies |
| Risk | 60 min | 8 portfolios VaR/CVaR/Kelly |
| Macro regime | 60 min | CRISIS/RISK_OFF/RISK_ON detection |
| Screener | 30 min | Buy/sell signals with RSI, Calmar |
| LLM research | continuous | 40+ tickers per batch |
| FINClaw brief | daily | Morning institutional briefing |

## Quick Start

```bash
git clone https://github.com/YuClawLab/yuclaw-brain
cd yuclaw-brain
pip install -r requirements.txt
python daily.py AAPL NVDA AMD
```

## Links

- [yuclaw-brain](https://github.com/YuClawLab/yuclaw-brain) — Core system
- [yuclaw-matrix](https://github.com/YuClawLab/yuclaw-matrix) — CRT scheduler + [arXiv paper](https://github.com/YuClawLab/yuclaw-matrix/blob/main/paper/submission/main.pdf)
- [yuclaw-edge](https://github.com/YuClawLab/yuclaw-edge) — C++ FIX gateway
- [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) — ZKP audit vault

## License

Proprietary — YuClawLab
