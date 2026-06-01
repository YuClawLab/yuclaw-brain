#!/usr/bin/env python3
"""Macro + sector rotation engine."""
import sys, json, os
sys.path.insert(0, os.path.expanduser("~/yuclaw"))
os.makedirs("output", exist_ok=True)

from yuclaw.modules.sector_rotation import SectorRotationModel
from yuclaw.modules.macro_regime import MacroRegimeDetector

macro = MacroRegimeDetector().detect()
signals = SectorRotationModel().analyze()

print(f"Macro: {macro.regime} ({macro.confidence:.0%})")
for a in macro.portfolio_implications:
    print(f"  -> {a}")
print()
for s in signals:
    print(f"  {s.rank}. {s.sector:20} {s.signal:12} Mom1m:{s.momentum_1m:+.1%}")

output = {
    "macro": {
        "regime": macro.regime, "confidence": macro.confidence,
        "implications": macro.portfolio_implications,
        "indicators": {k: round(v, 4) for k, v in macro.indicators.items()},
    },
    "sectors": [{"sector": s.sector, "signal": s.signal,
                 "mom_1m": round(s.momentum_1m, 4), "rank": s.rank}
                for s in signals],
    "is_real": True,
}
json.dump(output, open("output/macro_sector_latest.json", "w"), indent=2)
