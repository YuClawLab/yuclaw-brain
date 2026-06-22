"""YUCLAW v5 Layer 1 Day 4 — specialized validation batch.

Runs the Day-4 pipeline (base swarm + spawned specialists + C6 risk channel + 70B synthesis) on
a batch spanning multiple event types: the 5 Day-3 filings (2 trigger the M&A specialist; 3 are
base-only) plus the HPE Regulatory 10-Q (REGULATORY_ACTION). Narratives come from Day-3
swarm_inputs; any missing one is extracted on the fly (one EDGAR fetch, cached).

Per filing reports: specialists spawned (+why), grounding per agent, the risk-channel
flag/level, and whether synthesis kept direction and risk separate. Plus cost/filing vs the
Day-3 baseline (~196s).

Usage: python3 -m yuclaw.v5.swarm.tests.batch_specialized
"""

from __future__ import annotations

import subprocess
import sys
import time

import psycopg2

from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.worker import WORKER_MODEL
from yuclaw.v5.extract.narrative import extract_and_store, sanity_ok

FILINGS = [
    ("0001645590-26-000052", "8-K/HPE (M&A)"),
    ("0001193125-26-226746", "8-K/AMD (M&A)"),
    ("0000320193-26-000013", "10-Q/AAPL (base)"),
    ("0000097745-26-000018", "10-K/TMO (base)"),
    ("0000200406-26-000087", "10-Q/JNJ (base)"),
    ("0001645590-26-000055", "10-Q/HPE (Regulatory)"),
]


def _preflight() -> None:
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    bad = [l for l in ps.splitlines()
           if any(t in l for t in ("llama-server", "vllm", "text-generation"))
           and "ollama" not in l.lower()]
    if bad:
        print("PREFLIGHT FAIL: non-Ollama model server present:", bad[:2]); sys.exit(3)
    with open("/proc/meminfo") as f:
        mi = {k.strip(): v for k, v in (l.split(":", 1) for l in f)}
    print(f"PREFLIGHT OK: box exclusive; MemAvailable="
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB; WORKER_MODEL={WORKER_MODEL}\n")


def _narrative(acc: str) -> str | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else None


def main() -> int:
    _preflight()
    print(f"=== DAY-4 SPECIALIZED VALIDATION BATCH ({len(FILINGS)} filings) ===")
    rows = []
    t0 = time.perf_counter()
    for acc, tag in FILINGS:
        nar = _narrative(acc)
        if not nar:
            print(f"[{tag}] extracting narrative ...", flush=True)
            rec = extract_and_store(acc, persist=True)
            ok, probs = sanity_ok(rec)
            if not ok:
                print(f"  EXTRACT sanity FAIL {probs}"); rows.append({"acc": acc, "tag": tag, "fail": "extract"}); continue
            nar = rec["narrative_text"]
        print(f"\n[{tag}] {acc}", flush=True)
        try:
            res = run_specialized(acc, nar, synthesize=True)
        except Exception as e:
            print(f"  FAIL {type(e).__name__}: {e}"); rows.append({"acc": acc, "tag": tag, "fail": str(e)[:120]}); continue
        rc = res["risk_channel"]
        so = res["synthesis"]["output"]
        base_gr = {r: res["base"][r]["grounding"]["grounding_rate"] for r in ROLES}
        spec_gr = {k: v["grounding"]["grounding_rate"] for k, v in res["specialists"].items()}
        rows.append({
            "acc": acc, "tag": tag, "spawned": res["spawn_keys"],
            "base_gr": base_gr, "spec_gr": spec_gr,
            "risk_level": rc["level"], "risk_flag": rc["flag"], "insider_gate": rc["insider_gate"],
            "synth_dir": so["return_channel"].get("direction"),
            "synth_risk": so["risk_channel"].get("flag"),
            "total_secs": res["timings"]["total_secs"],
            "worker_wall": res["timings"]["concurrent_worker_wall_secs"],
            "synth_secs": res["timings"]["synthesis_secs"],
        })
        r = rows[-1]
        print(f"  spawned={r['spawned'] or 'base-only'}  base_gr={ {k:round(v,2) for k,v in base_gr.items()} }"
              f"  spec_gr={ {k:round(v,2) for k,v in spec_gr.items()} }")
        print(f"  RISK channel: level={r['risk_level']} flag={r['risk_flag']} insider_gate={r['insider_gate']}"
              f"  | SYNTH: direction={r['synth_dir']} risk_flag={r['synth_risk']}  ({r['total_secs']}s)")

    wall = time.perf_counter() - t0
    done = [r for r in rows if "fail" not in r]
    print("\n=== BATCH SUMMARY ===")
    print(f"  completed {len(done)}/{len(rows)}  batch_wall={wall:.0f}s")
    for r in done:
        print(f"  {r['tag']:>22}: spawned={r['spawned'] or '[]'}  risk={r['risk_level']}/{r['risk_flag']}  "
              f"dir={r['synth_dir']}")
    if done:
        avg = sum(r["total_secs"] for r in done) / len(done)
        avg_w = sum(r["worker_wall"] for r in done) / len(done)
        avg_s = sum(r["synth_secs"] for r in done) / len(done)
        print(f"  cost/filing: total={avg:.1f}s (worker_wall {avg_w:.1f}s + synth {avg_s:.1f}s) "
              f"vs Day-3 ~196s")
        n_spec = sum(1 for r in done if r["spawned"])
        print(f"  filings that spawned a specialist: {n_spec}/{len(done)}")
    for r in rows:
        if "fail" in r:
            print(f"  FAIL {r['tag']} — {r['fail']}")
    return 0 if len(done) == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main())
