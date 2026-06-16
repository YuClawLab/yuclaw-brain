"""YUCLAW v5 Layer 1 Day 3 — narrative grounding smoke (HARD GATE).

Runs the FULL Day-2 grounded swarm (Bull/Bear/Skeptic + verifier + 70B synthesis) on the
re-fetched MD&A NARRATIVE text instead of the XBRL cover, on ONE 10-K/10-Q that grounded
~0.0 for bull/bear in Day 2. Prints all four outputs + grounding reports verbatim and the
before/after delta vs the persisted Day-2 (XBRL) baseline.

HARD GATE: if narrative extraction fails its sanity check, or grounding does NOT improve on
the prose, STOP and report — that is a real finding (chunking / 8B context limits), not to be
papered over.

Usage:  python3 -m yuclaw.v5.swarm.tests.smoke_narrative [ACCESSION]
"""

from __future__ import annotations

import json
import subprocess
import sys

import psycopg2

from yuclaw.v5.extract.narrative import extract_and_store, sanity_ok
from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, ROLES, SwarmOrchestrator, SwarmDispatchError,
)

DEFAULT_ACC = "0000320193-26-000013"  # AAPL 10-Q — Day-2 XBRL baseline: bull 0.0 / bear 0.0


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
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB\n")


def _day2_baseline(acc: str) -> dict | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT grounding_summary->'per_agent' FROM yuclaw_v5.swarm_outputs "
                "WHERE accession_number=%s AND prompt_version='v2'", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else None


def _clean_prior_jobs(acc: str) -> None:
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def _print_agent(role: str, res: dict) -> None:
    out, g = res["output"], res["grounding"]
    print(f"\n----- {role.upper()} ({res['llama_secs']}s, grounding_rate={g['grounding_rate']}, "
          f"grounded={g['points_grounded']}/{g['points_total']}, "
          f"cites {g['citations_verified']}/{g['citations_total']}) -----")
    print(f"stance: {out['stance']}")
    print(f"return_view={out['return_view'].get('direction')}")
    for p in g["points"]:
        tag = "GROUNDED" if p["grounded"] else f"DISCARDED ({p['discard_reason']})"
        print(f"  [{tag}] {p['point']}")
        for q in p["quotes"]:
            mk = f"verbatim@{q['start']}-{q['end']}" if q["verified"] else "NOT FOUND"
            print(f"       ({mk}) \"{q['quote'][:130]}\"")


def main() -> int:
    acc = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ACC
    _preflight()
    print(f"=== DAY-3 NARRATIVE SMOKE: {acc} ===")

    # 1. extract narrative (re-fetch full primary doc, locate MD&A)
    print("Extracting narrative from primary document ...", flush=True)
    rec = extract_and_store(acc, persist=True)
    ok, probs = sanity_ok(rec)
    print(f"  section={rec['narrative_section']} chars={rec['char_len']} "
          f"alpha={rec['alpha_ratio']} http={rec['http_count']} "
          f"full_doc={rec['full_doc_len']:,}  sanity={'OK' if ok else 'FAIL ' + str(probs)}")
    if not ok:
        print("HARD GATE FAIL: narrative failed sanity check (not prose)."); return 1
    print("  narrative head:", rec["narrative_text"][:180].replace("\n", " "), "...")

    base = _day2_baseline(acc)
    print(f"\nDay-2 XBRL baseline (per-agent grounding_rate): "
          f"{ {r: base[r]['grounding_rate'] for r in ROLES} if base else 'none persisted' }")

    # 2. run the grounded swarm on the NARRATIVE text
    _clean_prior_jobs(acc)
    orch = SwarmOrchestrator()
    try:
        res = orch.dispatch(acc, raw_text=rec["narrative_text"], persist=False, synthesize=True)
    except SwarmDispatchError as e:
        print(f"HARD GATE FAIL — dispatch error: {e}"); return 1

    for role in ROLES:
        _print_agent(role, res["agents"][role])

    s = res["synthesis"]
    print(f"\n----- SYNTHESIS ({s['llama_secs']}s) -----")
    print(json.dumps(s["output"], indent=2, ensure_ascii=False))

    # 3. before/after
    print("\n=== GROUNDING: Day-2 XBRL  ->  Day-3 narrative ===")
    improved = True
    for role in ROLES:
        d3 = res["agents"][role]["grounding"]["grounding_rate"]
        d2 = base[role]["grounding_rate"] if base else None
        print(f"  {role:>8}: {d2}  ->  {d3}   grounded {res['agents'][role]['grounding']['points_grounded']}"
              f"/{res['agents'][role]['grounding']['points_total']}")
    # gate: bull and bear should improve on narrative (the XBRL-starved roles)
    bull3 = res["agents"]["bull"]["grounding"]["grounding_rate"]
    bear3 = res["agents"]["bear"]["grounding"]["grounding_rate"]
    bull2 = base["bull"]["grounding_rate"] if base else 0.0
    bear2 = base["bear"]["grounding_rate"] if base else 0.0
    lifted = (bull3 + bear3) > (bull2 + bear2)
    print(f"\nbull+bear grounding: Day-2 {bull2 + bull2*0:.2f}/{bear2:.2f} -> "
          f"Day-3 {bull3:.2f}/{bear3:.2f}  ({'LIFTED' if lifted else 'NOT improved'})")
    print("\n=== GATE:", "PASS" if lifted else "FAIL (no improvement on prose — real finding)", "===")
    return 0 if lifted else 1


if __name__ == "__main__":
    sys.exit(main())
