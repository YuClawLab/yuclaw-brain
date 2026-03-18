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
[![Nemotron 3 Super](https://img.shields.io/badge/LLM-Nemotron%203%20Super%20120B-green.svg)](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4)
[![DGX Spark](https://img.shields.io/badge/Hardware-DGX%20Spark%20GB10-76B900.svg)](https://nvidia.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

**The first adversarial financial intelligence system. Runs locally on DGX Spark at $0/token.**

---

## Demo: Real Output from YUCLAW

### Research Engine

```
$ python yuclaw_cli.py research AAPL "investment thesis, margins, moat, risks"

────────────────────────────────────────────────────────────
  RESEARCH — AAPL
────────────────────────────────────────────────────────────
  Status:   Evidence_Extracted
  Evidence: 2 anchors

  BULL CASE:
  AAPL's strong brand and loyal customer base will continue to
  drive revenue growth and maintain its market share.

  BASE CASE:
  AAPL's financial performance is stable, but the company faces
  intense competition in the consumer electronics industry.

  BEAR CASE:
  AAPL's valuation is relatively expensive compared to its peers,
  which may lead to a correction in the stock price.

  Excel saved: output/AAPL_20260317_research.xlsx
```

### Earnings War Room

```
$ python yuclaw_cli.py earnings AAPL

════════════════════════════════════════════════════════════
  EARNINGS WAR ROOM — AAPL
════════════════════════════════════════════════════════════
  BEAT  |  Apple's Q2 revenue and EPS exceed expectations

  Revenue:  Actual $81.8B  |  Consensus $77.4B  |  5.6% surprise  |  YoY 17%
  EPS:      Actual $1.40   |  Consensus $1.23   |  13.8% surprise
  Gross Margin: 47.4%  (Prior Q: 46.3%  |  Prior Y: 44.9%)  [expanding]
  Guidance: $85-90B  |  +$2.3B vs consensus  |  Tone: RAISED

  Management Tone: BULLISH
    "strong demand for iPhone"
    "record revenue in Americas and Europe"
    increased confidence in services segment

  Key Concerns:
    supply chain constraints
    regulatory risks in China

  1-Week View: positive
  Evidence anchors: 3 claims traceable to source
```

### Scenario Shock Engine

```
$ python yuclaw_cli.py shock "Federal Reserve raises rates 75bps unexpectedly"

════════════════════════════════════════════════════════════
  SCENARIO SHOCK ENGINE
  Event: Federal Reserve raises rates 75bps unexpectedly
  Type: MONETARY  |  Probability: MEDIUM
════════════════════════════════════════════════════════════

  TRANSMISSION CHAIN:
  1. Interest Rate Shock -> US Treasury Market, MBS
  2. Yield Curve Steepening -> Corporate Bonds, High-Yield
  3. Credit Spread Widening -> IG Corporates, Emerging Markets

  CASUALTIES:
    Long-Term US Treasury Bonds  [large]
    Mortgage REITs               [medium]

  BENEFICIARIES:
    US Dollar                    [large]
    Short-Term Treasury Bills    [medium]

  ROTATE INTO: Financials, Utilities
  ROTATE OUT:  Real Estate, Consumer Discretionary

  HISTORICAL ANALOGUE:
    1994 — Fed raises 75bps: Bond market sell-off and increased volatility
```

---

## Adversarial Validation: The Red Team

The core differentiator. Before any strategy touches capital, a Red Team module attacks it with 13 crisis scenarios. If the strategy survives, it passes. If not, you see exactly what killed it.

**Real example — a strategy that got killed:**

```
$ python yuclaw_cli.py validate "Buy top-decile 6-month momentum ETFs,
    rebalance monthly, 5% stop-loss"

  ADVERSARIAL VALIDATION RESULT
  ─────────────────────────────────────────

  Strategy:  Buy top-decile 6-month momentum ETFs,
             rebalance monthly, 5% stop-loss
  Verdict:   REJECTED — failed Red Team
  Calmar:    0.002
  Survival:  0% (0/13 scenarios)

  Fatal scenarios:
    Flash crash: market drops 15% in 30 min, spreads widen 10x
    Factor crowding reversal: momentum unwinds as funds de-gross
    Regime break: risk-on to crisis, all correlations spike to 1.0
    Liquidity freeze: no buyers for any risky asset
    Central bank surprise: emergency 100bps rate cut

  AI attack scenarios:
    Flash Crash | Momentum Reversal | High-Interest Rate Shock

  Audit receipt: rcpt_1773797421053532227_a4c1ca84
  Audit hash:    a4c1ca844097ada8...
```

The strategy looked reasonable on paper — top-decile momentum with a stop-loss. But the Red Team found it catastrophically vulnerable to crowding reversals and correlation spikes.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your LLM endpoint (local DGX Spark or any OpenAI-compatible API)
echo 'YUCLAW_SUPER_ENDPOINT=http://localhost:11434/v1' > .env

# 3. Run
python yuclaw_cli.py research AAPL "investment thesis and margin trends"
```

---

## All Commands

```bash
python yuclaw_cli.py research AAPL "your research question"   # Deep equity research
python yuclaw_cli.py earnings AAPL                             # Earnings analysis
python yuclaw_cli.py validate "your strategy description"      # Adversarial stress test
python yuclaw_cli.py shock "any macro event"                   # Scenario modeling
python yuclaw_cli.py macro "any macro event"                   # Macro impact analysis
python yuclaw_cli.py factor "any factor description"           # Factor lab
python yuclaw_cli.py watchlist add AAPL "your thesis"          # Portfolio watchlist
python yuclaw_cli.py watchlist show                            # Show watchlist
python yuclaw_cli.py scan                                      # Sentinel scan
python yuclaw_cli.py audit                                     # Audit trail
```

---

## Comparison

| Feature | YUCLAW ATROS | Traditional Backtest | ChatGPT Finance |
|---------|-------------|---------------------|-----------------|
| Adversarial validation | 13 crisis scenarios | None | None |
| Evidence anchoring | SHA-256 hash chain | None | None |
| Local execution | $0/token, zero data leakage | N/A | Cloud-only, data shared |
| Audit trail | Cryptographic receipts | Manual | None |
| Model size | 120B parameters | N/A | Unknown |
| Earnings analysis | Beat/miss + margin + tone | N/A | Generic summary |
| Macro shock modeling | Transmission chains + rotation | N/A | Narrative only |
| Concurrent monitoring | CRT lock-free (1000+ instruments) | Sequential | N/A |

---

## The 5 Dimensions of YUCLAW Architecture

### 1. Cognition Layer
Deep research with evidence-anchored claims. Every conclusion traces back to a source document, page number, and confidence score.

### 2. Adversarial Layer
GAN-inspired validation — the strategy is the generator, the Red Team is the discriminator. 13 structured crisis scenarios test every strategy before deployment.

### 3. Evidence Layer
Directed acyclic graph (DAG) of evidence nodes. Claims link to source documents. Contradictions are detected. Confidence propagates through the graph.

### 4. Concurrency Layer
[CRT lock-free scheduler](https://github.com/YuClawLab/yuclaw-matrix) — Chinese Remainder Theorem eliminates mutex contention. 15x faster than threading at 1,000 instruments.

### 5. Trust Layer
[ZKP audit vault](https://github.com/YuClawLab/yuclaw-trust) — every decision sealed with cryptographic proofs. Tamper-proof. Regulatory ready.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     YUCLAW CLI                           │
├─────────┬──────────┬──────────┬─────────┬───────────────┤
│Research │ Earnings │ Validate │  Shock  │  Factor Lab   │
├─────────┴──────────┴──────────┴─────────┴───────────────┤
│              Evidence Graph (DAG)                         │
│           Portfolio Memory (SQLite)                       │
│            Audit Ledger (SHA-256)                         │
├──────────────────────────────────────────────────────────┤
│    Router → Nemotron 3 Super (120B) or any LLM           │
├──────────────────────────────────────────────────────────┤
│    CRT Scheduler → Lock-free concurrent monitoring       │
├──────────────────────────────────────────────────────────┤
│              NVIDIA DGX Spark GB10                        │
│        128 GB Unified Memory · Blackwell GPU             │
└──────────────────────────────────────────────────────────┘
```

---

## Hardware

- **NVIDIA DGX Spark** — GB10 Grace Blackwell, 128 GB unified memory
- **Model**: Nemotron 3 Super 120B-A12B (NVFP4 or via Ollama)
- **Mode**: Fully local — $0/token, all data stays on-device

## Output

All analyses export to Excel files in `output/` with full evidence anchoring and audit receipts.

## Related Repositories

| Repository | Description |
|------------|-------------|
| [yuclaw-matrix](https://github.com/YuClawLab/yuclaw-matrix) | CRT lock-free concurrent scheduler |
| [yuclaw-edge](https://github.com/YuClawLab/yuclaw-edge) | C++ FIX 4.4 execution gateway |
| [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) | ZKP cryptographic audit vault |

## License

Proprietary — YuClawLab
