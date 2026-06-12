"""YUCLAW v5 Layer 1 — small 3-filing swarm batch (Day-1, runs AFTER the gate).

Drives three DISTINCT real filings through the full swarm path
(orchestrator -> queue -> 3 concurrent 8B agents -> 70B synthesis -> persist),
back to back, to confirm the path is stable across filings and that the 70B
runner stays warm between them. This is the deliberately-watched small batch;
a full backfill is a separate session.

NEW operational rule (post-reboot, baked in): before driving any Ollama work we
assert the box is EXCLUSIVELY Ollama's (no non-Ollama model server) and report
free-memory headroom, because the Day-1 freeze was a GB10 memory collision with
a concurrent non-YUCLAW llama-server.

READ-ONLY on public.events_raw ; writes only to schema yuclaw_v5.
Usage:  python3 -m yuclaw.v5.swarm.tests.batch_three_filings [N]
Exit 0 = all filings passed, non-zero = at least one failed/regressed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

import psycopg2

from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, ROLES, SwarmOrchestrator, SwarmDispatchError,
)


def _preflight() -> None:
    """Hard gate: refuse to run if a non-Ollama model server is up; report mem."""
    ps = subprocess.run(["ps", "-eo", "comm,args"], capture_output=True, text=True).stdout
    bad = [ln for ln in ps.splitlines()
           if any(t in ln for t in ("llama-server", "vllm", "text-generation"))
           and "ollama" not in ln.lower()]
    if bad:
        print("PREFLIGHT FAIL: non-Ollama model server present — box not exclusive:")
        for ln in bad:
            print("  ", ln.strip())
        sys.exit(3)
    with open("/proc/meminfo") as f:
        mi = {k.strip(): v for k, v in (l.split(":", 1) for l in f)}
    avail_gib = int(mi["MemAvailable"].split()[0]) / 1024 / 1024
    print(f"PREFLIGHT OK: no non-Ollama model server; MemAvailable={avail_gib:.0f} GiB\n")


def _pick_accessions(n: int) -> list[str]:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT accession_number FROM public.events_raw "
                "WHERE length(raw_text) BETWEEN 5500 AND 8000 "
                "AND accession_number IS NOT NULL "
                "ORDER BY length(raw_text) DESC LIMIT %s", (n,))
    rows = [r[0] for r in cur.fetchall()]; cn.close()
    return rows


def _clean_prior_jobs(acc: str) -> None:
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def _evaluate(res: dict) -> tuple[bool, list[str]]:
    """Per-filing gate: distinct bull/bear direction, no empty key_points,
    persistence is checked separately by the caller."""
    problems = []
    dirs = {r: (res["agents"][r]["output"]["return_view"].get("direction") or "").lower()
            for r in ROLES}
    if dirs["bull"] == dirs["bear"]:
        problems.append(f"bull==bear direction ({dirs['bull']!r})")
    for r in ROLES:
        if not res["agents"][r]["output"]["key_points"]:
            problems.append(f"empty key_points for {r}")
    return (not problems), problems


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    _preflight()
    accs = _pick_accessions(n)
    if len(accs) < n:
        print(f"BATCH ABORT: only found {len(accs)} filings (<{n})"); return 1
    print(f"=== SWARM BATCH: {len(accs)} filings ===")
    for a in accs:
        print(f"  - {a}")
    print()

    orch = SwarmOrchestrator()
    t0 = time.perf_counter()
    rows = []
    ok_all = True
    for i, acc in enumerate(accs, 1):
        _clean_prior_jobs(acc)
        print(f"[{i}/{len(accs)}] dispatch {acc} ...", flush=True)
        try:
            res = orch.dispatch(acc)
        except SwarmDispatchError as e:
            print(f"   DISPATCH FAIL: {e}"); ok_all = False
            rows.append((acc, "FAIL", None, None, str(e))); continue

        ok, problems = _evaluate(res)
        # persistence confirm (READ-ONLY)
        cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
        cur = cn.cursor()
        cur.execute("SELECT swarm_id FROM yuclaw_v5.swarm_outputs "
                    "WHERE accession_number=%s AND prompt_version=%s",
                    (acc, res["prompt_version"]))
        persisted = cur.fetchone(); cn.close()
        if persisted is None:
            ok = False; problems.append("not persisted")

        dirs = {r: res["agents"][r]["output"]["return_view"].get("direction") for r in ROLES}
        synth_dir = res["synthesis"]["output"]["return_channel"].get("direction")
        t = res["timings"]
        print(f"   {'OK  ' if ok else 'FAIL'} dirs(bull/bear/skeptic)="
              f"{dirs['bull']}/{dirs['bear']}/{dirs['skeptic']} synth={synth_dir} | "
              f"agent_wall={t['concurrent_agent_wall_secs']}s synth={t['synthesis_secs']}s "
              f"total={t['total_swarm_secs']}s")
        if problems:
            print(f"        problems: {problems}")
        ok_all = ok_all and ok
        rows.append((acc, "OK" if ok else "FAIL",
                     t["synthesis_secs"], t["total_swarm_secs"], ";".join(problems)))

    wall = time.perf_counter() - t0
    print("\n=== BATCH SUMMARY ===")
    passed = sum(1 for r in rows if r[1] == "OK")
    print(f"  passed={passed}/{len(rows)}  batch_wall={wall:.1f}s")
    synths = [r[2] for r in rows if r[2] is not None]
    if synths:
        print(f"  synthesis_secs: first={synths[0]} min={min(synths)} "
              f"max={max(synths)} (first includes 70B cold-load; rest warm)")
    for acc, st, ss, ts, prob in rows:
        print(f"  {st:4} {acc} synth={ss}s total={ts}s {('— ' + prob) if prob else ''}")
    print("\n=== BATCH:", "PASS" if ok_all else "FAIL", "===")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
