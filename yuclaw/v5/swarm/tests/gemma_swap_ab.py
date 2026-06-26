"""Order-3 in-place A/B: run the full swarm on ONE real filing with the configured
WORKER_MODEL (Gemma or 8B), report grounding / citation fidelity / C6 separation / timing.
Usage: YUCLAW_V5_WORKER_MODEL=<model> python3 -m yuclaw.v5.swarm.tests.gemma_swap_ab <acc>
"""
from __future__ import annotations
import sys, time, statistics as st
from yuclaw.v5.swarm.tests.validate_scale import _filings, _acquire_text
from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.specialists import RISK_NATURED
from yuclaw.v5.swarm.worker import WORKER_MODEL


def main() -> int:
    acc = sys.argv[1] if len(sys.argv) > 1 else "0001628280-26-025365"
    f = next(x for x in _filings() if x["acc"] == acc)
    text, src = _acquire_text(f)
    print(f"=== SWARM A/B  worker={WORKER_MODEL}  filing={f['ticker']} {f['et']} "
          f"(src={src}, {len(text)} chars) ===")
    t0 = time.perf_counter()
    res = run_specialized(acc, text, synthesize=True)
    wall = time.perf_counter() - t0

    base_gr = [res["base"][r]["grounding"]["grounding_rate"] for r in ROLES]
    spec_gr = [v["grounding"]["grounding_rate"] for v in res["specialists"].values()]
    cv = sum(res["base"][r]["grounding"]["citations_verified"] for r in ROLES)
    ct = sum(res["base"][r]["grounding"]["citations_total"] for r in ROLES)
    c6 = [k for k in res["specialists"]
          if k in RISK_NATURED
          and (((res["specialists"][k]["output"].get("return_view") or {}).get("direction") or "").lower()
               not in ("neutral", "mixed", ""))]
    allgr = base_gr + spec_gr
    synth = res.get("synthesis") or {}
    rc = synth.get("return_channel") or {}
    rk = synth.get("risk_channel") or {}
    print(f"  base grounding   : {[round(x,2) for x in base_gr]}  mean={st.mean(base_gr):.3f}")
    print(f"  spec grounding   : {[round(x,2) for x in spec_gr]}  ({list(res['specialists'])})")
    print(f"  MEAN grounding   : {st.mean(allgr):.3f}  (n={len(allgr)})")
    print(f"  base cite fidelity: {cv}/{ct} = {(cv/ct if ct else 0):.3f}")
    print(f"  C6 separation    : {len(c6)} risk-natured emitting direction {'<<FAIL' if c6 else '(PASS)'}")
    print(f"  synth direction={rc.get('direction')} risk_flag={rk.get('flag')} "
          f"(separate-channels {'YES' if rc.get('direction') and rk.get('flag') else '?'})")
    print(f"  wall={wall:.0f}s  spawned={res['spawn_keys']}")
    print(f"RESULT {WORKER_MODEL} mean_grounding={st.mean(allgr):.3f} cite={(cv/ct if ct else 0):.3f} "
          f"c6_viol={len(c6)} wall={wall:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
