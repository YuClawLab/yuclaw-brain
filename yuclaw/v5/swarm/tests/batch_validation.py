"""YUCLAW v5 Layer 1 Day 2 — validation batch (5 filings, FULL grounded path).

Runs the final v2 prompts end-to-end (grounded agents -> verifier -> 70B
synthesis over grounded-only -> persist) on 5 diverse real filings, persisting to
yuclaw_v5.swarm_outputs with prompt_version=v2. Reports the Day-2 metrics:
per-agent grounding rates, discarded-point counts, the verifier's fabricated-
number catches (its saves), latency, and the new cost/filing constant (longer
grounded prompts cost tokens vs Day 1).

Preflight asserts the box is exclusively Ollama's and reports mem headroom.

Usage:  python3 -m yuclaw.v5.swarm.tests.batch_validation [N]
Exit 0 = all filings completed the pipeline (grounding quality is REPORTED, not a
gate — a low rate is a finding, not a crash).
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

FORMS = ("8-K", "10-Q", "10-K", "8-K", "10-Q")  # diverse 5


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


def _pick(forms: tuple, n: int) -> list[tuple[str, str]]:
    """Distinct accessions, one per form slot, diverse lengths."""
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    chosen, seen = [], set()
    for form in forms:
        cur.execute("SELECT accession_number, ticker FROM public.events_raw "
                    "WHERE source_type=%s AND accession_number IS NOT NULL "
                    "AND length(raw_text) BETWEEN 4500 AND 8000 "
                    "AND accession_number <> ALL(%s) "
                    "ORDER BY length(raw_text) DESC LIMIT 1",
                    (form, list(seen) or [""]))
        row = cur.fetchone()
        if row:
            chosen.append((row[0], f"{form}/{row[1] or '?'}"))
            seen.add(row[0])
        if len(chosen) >= n:
            break
    cn.close()
    return chosen


def _clean_prior(acc: str) -> None:
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    _preflight()
    filings = _pick(FORMS, n)
    if len(filings) < n:
        print(f"BATCH ABORT: only found {len(filings)} filings (<{n})"); return 1
    print(f"=== VALIDATION BATCH: {len(filings)} filings (prompt v2) ===")
    for acc, tag in filings:
        print(f"  {acc} ({tag})")
    print()

    orch = SwarmOrchestrator()
    t0 = time.perf_counter()
    rows = []
    for i, (acc, tag) in enumerate(filings, 1):
        _clean_prior(acc)
        print(f"[{i}/{len(filings)}] {acc} ({tag}) ...", flush=True)
        try:
            res = orch.dispatch(acc)  # full path, persist v2
        except SwarmDispatchError as e:
            print(f"   DISPATCH FAIL: {e}")
            rows.append({"acc": acc, "tag": tag, "fail": str(e)}); continue

        gs = res["grounding_summary"]["per_agent"]
        # fabricated-number catches = discards whose reason cites an uncited number
        fab = 0
        evals = []
        for role in ROLES:
            g = res["agents"][role]["grounding"]
            fab += sum(1 for d in g["discarded_points"] if "not in cited quote" in d["reason"])
            evals.append(res["agents"][role].get("eval_count") or 0)
        t = res["timings"]
        rows.append({
            "acc": acc, "tag": tag,
            "rates": {r: gs[r]["grounding_rate"] for r in ROLES},
            "grounded": {r: gs[r]["points_grounded"] for r in ROLES},
            "discarded": {r: gs[r]["points_discarded"] for r in ROLES},
            "fab_caught": fab,
            "ledger": res["grounding_summary"].get("ledger_span_count"),
            "agent_evals": sum(evals),
            "synth_evals": res["synthesis"].get("eval_count") or 0,
            "total_secs": t["total_swarm_secs"], "synth_secs": t["synthesis_secs"],
            "agent_wall": t["concurrent_agent_wall_secs"],
        })
        r = rows[-1]
        print(f"   OK rates(b/b/s)={r['rates']['bull']:.2f}/{r['rates']['bear']:.2f}/"
              f"{r['rates']['skeptic']:.2f} grounded={list(r['grounded'].values())} "
              f"fab_caught={fab} ledger={r['ledger']} total={r['total_secs']}s")

    wall = time.perf_counter() - t0
    done = [r for r in rows if "fail" not in r]
    print("\n=== VALIDATION SUMMARY ===")
    print(f"  completed={len(done)}/{len(rows)}  batch_wall={wall:.1f}s")
    if done:
        for role in ROLES:
            rs = [r["rates"][role] for r in done]
            gp = [r["grounded"][role] for r in done]
            print(f"  {role:>8}: mean_grounding_rate={sum(rs)/len(rs):.2f} "
                  f"min_grounded_points={min(gp)} rates={[round(x,2) for x in rs]}")
        tot_fab = sum(r["fab_caught"] for r in done)
        avg_total = sum(r["total_secs"] for r in done) / len(done)
        avg_synth = sum(r["synth_secs"] for r in done) / len(done)
        avg_agent_evals = sum(r["agent_evals"] for r in done) / len(done)
        avg_synth_evals = sum(r["synth_evals"] for r in done) / len(done)
        print(f"  verifier fabricated-number catches (saves): {tot_fab}")
        print(f"  COST/FILING: total={avg_total:.1f}s synth={avg_synth:.1f}s "
              f"agent_tokens~{avg_agent_evals:.0f} synth_tokens~{avg_synth_evals:.0f}")
        print(f"  ledger spans/filing: {[r['ledger'] for r in done]}")
    for r in rows:
        if "fail" in r:
            print(f"  FAIL {r['acc']} ({r['tag']}) — {r['fail']}")
    # persistence confirm
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT count(*) FROM yuclaw_v5.swarm_outputs WHERE prompt_version='v2'")
    print(f"\n  persisted v2 rows in swarm_outputs: {cur.fetchone()[0]}")
    cn.close()
    return 0 if len(done) == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main())
