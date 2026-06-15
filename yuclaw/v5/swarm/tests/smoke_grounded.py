"""YUCLAW v5 Layer 1 Day 2 — grounded one-filing smoke (HARD GATE).

Runs the FULL grounded path (3 grounded 8B agents -> verifier -> 70B synthesis
over grounded-only claims -> persist) on the Day-1 CONTRADICTION filing
(0000097745-26-000018, Thermo Fisher) where a v1 bull claimed "debt decreased"
while a v1 bear claimed "debt increased" on the same text.

Prints all four outputs + per-agent grounding reports verbatim, then the debt
exhibit: what each agent now says about debt and the verbatim span it cites — so
the contradiction is either RESOLVED (both cite the real debt language) or
SURFACED as legitimate quote-backed interpretive disagreement.

Preflight (Day-2 operational rule): refuse to run if a non-Ollama model server is
present; report memory headroom.

Usage:  python3 -m yuclaw.v5.swarm.tests.smoke_grounded [ACCESSION]
Exit 0 = gate pass, non-zero = pipeline error (diagnose, do not proceed).
"""

from __future__ import annotations

import json
import subprocess
import sys

import psycopg2

from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, ROLES, SwarmOrchestrator, SwarmDispatchError,
)

CONTRADICTION_ACC = "0000097745-26-000018"


def _preflight() -> None:
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    bad = [ln for ln in ps.splitlines()
           if any(t in ln for t in ("llama-server", "vllm", "text-generation"))
           and "ollama" not in ln.lower()]
    if bad:
        print("PREFLIGHT FAIL: non-Ollama model server present:", bad[:2]); sys.exit(3)
    with open("/proc/meminfo") as f:
        mi = {k.strip(): v for k, v in (l.split(":", 1) for l in f)}
    print(f"PREFLIGHT OK: box exclusive; MemAvailable="
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB\n")


def _clean_prior_jobs(acc: str) -> None:
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def _print_agent(role: str, res: dict) -> None:
    out, g = res["output"], res["grounding"]
    print(f"\n----- {role.upper()} ({res['model']}, {res['llama_secs']}s, "
          f"grounding_rate={g['grounding_rate']}, "
          f"grounded={g['points_grounded']}/{g['points_total']}, "
          f"citations {g['citations_verified']}/{g['citations_total']}, "
          f"warnings={res['schema_warnings']}) -----")
    print(f"stance: {out['stance']}")
    print(f"return_view={out['return_view'].get('direction')}  "
          f"risk_view={out['risk_view'].get('level')}")
    for p in g["points"]:
        tag = "GROUNDED" if p["grounded"] else f"DISCARDED ({p['discard_reason']})"
        print(f"  [{tag}] {p['point']}")
        for q in p["quotes"]:
            mark = f"verbatim@{q['start']}-{q['end']}" if q["verified"] else "NOT FOUND"
            print(f"       ({mark}) \"{q['quote'][:140]}\"")


def _debt_exhibit(res_by_role: dict) -> None:
    print("\n" + "=" * 72)
    print("DEBT EXHIBIT — the Day-1 contradiction, re-examined under grounding")
    print("=" * 72)
    any_debt = False
    for role in ROLES:
        g = res_by_role[role]["grounding"]
        hits = []
        for p in g["points"]:
            if "debt" in p["point"].lower() or any("debt" in q["quote"].lower()
                                                   for q in p["quotes"]):
                verified_q = [q for q in p["quotes"] if q["verified"]
                              and "debt" in q["quote"].lower()]
                hits.append((p, verified_q))
        if hits:
            any_debt = True
            for p, vq in hits:
                status = "GROUNDED" if p["grounded"] else f"DISCARDED({p['discard_reason']})"
                print(f"\n  {role.upper()} [{status}]: {p['point']}")
                for q in vq:
                    print(f"      cites verbatim @ {q['start']}-{q['end']}: "
                          f"\"{q['quote'][:160]}\"")
                if not vq:
                    print("      (no VERIFIED debt quote — claim is not grounded)")
        else:
            print(f"\n  {role.upper()}: no debt claim this run")
    if not any_debt:
        print("\n  (No agent made a debt claim this run — contradiction not reproduced.)")
    print("\nInterpretation: any debt claim that SURVIVES is backed by a verbatim")
    print("span. A bull and bear both grounding debt claims to real filing language")
    print("is legitimate quote-backed disagreement; a fabricated debt direction is")
    print("now DISCARDED by the verifier rather than published.")


def main() -> int:
    acc = sys.argv[1] if len(sys.argv) > 1 else CONTRADICTION_ACC
    _preflight()
    print(f"=== GROUNDED SMOKE: filing {acc} (prompt v2) ===")
    _clean_prior_jobs(acc)

    orch = SwarmOrchestrator()
    try:
        res = orch.dispatch(acc)
    except SwarmDispatchError as e:
        print(f"HARD GATE FAIL — dispatch error: {e}"); return 1

    for role in ROLES:
        _print_agent(role, res["agents"][role])

    s = res["synthesis"]
    sg = s["synth_citation_grounding"]
    print(f"\n----- SYNTHESIS ({s['model']}, {s['llama_secs']}s, "
          f"cited {sg['citations_verified']}/{sg['citations_total']} verifiable, "
          f"warnings={s['schema_warnings']}) -----")
    print(json.dumps(s["output"], indent=2, ensure_ascii=False))

    print("\n=== citation_ledger (proto evidence token) ===")
    led = res["citation_ledger"]
    print(f"accession={led['accession_number']} spans={len(led['spans'])} "
          f"sources={sorted({sp['source'] for sp in led['spans']})}")

    print("\n=== grounding_summary ===")
    print(json.dumps(res["grounding_summary"], indent=2))

    _debt_exhibit(res["agents"])

    # persistence confirm
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT swarm_id, (citation_ledger->>'accession_number') "
                "FROM yuclaw_v5.swarm_outputs WHERE accession_number=%s AND prompt_version=%s",
                (acc, res["prompt_version"]))
    persisted = cur.fetchone(); cn.close()

    print("\n=== timings ===", json.dumps(res["timings"]))
    ok = True
    if persisted is None or persisted[1] != acc:
        print("HARD GATE FAIL: not persisted with ledger."); ok = False
    print("\n=== GATE:", "PASS" if ok else "FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
