# FINClaw Institutional Brief
## 2026-03-23 | 02:26 ET | YUCLAW Engine
---

## 1. MARKET REGIME: CRISIS
**Confidence:** 90% | **Source:** Live prices (SPY/TLT/GLD/UUP)

- Maximum cash
- TLT + GLD only
- Hedge with puts

**Overweight:** Energy
**Underweight:** Technology, Financials, ConsumerDisc, Healthcare

## 2. SIGNALS (49 instruments)
**Source:** 12-factor model from real price history

| Ticker | Signal | Score | RSI |
|---|---|---|---|
| MRNA | STRONG_BUY | +0.835 | 47.4 |
| DELL | STRONG_BUY | +0.754 | 54.9 |
| MU | STRONG_BUY | +0.754 | 52.1 |
| ASTS | STRONG_BUY | +0.702 | 52.5 |
| KLAC | STRONG_BUY | +0.674 | 46.7 |
| AMAT | STRONG_BUY | +0.648 | 44.0 |
| LUNR | STRONG_BUY | +0.616 | 49.0 |
| LRCX | STRONG_BUY | +0.581 | 48.9 |

## 3. STRATEGIES (Real Backtest)
**Source:** 15yr historical prices | Real Calmar

| Strategy | Calmar | MaxDD | AnnRet | Sharpe |
|---|---|---|---|---|
| mom_1m_tight | 2.309 | 9.8% | 22.7% | 1.97 |
| mom_6m_tight | 1.764 | 12.8% | 22.5% | 1.81 |
| mom_6m_top3 | 1.291 | 12.8% | 16.5% | 1.18 |
| mom_3m_top3 | 0.968 | 16.7% | 16.2% | 1.16 |
| mom_6m_top5 | 0.799 | 15.2% | 12.2% | 0.90 |

## 4. RISK
**Source:** 2yr historical VaR simulation

| Portfolio | VaR95 | Sharpe | MaxDD | Kelly |
|---|---|---|---|---|
| balanced | -1.63% | 1.60 | -15.6% | 25.0% |
| ai_infra | -4.91% | 0.89 | -33.2% | 25.0% |
| defensive | -0.97% | 1.35 | -9.7% | 25.0% |
| nuclear | -5.63% | 1.53 | -37.0% | 25.0% |
| mag7 | -2.70% | 0.98 | -28.2% | 25.0% |
| pharma | -3.49% | -0.01 | -36.2% | 0.0% |
| space | -5.35% | 2.28 | -34.3% | 25.0% |
| crypto | -3.62% | 0.58 | -36.2% | 25.0% |

---
*FINClaw | YUCLAW Engine | github.com/YuClawLab*
*Every number traceable. Zero LLM estimation in quantitative components.*