"""YUCLAW v5 Layer 1 Day 5C — offline diagnosis + A/B of risk-aggregation candidates.

Reads the per-agent risk capture (risk_recal_capture.py) and, WITHOUT any LLM, computes for the
current max() aggregation and each candidate:
  - the diagnosis: how often each agent floods "high" (the saturation mechanism, shown not assumed);
  - the elevated BASE RATE (is it now rare-by-construction?);
  - DISCRIMINATION: forward-20d realized vol for elevated vs normal, with HONEST split sizes.

Candidates (all pure functions of the captured per-agent risk scores low=0/medium=1/high=2):
  max        : elevated if ANY agent high            (current — the saturated baseline)
  count2     : elevated if >= 2 agents high           (one flooder can't trigger)
  exclbear   : max() but EXCLUDING the structurally-pessimistic bear agent
  mean@T     : graded continuous score = mean(scores); elevated if mean >= T, T chosen so the
               elevated base rate is rare-by-construction (swept; report the rate at each T)

Usage: python3 -m yuclaw.v5.swarm.tests.risk_recal_analyze [capture.json]
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter

SCORE = {"low": 0, "medium": 1, "high": 2, "elevated": 2}


def _scores(rec: dict, exclude: set = frozenset()) -> list[int]:
    return [SCORE.get(v, 0) for k, v in rec["per_agent_risk"].items()
            if v is not None and k not in exclude]


def agg_max(rec) -> bool:
    s = _scores(rec)
    return bool(s) and max(s) >= 2


def agg_count2(rec) -> bool:
    return sum(1 for x in _scores(rec) if x >= 2) >= 2


def agg_exclbear(rec) -> bool:
    s = _scores(rec, exclude={"bear"})
    return bool(s) and max(s) >= 2


def mean_score(rec, exclude: set = frozenset()) -> float:
    s = _scores(rec, exclude)
    return (sum(s) / len(s)) if s else 0.0


def _disc(rows, flagfn):
    """Discrimination: mean fwd vol for elevated vs normal, with split sizes."""
    ev = [r for r in rows if r["fwd_vol"] is not None]
    elev = [r["fwd_vol"] for r in ev if flagfn(r)]
    norm = [r["fwd_vol"] for r in ev if not flagfn(r)]
    base_elev = sum(1 for r in rows if flagfn(r)) / len(rows)
    out = {"base_rate": base_elev, "n_elev": len(elev), "n_norm": len(norm),
           "vol_elev": st.mean(elev) if elev else None, "vol_norm": st.mean(norm) if norm else None}
    out["sep"] = (out["vol_elev"] - out["vol_norm"]) if (elev and norm) else None
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/d5c_capture.json"
    rows = json.load(open(path))["rows"]
    print(f"=== RISK RECALIBRATION ANALYSIS (N={len(rows)}) ===\n")

    # ---- DIAGNOSIS: per-agent flooding ----
    print("-- DIAGNOSIS: how often does each agent emit 'high' risk? --")
    agents = sorted({k for r in rows for k in r["per_agent_risk"]})
    for a in agents:
        vals = [r["per_agent_risk"].get(a) for r in rows if r["per_agent_risk"].get(a) is not None]
        if not vals:
            continue
        hi = sum(1 for v in vals if SCORE.get(v, 0) >= 2)
        dist = Counter(vals)
        print(f"  {a:18} high {hi}/{len(vals)} ({hi/len(vals):.0%})  dist={dict(dist)}")
    # which agent is the lone trigger of an elevated flag under max()?
    lone = Counter()
    for r in rows:
        highs = [k for k, v in r["per_agent_risk"].items() if SCORE.get(v, 0) >= 2]
        if len(highs) == 1:
            lone[highs[0]] += 1
    print(f"\n  filings where elevated is triggered by a SINGLE agent: {sum(lone.values())}/{len(rows)}")
    print(f"  that single trigger is: {dict(lone)}")

    # ---- CANDIDATE A/B ----
    print("\n-- CANDIDATE AGGREGATIONS: base rate + discrimination (fwd 20d vol) --")
    cands = [("max (current)", agg_max), ("count>=2 high", agg_count2),
             ("exclude-bear max", agg_exclbear)]
    # graded mean@T sweep
    means = [mean_score(r) for r in rows]
    print(f"  graded-mean score: min={min(means):.2f} median={st.median(means):.2f} "
          f"max={max(means):.2f}")
    for T in (0.8, 1.0, 1.2, 1.34):
        cands.append((f"mean>= {T}", (lambda r, T=T: mean_score(r) >= T)))

    print(f"\n  {'candidate':18} {'elev_rate':>9} {'n_el/n_no':>9} {'vol_elev':>9} {'vol_norm':>9} {'sep':>8}")
    best = None
    for name, fn in cands:
        d = _disc(rows, fn)
        ve = f"{d['vol_elev']:.4f}" if d['vol_elev'] is not None else "   -  "
        vn = f"{d['vol_norm']:.4f}" if d['vol_norm'] is not None else "   -  "
        sep = f"{d['sep']:+.4f}" if d['sep'] is not None else "   -  "
        print(f"  {name:18} {d['base_rate']:>8.0%} {str(d['n_elev'])+'/'+str(d['n_norm']):>9} "
              f"{ve:>9} {vn:>9} {sep:>8}")
        # track the candidate with the best positive separation that is also rare (rate<=0.6) and has a usable normal arm (n_norm>=5)
        if d["sep"] is not None and d["sep"] > 0 and d["base_rate"] <= 0.6 and d["n_norm"] >= 5:
            if best is None or d["sep"] > best[1]["sep"]:
                best = (name, d)
    print("\n-- VERDICT --")
    if best:
        print(f"  best discriminating + rare candidate: {best[0]}  "
              f"(elev rate {best[1]['base_rate']:.0%}, sep {best[1]['sep']:+.4f}, "
              f"n_norm={best[1]['n_norm']})")
    else:
        print("  NONE crosses the bar (rare AND positive separation AND normal-arm n>=5) — "
              "real finding: aggregation alone may not recover discrimination at this N.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
