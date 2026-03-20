#!/usr/bin/env python3
"""Risk engine — analyzes 8 portfolio configurations with real VaR/Kelly."""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.risk.risk_engine import RiskEngine

e = RiskEngine()
portfolios = [
    {"name": "balanced", "t": ["AAPL", "NVDA", "GLD", "TLT"], "w": [0.3, 0.3, 0.2, 0.2]},
    {"name": "ai_infra", "t": ["NVDA", "AMD", "SMCI", "PLTR"], "w": [0.4, 0.3, 0.2, 0.1]},
    {"name": "defensive", "t": ["TLT", "GLD", "XLV", "XLP"], "w": [0.3, 0.3, 0.2, 0.2]},
    {"name": "nuclear", "t": ["NNE", "OKLO", "CCJ", "GLD"], "w": [0.25, 0.25, 0.25, 0.25]},
    {"name": "mag7", "t": ["AAPL", "NVDA", "MSFT", "GOOGL", "META", "AMZN", "TSLA"], "w": [0.2, 0.2, 0.15, 0.15, 0.1, 0.1, 0.1]},
    {"name": "pharma", "t": ["LLY", "NVO", "MRNA", "BNTX"], "w": [0.35, 0.35, 0.15, 0.15]},
    {"name": "space", "t": ["LUNR", "RKLB", "ASTS", "GLD"], "w": [0.3, 0.3, 0.2, 0.2]},
    {"name": "crypto", "t": ["COIN", "MSTR", "TLT", "GLD"], "w": [0.3, 0.3, 0.2, 0.2]},
]

results = []
for p in portfolios:
    try:
        r = e.analyze_portfolio(p["t"], p["w"])
        results.append({
            "portfolio": p["name"], "var_95": round(r.var_95, 4),
            "sharpe": round(r.portfolio_sharpe, 3),
            "maxdd": round(r.max_drawdown, 4),
            "kelly": round(r.kelly_fraction, 3), "real": True,
        })
        print(f"{p['name']:15} VaR:{r.var_95:.2%} Sharpe:{r.portfolio_sharpe:.2f} MaxDD:{r.max_drawdown:.1%} Kelly:{r.kelly_fraction:.1%}")
    except Exception as ex:
        print(f"{p['name']:15} ERROR: {ex}")

json.dump(results, open("output/risk_analysis.json", "w"), indent=2)
print(f"\nRisk: {len(results)} portfolios analyzed")
