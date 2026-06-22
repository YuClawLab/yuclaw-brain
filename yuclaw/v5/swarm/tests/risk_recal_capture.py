"""YUCLAW v5 Layer 1 Day 5C — capture per-agent risk over the Day-5B N=27 set (agent-only).

The Day-5B risk channel saturates because it aggregates risk_view by max() and the Bear agent
floods "high". The candidate fixes (median / count-threshold / graded-mean / exclude-bear) are all
pure functions of the SAME per-agent risk scores — so we capture per-agent risk ONCE here, then
A/B every aggregation OFFLINE (risk_recal_analyze.py), no re-running the LLM per candidate.

Captures, per filing: ticker, corrected event_type, spawned specialists, EACH agent's
risk_view.level (base + specialists), the synth-independent risk drivers, and the forward 20d
realized volatility outcome. Agent-only, persist=False, READ-ONLY public.*.

Usage: python3 -m yuclaw.v5.swarm.tests.risk_recal_capture [out.json]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

# reuse the Day-5B at-scale plumbing verbatim (same filings, same text chain, same fwd-vol)
from yuclaw.v5.swarm.tests.validate_scale import (
    _filings, _acquire_text, _fwd_vol, _preflight,
)
from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.worker import WORKER_MODEL


def main() -> int:
    _preflight()
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/d5c_capture.json"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    filings = _filings()
    if limit:
        filings = filings[:limit]
    print(f"=== RISK CAPTURE: {len(filings)} filings (agent-only) WORKER_MODEL={WORKER_MODEL} ===\n")
    rows = []
    t0 = time.perf_counter()
    for i, f in enumerate(filings, 1):
        text, src = _acquire_text(f)
        if not text:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: NO TEXT"); continue
        try:
            res = run_specialized(f["acc"], text, synthesize=False)
        except Exception as e:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: FAIL {type(e).__name__}: {e}"); continue
        # per-agent risk_view.level (base + specialists)
        per_agent = {}
        for r in ROLES:
            per_agent[r] = ((res["base"][r]["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        for k, v in res["specialists"].items():
            per_agent[f"spec:{k}"] = ((v["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        rec = {
            "acc": f["acc"], "ticker": f["ticker"], "et": f["et"], "evdate": str(f["evdate"]),
            "text_src": src, "spawned": res["spawn_keys"],
            "per_agent_risk": per_agent,
            "current_flag": res["risk_channel"]["flag"],     # the max()-based flag (baseline)
            "current_level": res["risk_channel"]["level"],
            "fwd_vol": _fwd_vol(f["ticker"], f["evdate"]),
        }
        rows.append(rec)
        print(f"[{i}/{len(filings)}] {f['ticker']:5} {f['et']:16} "
              f"base(b/b/s)={per_agent['bull']}/{per_agent['bear']}/{per_agent['skeptic']} "
              f"-> {rec['current_flag']}  fwd_vol={rec['fwd_vol'] if rec['fwd_vol'] is None else round(rec['fwd_vol'],4)}")
    wall = time.perf_counter() - t0
    json.dump({"rows": rows, "wall_s": wall}, open(out_path, "w"), indent=2)
    print(f"\ncaptured {len(rows)} filings in {wall:.0f}s -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
