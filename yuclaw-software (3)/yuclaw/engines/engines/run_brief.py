#!/usr/bin/env python3
"""Brief engine — generates institutional brief + daily summary."""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.chdir(os.path.expanduser("~/yuclaw"))
os.makedirs("output/briefs", exist_ok=True)

# Generate institutional brief
from yuclaw.finclaw.institutional_brief import generate
brief = generate()
today = datetime.now().strftime("%Y-%m-%d")
with open(f"output/briefs/institutional_{today}.md", "w") as f:
    f.write(brief)
with open("output/briefs/latest.md", "w") as f:
    f.write(brief)

# Generate daily summary JSON
try:
    macro = json.load(open("output/macro_sector_latest.json"))
    factors = json.load(open("output/factor_scan_full.json"))
    backtest = json.load(open("output/backtest_all.json"))
    regime = macro["macro"]["regime"]
    buys = [r for r in factors if r["signal"] in ("STRONG_BUY", "BUY")][:5]
    best = max(backtest, key=lambda x: x["calmar"])
    summary = {
        "date": today, "time": datetime.now().strftime("%H:%M"),
        "regime": regime,
        "top_buys": [r["ticker"] for r in buys],
        "best_strategy": best["name"], "best_calmar": best["calmar"],
        "tweet": f"YUCLAW {today}: {regime}. BUY: {', '.join(r['ticker'] for r in buys[:3])}. Best Calmar {best['calmar']:.3f}. Real data. yuclawlab.github.io/yuclaw-brain",
    }
    json.dump(summary, open("output/daily_summary.json", "w"), indent=2)
    print(f"Brief: {regime} | BUY:{[r['ticker'] for r in buys[:3]]} | Calmar:{best['calmar']}")
    print(f"Tweet: {summary['tweet']}")
except Exception as e:
    print(f"Summary error: {e}")
