#!/usr/bin/env python3
"""Factor scan engine — runs every 30 min, scores full universe."""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.factors.factor_library import FactorLibrary
from yuclaw.universe import DAILY_CORE, FACTOR_UNIVERSE

ALL = sorted(set(DAILY_CORE + FACTOR_UNIVERSE))
lib = FactorLibrary()

results = []
for t in ALL:
    r = lib.calculate(t)
    if r.composite_score is not None:
        results.append({
            "ticker": t, "signal": r.signal,
            "score": round(r.composite_score, 3),
            "mom_1m": round(r.momentum_1m, 3) if r.momentum_1m else None,
            "calmar_90d": round(r.calmar_90d, 3) if r.calmar_90d else None,
            "rsi": round(r.rsi_14, 1) if r.rsi_14 else None,
        })

results.sort(key=lambda x: x["score"], reverse=True)
json.dump(results, open("output/factor_scan_full.json", "w"), indent=2)

buys = [r for r in results if r["signal"] in ("STRONG_BUY", "BUY")]
print(f"Factor: {len(results)} instruments, {len(buys)} BUY signals")
for r in buys[:5]:
    print(f"  {r['ticker']:6} {r['signal']:12} {r['score']:+.3f}")
