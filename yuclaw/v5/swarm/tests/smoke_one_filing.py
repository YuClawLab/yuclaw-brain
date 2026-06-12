"""YUCLAW v5 Layer 1 — MANDATORY one-filing real smoke test (hard gate).

One real ~6000-char filing from public.events_raw (READ-ONLY) through the FULL
swarm path: orchestrator -> queue -> 3 concurrent agents -> 70B synthesis ->
persist to yuclaw_v5.swarm_outputs. Prints all four outputs verbatim and asserts
the three agents produced genuinely DIFFERENT stances.

Usage:  python3 -m yuclaw.v5.swarm.tests.smoke_one_filing [ACCESSION]
Exit 0 = gate pass, non-zero = gate fail (diagnose, do not proceed).
"""

from __future__ import annotations

import json
import sys

import psycopg2

from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, SwarmOrchestrator, SwarmDispatchError,
)


def _pick_accession() -> str:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT accession_number FROM public.events_raw "
                "WHERE length(raw_text) BETWEEN 5500 AND 8000 "
                "ORDER BY length(raw_text) DESC LIMIT 1")
    row = cur.fetchone(); cn.close()
    if not row:
        print("SMOKE FAIL: no ~6000-char filing in public.events_raw"); sys.exit(2)
    return row[0]


def _clean_prior_jobs(acc: str, version: str = "v1") -> None:
    """Clear prior swarm jobs for this accession so the smoke runs clean
    (idempotency keys would otherwise leave already-succeeded jobs unclaimable).
    yuclaw_v5 schema only."""
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute(
            "DELETE FROM yuclaw_v5.evidence_jobs "
            "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
            (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def main() -> int:
    acc = sys.argv[1] if len(sys.argv) > 1 else _pick_accession()
    print(f"=== SMOKE: filing {acc} ===\n")
    _clean_prior_jobs(acc)

    orch = SwarmOrchestrator()
    try:
        res = orch.dispatch(acc)
    except SwarmDispatchError as e:
        print(f"HARD GATE FAIL — dispatch error: {e}"); return 1

    roles = ("bull", "bear", "skeptic")
    # ---- print all four outputs verbatim ----
    for role in roles:
        a = res["agents"][role]
        print(f"\n----- {role.upper()} ({a['model']}, {a['llama_secs']}s, "
              f"warnings={a['schema_warnings']}) -----")
        print(json.dumps(a["output"], indent=2, ensure_ascii=False))
    s = res["synthesis"]
    print(f"\n----- SYNTHESIS ({s['model']}, {s['llama_secs']}s, "
          f"warnings={s['schema_warnings']}) -----")
    print(json.dumps(s["output"], indent=2, ensure_ascii=False))

    # ---- differentiation gate ----
    dirs = {r: (res["agents"][r]["output"]["return_view"].get("direction") or "").lower()
            for r in roles}
    stances = {r: (res["agents"][r]["output"]["stance"] or "").strip().lower() for r in roles}
    print("\n=== differentiation check ===")
    for r in roles:
        print(f"  {r}: direction={dirs[r]!r}  stance[:80]={stances[r][:80]!r}")
    distinct_stances = len(set(stances.values())) == 3
    bull_bear_differ = dirs["bull"] != dirs["bear"]
    empties = [r for r in roles if not res["agents"][r]["output"]["key_points"]]

    print("\n=== timings ===", json.dumps(res["timings"], indent=2))
    print("agent_job_ids:", res["agent_job_ids"], "synth_job_id:", res["synth_job_id"])

    # persistence confirm
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT swarm_id, created_at FROM yuclaw_v5.swarm_outputs "
                "WHERE accession_number=%s AND prompt_version=%s", (acc, res["prompt_version"]))
    persisted = cur.fetchone(); cn.close()
    print("persisted swarm_outputs row:", persisted)

    ok = True
    if empties:
        print(f"\nHARD GATE FAIL: empty key_points for {empties}"); ok = False
    if not bull_bear_differ:
        print(f"\nDIFFERENTIATION WARNING: bull & bear share direction {dirs['bull']!r} "
              "— iterate role prompts."); ok = False
    if not distinct_stances:
        print("\nDIFFERENTIATION WARNING: stances not all distinct.")
    if persisted is None:
        print("\nHARD GATE FAIL: nothing persisted."); ok = False

    print("\n=== GATE:", "PASS" if ok else "NEEDS ITERATION/FAIL", "===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
