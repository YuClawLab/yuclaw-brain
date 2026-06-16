"""YUCLAW v5 Layer 1 Day 3 — narrative validation batch (5 filings, XBRL vs narrative).

Runs the Day-2 grounded swarm on the re-fetched MD&A narrative for the SAME 5 filings used in
the Day-2 validation batch, so per-agent grounding deltas are directly comparable. Narrative
is persisted to yuclaw_v5.swarm_inputs (additive); the swarm result itself is not re-persisted
(persist=False) so the Day-2 swarm_outputs baseline rows are preserved for comparison.

Headline question: did 10-K/10-Q bull/bear grounding move from ~0.0 toward the ~0.85 the prose
8-Ks already hit? Reports per-filing deltas + new cost/filing (extraction + swarm).

Usage:  python3 -m yuclaw.v5.swarm.tests.batch_narrative
"""

from __future__ import annotations

import subprocess
import sys
import time

import psycopg2

from yuclaw.v5.extract.narrative import extract_and_store, sanity_ok
from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, ROLES, SwarmOrchestrator, SwarmDispatchError,
)

# Same 5 as the Day-2 validation batch (for direct baseline comparison).
FILINGS = [
    ("0001645590-26-000052", "8-K/HPE"),
    ("0000320193-26-000013", "10-Q/AAPL"),
    ("0000097745-26-000018", "10-K/TMO"),
    ("0001193125-26-226746", "8-K/AMD"),
    ("0000200406-26-000087", "10-Q/JNJ"),
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
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB\n")


def _day2(acc: str) -> dict | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT grounding_summary->'per_agent' FROM yuclaw_v5.swarm_outputs "
                "WHERE accession_number=%s AND prompt_version='v2'", (acc,))
    row = cur.fetchone(); cn.close()
    return row[0] if row else None


def _clean(acc: str) -> None:
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def main() -> int:
    _preflight()
    print("=== DAY-3 NARRATIVE VALIDATION BATCH (5 filings) ===")
    orch = SwarmOrchestrator()
    rows = []
    t0 = time.perf_counter()
    for acc, tag in FILINGS:
        print(f"\n[{tag}] {acc}", flush=True)
        te = time.perf_counter()
        try:
            rec = extract_and_store(acc, persist=True)
        except Exception as e:
            print(f"   EXTRACT FAIL: {type(e).__name__}: {e}")
            rows.append({"acc": acc, "tag": tag, "fail": "extract"}); continue
        extract_secs = time.perf_counter() - te
        ok, probs = sanity_ok(rec)
        print(f"   narrative: section={rec['narrative_section']} chars={rec['char_len']} "
              f"alpha={rec['alpha_ratio']} http={rec['http_count']} sanity={'OK' if ok else probs}")
        base = _day2(acc)
        _clean(acc)
        try:
            res = orch.dispatch(acc, raw_text=rec["narrative_text"], persist=False, synthesize=True)
        except SwarmDispatchError as e:
            print(f"   DISPATCH FAIL: {e}"); rows.append({"acc": acc, "tag": tag, "fail": "dispatch"}); continue
        d3 = {r: res["agents"][r]["grounding"]["grounding_rate"] for r in ROLES}
        d2 = {r: (base[r]["grounding_rate"] if base else None) for r in ROLES}
        rows.append({"acc": acc, "tag": tag, "section": rec["narrative_section"],
                     "alpha": rec["alpha_ratio"], "d2": d2, "d3": d3,
                     "extract_secs": round(extract_secs, 1),
                     "total_secs": res["timings"]["total_swarm_secs"]})
        print(f"   grounding  bull {d2['bull']}→{d3['bull']}  bear {d2['bear']}→{d3['bear']}  "
              f"skeptic {d2['skeptic']}→{d3['skeptic']}")

    wall = time.perf_counter() - t0
    print("\n=== DELTA SUMMARY (Day-2 XBRL → Day-3 narrative) ===")
    done = [r for r in rows if "fail" not in r]
    for r in done:
        print(f"  {r['tag']:>10} ({r['section']},α={r['alpha']}): "
              f"bull {r['d2']['bull']}→{r['d3']['bull']}  "
              f"bear {r['d2']['bear']}→{r['d3']['bear']}  "
              f"skeptic {r['d2']['skeptic']}→{r['d3']['skeptic']}")
    for role in ROLES:
        d2m = [r["d2"][role] for r in done if r["d2"][role] is not None]
        d3m = [r["d3"][role] for r in done]
        if d2m and d3m:
            print(f"  MEAN {role:>8}: {sum(d2m)/len(d2m):.2f} → {sum(d3m)/len(d3m):.2f}")
    if done:
        avg_ex = sum(r["extract_secs"] for r in done) / len(done)
        avg_tot = sum(r["total_secs"] for r in done) / len(done)
        print(f"\n  cost/filing: extraction {avg_ex:.1f}s + swarm {avg_tot:.1f}s  (batch_wall {wall:.0f}s)")
    print(f"  completed {len(done)}/{len(rows)}")
    return 0 if len(done) == len(rows) else 2


if __name__ == "__main__":
    sys.exit(main())
