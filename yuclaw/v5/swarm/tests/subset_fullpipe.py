"""Day-5B full-pipeline subset: confirm 70B synthesis keeps direction/risk SEPARATE at scale, on
the new event types (exhibit-fed earnings + multi-specialist regulatory), + true full cost/filing.
The at-scale metrics (grounding/spawn/risk-discrimination) were agent-only; this validates the one
thing that needs the 70B. persist=False; READ-ONLY public.*.
"""
from __future__ import annotations
import json, sys, time, psycopg2
from yuclaw.v5.extract.exhibit import extract_exhibit
from yuclaw.v5.swarm.specialized import run_specialized
from yuclaw.v5.swarm.specialists import RISK_NATURED

CASES = [("0001628280-26-026551", "TSLA earnings (exhibit)"),
         ("0001645590-26-000055", "HPE regulatory (4 specialists)")]


def _nar(acc):
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); c = cn.cursor()
    c.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    r = c.fetchone(); cn.close()
    return r[0] if r else None


def main():
    rows = []
    for acc, tag in CASES:
        nar = _nar(acc) or extract_exhibit(acc, persist=False)["narrative_text"]
        t0 = time.perf_counter()
        res = run_specialized(acc, nar, synthesize=True)
        so = res["synthesis"]["output"]
        spec_dir = {k: (v["output"].get("return_view") or {}).get("direction") for k, v in res["specialists"].items()}
        c6 = [k for k in res["specialists"] if k in RISK_NATURED and (spec_dir.get(k) or "").lower() not in ("neutral", "mixed", "")]
        print(f"\n[{tag}] spawned={res['spawn_keys']}")
        print(f"  RISK channel: level={res['risk_channel']['level']} flag={res['risk_channel']['flag']}")
        print(f"  SYNTH: return.direction={so['return_channel'].get('direction')} "
              f"risk.flag={so['risk_channel'].get('flag')} risk.level={so['risk_channel'].get('level')}")
        print(f"  separate-channels={'YES' if so['return_channel'].get('direction') and so['risk_channel'].get('flag') else 'NO'}"
              f"  C6_violations={c6 or 'none'}  cost={res['timings']['total_secs']}s")
        rows.append(res["timings"]["total_secs"])
    print(f"\nfull-pipeline cost/filing: {sum(rows)/len(rows):.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
