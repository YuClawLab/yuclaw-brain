"""YUCLAW v5 Layer 1 Day 5A — Part-3 batch: full pipeline across new event types.

Runs the full specialized pipeline (base swarm + spawned specialists from the CORRECTED
event-type layer + content triggers + C6 risk channel + 70B synthesis) on filings that exercise
the new specialists, and reports per-filing: spawn correctness, grounding per agent, risk-channel
output, direction/risk separation, and cost/filing vs Day-4's 182s.

Reuses Day-3/Day-4 narratives where present (persist=False — no swarm_outputs writes); extracts a
missing narrative on the fly (cached).

Usage: python3 -m yuclaw.v5.swarm.tests.batch_specialists2
"""

from __future__ import annotations

import subprocess
import sys
import time

import psycopg2

from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.specialists import RISK_NATURED
from yuclaw.v5.swarm.worker import WORKER_MODEL
from yuclaw.v5.extract.narrative import extract_and_store, sanity_ok

# Filings chosen to collectively trigger the new specialists (via corrected tags + content):
#  HPE-reg  -> regulatory + litigation + macro + geopolitical
#  AAPL     -> macro (content)
#  TMO      -> macro (content)
#  AMD 8-K  -> now FINANCING (corrected) -> NO ma specialist (the Day-4 fix, demonstrated)
FILINGS = [
    ("0001645590-26-000055", "10-Q/HPE (Regulatory+Litigation)"),
    ("0000320193-26-000013", "10-Q/AAPL (Macro)"),
    ("0000097745-26-000018", "10-K/TMO (Macro)"),
    ("0001193125-26-226746", "8-K/AMD (FINANCING - no M&A now)"),
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
          f"WORKER_MODEL={WORKER_MODEL}\n")


def _narrative(acc: str) -> str | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else None


def main() -> int:
    _preflight()
    print(f"=== DAY-5A BATCH ({len(FILINGS)} filings, full pipeline) ===")
    rows = []
    t0 = time.perf_counter()
    for acc, tag in FILINGS:
        nar = _narrative(acc)
        if not nar:
            rec = extract_and_store(acc, persist=True)
            ok, probs = sanity_ok(rec)
            if not ok:
                print(f"[{tag}] extract FAIL {probs}"); rows.append({"tag": tag, "fail": "extract"}); continue
            nar = rec["narrative_text"]
        print(f"\n[{tag}] {acc}", flush=True)
        try:
            res = run_specialized(acc, nar, synthesize=True)
        except Exception as e:
            print(f"  FAIL {type(e).__name__}: {e}"); rows.append({"tag": tag, "fail": str(e)[:100]}); continue
        rc = res["risk_channel"]; so = res["synthesis"]["output"]
        spec_dirs = {k: (v["output"].get("return_view") or {}).get("direction") for k, v in res["specialists"].items()}
        # C6 check: risk-natured specialists must be neutral/mixed
        c6_viol = [k for k in res["specialists"] if k in RISK_NATURED
                   and (spec_dirs.get(k) or "").lower() not in ("neutral", "mixed", "")]
        rows.append({
            "tag": tag, "spawned": res["spawn_keys"],
            "base_gr": {r: round(res["base"][r]["grounding"]["grounding_rate"], 2) for r in ROLES},
            "spec_gr": {k: round(v["grounding"]["grounding_rate"], 2) for k, v in res["specialists"].items()},
            "spec_dirs": spec_dirs, "c6_viol": c6_viol,
            "risk_level": rc["level"], "risk_flag": rc["flag"],
            "synth_dir": so["return_channel"].get("direction"), "synth_risk": so["risk_channel"].get("flag"),
            "total_secs": res["timings"]["total_secs"],
        })
        r = rows[-1]
        print(f"  spawned={r['spawned'] or 'base-only'}")
        print(f"  base_gr={r['base_gr']}  spec_gr={r['spec_gr']}")
        print(f"  spec_dirs={r['spec_dirs']}  C6_violations={r['c6_viol'] or 'none'}")
        print(f"  RISK={r['risk_level']}/{r['risk_flag']} | SYNTH dir={r['synth_dir']} risk={r['synth_risk']}  ({r['total_secs']}s)")

    wall = time.perf_counter() - t0
    done = [r for r in rows if "fail" not in r]
    print("\n=== BATCH SUMMARY ===")
    print(f"  completed {len(done)}/{len(rows)}  batch_wall={wall:.0f}s")
    any_c6 = [r for r in done if r["c6_viol"]]
    print(f"  C6 violations (risk-natured specialist gave direction): {len(any_c6)} "
          f"{'<<< FAIL' if any_c6 else '(none — PASS)'}")
    for r in done:
        print(f"  {r['tag']:>34}: spawned={r['spawned'] or '[]'}  risk={r['risk_level']}/{r['risk_flag']}  dir={r['synth_dir']}")
    if done:
        avg = sum(r["total_secs"] for r in done) / len(done)
        print(f"  cost/filing: {avg:.1f}s vs Day-4 182s")
    for r in rows:
        if "fail" in r:
            print(f"  FAIL {r['tag']} — {r['fail']}")
    return 0 if (len(done) == len(rows) and not any_c6) else 1


if __name__ == "__main__":
    sys.exit(main())
