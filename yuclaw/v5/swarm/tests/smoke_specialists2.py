"""YUCLAW v5 Layer 1 Day 5A — per-specialist smoke for specialists #5-#10 (HARD GATE).

For each NEW specialist (macro, geopolitical, earningsquality, litigation, sentimentdrift, esg)
runs that specialist (grounded, model-agnostic worker) on a real filing that triggers it, and
checks: well-formed + grounded output, and the C6 discipline — RISK-NATURED specialists
(litigation, geopolitical) must keep return_view.direction neutral/mixed and put their signal in
risk_view. No 70B here (agent-level gate); Part 3 runs the full pipeline + synthesis separation.

HARD GATE: a specialist that fails to ground, or a risk-natured one that emits a directional
call, fails the gate.

Usage: python3 -m yuclaw.v5.swarm.tests.smoke_specialists2
"""

from __future__ import annotations

import subprocess
import sys

import psycopg2

from yuclaw.v5.swarm.specialists import SpecialistAgent, RISK_NATURED
from yuclaw.v5.swarm.worker import WORKER_MODEL, WORKER_THINK

# (specialist key, accession, text source) — text source: 'narrative' (swarm_inputs) | 'raw' (events_raw)
CASES = [
    ("macro",           "0000320193-26-000013", "narrative"),   # AAPL 10-Q MD&A (macro language)
    ("geopolitical",    "0001645590-26-000055", "narrative"),   # HPE Regulatory 10-Q
    ("litigation",      "0001645590-26-000055", "narrative"),   # HPE Regulatory 10-Q
    ("earningsquality", "0001628280-26-026551", "raw"),         # TSLA earnings 8-K
    ("sentimentdrift",  "0001534701-26-000015", "raw"),         # PSX guidance-cut 8-K
    ("esg",             "0001163165-26-000018", "raw"),         # COP 10-Q (ESG content)
]


def _preflight() -> None:
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    bad = [l for l in ps.splitlines()
           if any(t in l for t in ("llama-server", "vllm", "text-generation"))
           and "ollama" not in l.lower()]
    if bad:
        print("PREFLIGHT FAIL: non-Ollama model server:", bad[:2]); sys.exit(3)
    with open("/proc/meminfo") as f:
        mi = {k.strip(): v for k, v in (l.split(":", 1) for l in f)}
    print(f"PREFLIGHT OK; MemAvailable={int(mi['MemAvailable'].split()[0])/1024/1024:.0f} GiB "
          f"WORKER_MODEL={WORKER_MODEL} think={WORKER_THINK}\n")


def _text(acc: str, source: str) -> str | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    if source == "narrative":
        cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    else:
        cur.execute("SELECT raw_text FROM public.events_raw WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else None


def main() -> int:
    _preflight()
    ok_all = True
    for key, acc, source in CASES:
        text = _text(acc, source)
        if not text:
            print(f"[{key}] no text for {acc} ({source})"); ok_all = False; continue
        agent = SpecialistAgent(key, model=WORKER_MODEL)
        res = agent.run(text)
        out, g = res["output"], res["grounding"]
        direction = (out.get("return_view", {}).get("direction") or "").lower()
        risk = (out.get("risk_view", {}).get("level") or "").lower()
        print(f"--- {key.upper()} ({acc}, {res['llama_secs']}s) "
              f"grounding={g['grounding_rate']} grounded={g['points_grounded']}/{g['points_total']} "
              f"cites={g['citations_verified']}/{g['citations_total']} wf={bool(out.get('key_points') is not None)} ---")
        print(f"    stance: {out['stance'][:140]}")
        print(f"    return_view.direction={direction!r}  risk_view.level={risk!r}")
        # gate checks
        problems = []
        if g["points_total"] == 0:
            problems.append("no key_points (malformed)")
        if g["points_grounded"] == 0 and g["points_total"] > 0:
            problems.append("0 grounded")
        if key in RISK_NATURED and direction not in ("neutral", "mixed", ""):
            problems.append(f"C6 VIOLATION: risk-natured but direction={direction!r}")
        tag = "RISK-NATURED" if key in RISK_NATURED else "directional-ok"
        if problems:
            ok_all = False
            print(f"    [{tag}] PROBLEMS: {problems}")
        else:
            print(f"    [{tag}] OK")
        print()
    print("=== GATE:", "PASS" if ok_all else "FAIL", "===")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
