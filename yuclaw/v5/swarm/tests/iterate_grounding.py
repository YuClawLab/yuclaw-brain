"""YUCLAW v5 Layer 1 Day 2 — prompt-iteration harness (agent-only, NO synthesis).

The core Day-2 loop: run the 3 grounded 8B agents on N diverse filings, grade
them deterministically, and surface grounding rates + the FAILURE MODES (why
points were discarded) so the v2 role prompts can be iterated. Synthesis (70B) is
skipped — the target metric is per-agent grounding, and 70B per round is wasted
cost.

Selects one 8-K, one 10-Q and one 10-K by default (diverse forms), or takes
explicit accessions as args. Prints a per-(filing,agent) table and a per-agent
roll-up against the Day-2 target: grounding_rate >= 0.85 AND >= 3 grounded points.

Usage:  python3 -m yuclaw.v5.swarm.tests.iterate_grounding [ACC ...]
"""

from __future__ import annotations

import subprocess
import sys
from collections import defaultdict

import psycopg2

from yuclaw.v5.swarm.orchestrator import (
    AGENT_JOB_TYPE, SYNTH_JOB_TYPE, ROLES, SwarmOrchestrator, SwarmDispatchError,
)

TARGET_RATE = 0.85
TARGET_POINTS = 3
DEFAULT_FORMS = ("8-K", "10-Q", "10-K")


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
          f"{int(mi['MemAvailable'].split()[0]) / 1024 / 1024:.0f} GiB")


def _pick_one(form: str) -> tuple[str, str] | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT accession_number, ticker FROM public.events_raw "
                "WHERE source_type=%s AND accession_number IS NOT NULL "
                "AND length(raw_text) BETWEEN 5000 AND 8000 "
                "ORDER BY length(raw_text) DESC LIMIT 1", (form,))
    row = cur.fetchone(); cn.close()
    return (row[0], row[1] or "?") if row else None


def _clean_prior(acc: str) -> None:
    """Drop prior swarm jobs for this accession so each round runs fresh. Without
    this, a re-run hits idempotency: the previous round's jobs are 'succeeded', so
    enqueue returns them and the workers find nothing pending to claim (timeout)."""
    cn = psycopg2.connect("dbname=yuclaw_events")
    with cn, cn.cursor() as cur:
        cur.execute("DELETE FROM yuclaw_v5.evidence_jobs "
                    "WHERE job_type IN (%s,%s) AND idempotency_key LIKE %s",
                    (AGENT_JOB_TYPE, SYNTH_JOB_TYPE, f"%{acc}%"))
    cn.close()


def _select() -> list[tuple[str, str]]:
    out = []
    for f in DEFAULT_FORMS:
        r = _pick_one(f)
        if r:
            out.append((r[0], f"{f}/{r[1]}"))
    return out


def main() -> int:
    _preflight()
    if len(sys.argv) > 1:
        filings = [(a, "?") for a in sys.argv[1:]]
    else:
        filings = _select()
    print(f"=== ITERATION ROUND — {len(filings)} filings (agents only) ===")
    for acc, tag in filings:
        print(f"  {acc} ({tag})")

    orch = SwarmOrchestrator()
    per_agent_rates: dict[str, list] = defaultdict(list)
    per_agent_points: dict[str, list] = defaultdict(list)

    print(f"\n{'filing':>22} {'agent':>8} {'rate':>6} {'grnd':>5} {'cites':>9}  discards")
    for acc, tag in filings:
        _clean_prior(acc)
        try:
            res = orch.dispatch(acc, synthesize=False, persist=False)
        except SwarmDispatchError as e:
            print(f"  {acc} DISPATCH FAIL: {e}"); continue
        for role in ROLES:
            g = res["agents"][role]["grounding"]
            per_agent_rates[role].append(g["grounding_rate"])
            per_agent_points[role].append(g["points_grounded"])
            discards = "; ".join(d["reason"] for d in g["discarded_points"]) or "-"
            print(f"{acc[-10:]:>22} {role:>8} {g['grounding_rate']:>6.2f} "
                  f"{g['points_grounded']:>2}/{g['points_total']:<2} "
                  f"{g['citations_verified']:>3}/{g['citations_total']:<3}    {discards[:80]}")

    print(f"\n=== PER-AGENT ROLL-UP (target rate>={TARGET_RATE}, points>={TARGET_POINTS}) ===")
    all_pass = True
    for role in ROLES:
        rates = per_agent_rates[role] or [0]
        pts = per_agent_points[role] or [0]
        mean_rate = sum(rates) / len(rates)
        min_pts = min(pts)
        ok = mean_rate >= TARGET_RATE and min_pts >= TARGET_POINTS
        all_pass = all_pass and ok
        print(f"  {role:>8}: mean_rate={mean_rate:.2f} min_grounded_points={min_pts} "
              f"per_filing_rates={[round(r, 2) for r in rates]}  "
              f"{'PASS' if ok else 'BELOW TARGET'}")
    print(f"\n=== ROUND RESULT: {'TARGET MET' if all_pass else 'ITERATE'} ===")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
