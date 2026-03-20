#!/usr/bin/env python3
"""Backtest engine — runs 10 momentum strategies with real prices."""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.validation.real_backtest import RealBacktester

bt = RealBacktester()
configs = [
    {"name": "mom_1m_top3", "l": 1, "n": 3, "s": 0.05},
    {"name": "mom_1m_top5", "l": 1, "n": 5, "s": 0.05},
    {"name": "mom_1m_tight", "l": 1, "n": 3, "s": 0.02},
    {"name": "mom_3m_top3", "l": 3, "n": 3, "s": 0.05},
    {"name": "mom_3m_top5", "l": 3, "n": 5, "s": 0.08},
    {"name": "mom_6m_top3", "l": 6, "n": 3, "s": 0.05},
    {"name": "mom_6m_top5", "l": 6, "n": 5, "s": 0.08},
    {"name": "mom_6m_tight", "l": 6, "n": 3, "s": 0.03},
    {"name": "mom_12m_top3", "l": 12, "n": 3, "s": 0.08},
    {"name": "mom_12m_top5", "l": 12, "n": 5, "s": 0.10},
]

results = []
for c in configs:
    r = bt.run_momentum(lookback_months=c["l"], top_n=c["n"], stop_loss=c["s"])
    if r:
        results.append({
            "name": c["name"], "calmar": round(r.calmar_ratio, 3),
            "maxdd": round(r.max_drawdown, 4),
            "annret": round(r.annualized_return, 4),
            "sharpe": round(r.sharpe_ratio, 3), "real": True,
        })
        print(f"{c['name']:20} Calmar:{r.calmar_ratio:.3f} AnnRet:{r.annualized_return:.1%} Sharpe:{r.sharpe_ratio:.2f}")

json.dump(results, open("output/backtest_all.json", "w"), indent=2)
best = max(results, key=lambda x: x["calmar"]) if results else {}
print(f"\nBest: {best.get('name')} Calmar:{best.get('calmar')}")
