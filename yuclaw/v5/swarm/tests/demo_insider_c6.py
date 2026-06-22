"""YUCLAW v5 Layer 1 Day 4 — Insider specialist C6-split demonstration.

No filing in the corpus carries BOTH insider events AND MD&A narrative (insider events come from
Form 4, which has no events_raw row / no prose). So this demonstrates the Insider specialist's C6
behaviour on the real insider-SELL TRANSACTION facts (public.events.raw_excerpt for a real
cluster): heavy insider selling must drive risk_view (elevated), NOT return_view direction.

Asserts the C6 split: return_view.direction == neutral (risk-only), risk_view.level == high.

Usage: python3 -m yuclaw.v5.swarm.tests.demo_insider_c6 [TICKER]
"""

from __future__ import annotations

import json
import sys

import psycopg2

from yuclaw.v5.swarm.specialists import SpecialistAgent
from yuclaw.v5.swarm.worker import WORKER_MODEL


def _insider_cluster_text(ticker: str) -> tuple[str, int]:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True)
    cur = cn.cursor()
    cur.execute("SELECT raw_excerpt FROM public.events "
                "WHERE event_type='INSIDER_SELL' AND ticker=%s "
                "ORDER BY event_time DESC LIMIT 30", (ticker,))
    rows = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT count(*) FROM public.events WHERE event_type='INSIDER_SELL' AND ticker=%s", (ticker,))
    total = cur.fetchone()[0]; cn.close()
    header = (f"Insider transaction report for {ticker} — Form 4 filings (Section 16). "
              f"Total insider-SELL transactions on record: {total}. Recent transactions:\n")
    return header + "\n".join(rows), total


def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "DELL"
    text, total = _insider_cluster_text(ticker)
    print(f"=== INSIDER C6 DEMO: {ticker} ({total} insider-SELL on record) WORKER_MODEL={WORKER_MODEL} ===")
    print("--- input head ---"); print(text[:280], "...\n")
    agent = SpecialistAgent("insider", model=WORKER_MODEL)
    res = agent.run(text)
    out, g = res["output"], res["grounding"]
    rv, rk = out.get("return_view", {}), out.get("risk_view", {})
    print(f"grounding={g['grounding_rate']} grounded={g['points_grounded']}/{g['points_total']} "
          f"cites={g['citations_verified']}/{g['citations_total']} ({res['llama_secs']}s)")
    print("stance:", out["stance"])
    print(json.dumps({"return_view": rv, "risk_view": rk}, indent=2, ensure_ascii=False))
    for p in g["points"]:
        print(f"  [{'G' if p['grounded'] else 'X'}] {p['point']}")

    direction = (rv.get("direction") or "").lower()
    risk_level = (rk.get("level") or "").lower()
    c6_ok = direction in ("neutral", "mixed") and risk_level in ("high", "elevated")
    print(f"\n=== C6 SPLIT: direction={direction!r} (must be neutral/mixed), "
          f"risk={risk_level!r} (must be high/elevated) -> {'PASS' if c6_ok else 'FAIL'} ===")
    return 0 if c6_ok else 1


if __name__ == "__main__":
    sys.exit(main())
