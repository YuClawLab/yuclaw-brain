"""YUCLAW v5 Layer 1 Day 4 — specialized-swarm one-filing smoke (HARD GATE).

Runs the full Day-4 pipeline on ONE real filing that triggers a specialist (AMD 8-K,
M_AND_A_ANNOUNCE): deterministic spawn -> base swarm + specialist(s) (model-agnostic worker) ->
C6 risk channel -> 70B synthesis (direction + risk SEPARATE), on the Day-3 MD&A narrative.

Prints verbatim: which specialists spawned and why, each agent's grounded output + verifier
result, the risk-channel values, and the synthesis with direction and risk as separate channels.

HARD GATE: wrong spawn, cratered grounding, or risk/direction conflation -> STOP and report.

Usage: python3 -m yuclaw.v5.swarm.tests.smoke_specialized [ACCESSION]
"""

from __future__ import annotations

import json
import subprocess
import sys

import psycopg2

from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.worker import WORKER_MODEL, WORKER_THINK

DEFAULT_ACC = "0001193125-26-226746"  # AMD 8-K — M_AND_A_ANNOUNCE


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
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB; "
          f"WORKER_MODEL={WORKER_MODEL} think={WORKER_THINK}\n")


def _narrative(acc: str) -> dict | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT narrative_text, source_type FROM yuclaw_v5.swarm_inputs "
                "WHERE accession_number=%s", (acc,))
    row = cur.fetchone(); cn.close()
    return {"text": row[0], "source_type": row[1]} if row else None


def _print_agent(name: str, res: dict) -> None:
    out, g = res["output"], res["grounding"]
    rv, rk = out.get("return_view", {}), out.get("risk_view", {})
    print(f"\n--- {name.upper()} ({res['model']}, {res['llama_secs']}s, "
          f"grounding={g['grounding_rate']} grounded={g['points_grounded']}/{g['points_total']} "
          f"cites={g['citations_verified']}/{g['citations_total']}) ---")
    print(f"stance: {out['stance']}")
    print(f"return_view.direction={rv.get('direction')}  risk_view.level={rk.get('level')}")
    for p in g["points"]:
        tag = "G" if p["grounded"] else f"X({p['discard_reason']})"
        print(f"  [{tag}] {p['point']}")


def main() -> int:
    acc = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ACC
    _preflight()
    nar = _narrative(acc)
    if not nar:
        print(f"no narrative for {acc} in swarm_inputs"); return 2
    print(f"=== DAY-4 SPECIALIZED SMOKE: {acc} ({nar['source_type']}) ===")

    res = run_specialized(acc, nar["text"], synthesize=True)

    print("\n=== SPAWNED SPECIALISTS (deterministic, from event_type) ===")
    for s in res["spawned"]:
        print(f"  {s['key']}  <- {s['reason']}")
    if not res["spawned"]:
        print("  (none — base swarm only)")

    print("\n=== BASE SWARM ===")
    for r in ROLES:
        _print_agent(r, res["base"][r])
    if res["specialists"]:
        print("\n=== SPECIALISTS ===")
        for key, sres in res["specialists"].items():
            _print_agent(f"spec:{key}", sres)

    rc = res["risk_channel"]
    print("\n=== C6 RISK CHANNEL (separate from direction) ===")
    print(json.dumps(rc, indent=2))

    s = res["synthesis"]
    print(f"\n=== SYNTHESIS ({s['model']}, {s['llama_secs']}s, warnings={s['schema_warnings']}) ===")
    print(json.dumps(s["output"], indent=2, ensure_ascii=False))
    print("\n=== timings ===", json.dumps(res["timings"]))

    # ---- HARD GATE checks ----
    ok = True
    problems = []
    # 1. spawn matched the filing's event (AMD 8-K should spawn 'ma')
    if acc == DEFAULT_ACC and "ma" not in res["spawn_keys"]:
        problems.append("expected M&A specialist not spawned"); ok = False
    # 2. base grounding not cratered (>=1 base agent grounded)
    if sum(res["base"][r]["grounding"]["points_grounded"] for r in ROLES) == 0:
        problems.append("base grounding cratered (0 grounded points)"); ok = False
    # 3. synthesis keeps direction and risk as separate channels
    so = s["output"]
    if not so.get("return_channel", {}).get("direction") or not so.get("risk_channel", {}).get("flag"):
        problems.append("synthesis missing separate return/risk channels"); ok = False
    # 4. C6: if insider specialist present, its direction must be neutral (risk-only)
    if "insider" in res["specialists"]:
        d = (res["specialists"]["insider"]["output"].get("return_view") or {}).get("direction", "")
        if d.lower() not in ("neutral", "mixed", ""):
            problems.append(f"C6 violation: insider specialist gave direction {d!r}"); ok = False

    print("\n=== GATE:", "PASS" if ok else f"FAIL {problems}", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
