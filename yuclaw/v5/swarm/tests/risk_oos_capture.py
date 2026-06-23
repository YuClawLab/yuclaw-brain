"""YUCLAW v5 Layer 1 — OOS risk capture (held-out event types, frozen count2 config).

The Day-5C count>=2 recalibration was tuned/measured on the L1 corpus (8 event types,
base + specialists). That corpus is now exhausted (corpus == tuning set; no new L1-type
filings since D5C), so there are ZERO same-regime held-out filings. The only genuinely
unseen filings are NON-L1 event types (EXEC_CHANGE / OTHER_MATERIAL / DIVIDEND) — these
spawn NO specialists, so they exercise the risk channel in a BASE-ONLY regime.

This harness captures, per held-out filing, EACH base agent's risk_view.level + the
forward-20d realized vol, into the SAME schema as risk_recal_capture.py so the existing
risk_recal_analyze.py A/B (max vs count2 vs ...) runs unchanged. We measure whether
count2's rare-by-construction property GENERALIZES out-of-sample (vs max() re-saturating
via the structurally-pessimistic Bear). Frozen config: no re-tuning to this batch.

Agent-only, persist=False, READ-ONLY public.*. Usage:
  python3 -m yuclaw.v5.swarm.tests.risk_oos_capture [out.json]
"""

from __future__ import annotations

import json
import sys
import time

import psycopg2

from yuclaw.v5.swarm.tests.validate_scale import _acquire_text, _fwd_vol, _preflight
from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.worker import WORKER_MODEL

# Event types NOT used to tune count2 (disjoint from the L1 8-type corpus).
OOS_TYPES = ("EXEC_CHANGE", "OTHER_MATERIAL", "DIVIDEND")


def _oos_filings() -> list[dict]:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("""
        SELECT DISTINCT er.accession_number AS acc, er.ticker, er.source_type AS form,
               e.event_time::date AS evdate,
               COALESCE(c.corrected_event_type, e.event_type) AS et
        FROM public.events e JOIN public.events_raw er ON er.source_url=e.source_url
        LEFT JOIN yuclaw_v5.event_type_corrected c ON c.event_id=e.event_id
        WHERE e.event_id NOT LIKE 'CASCADE%%'
          AND COALESCE(c.corrected_event_type,e.event_type) IN %s
        ORDER BY et, evdate""", (OOS_TYPES,))
    rows = [{"acc": a, "ticker": t, "form": fm, "evdate": d, "et": et}
            for a, t, fm, d, et in cur.fetchall()]
    cn.close()
    return rows


def main() -> int:
    _preflight()
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/oos_capture.json"
    filings = _oos_filings()
    print(f"=== OOS RISK CAPTURE: {len(filings)} held-out filings (non-L1 types, agent-only) "
          f"WORKER_MODEL={WORKER_MODEL} ===\n")
    rows = []
    t0 = time.perf_counter()
    for i, f in enumerate(filings, 1):
        text, src = _acquire_text(f)
        if not text:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: NO TEXT"); continue
        try:
            res = run_specialized(f["acc"], text, synthesize=False)
        except Exception as e:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: FAIL {type(e).__name__}: {e}"); continue
        per_agent = {}
        for r in ROLES:
            per_agent[r] = ((res["base"][r]["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        for k, v in res["specialists"].items():
            per_agent[f"spec:{k}"] = ((v["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        rec = {
            "acc": f["acc"], "ticker": f["ticker"], "et": f["et"], "evdate": str(f["evdate"]),
            "text_src": src, "spawned": res["spawn_keys"],
            "per_agent_risk": per_agent,
            "current_flag": res["risk_channel"]["flag"],   # count2 (frozen default)
            "current_level": res["risk_channel"]["level"],
            "fwd_vol": _fwd_vol(f["ticker"], f["evdate"]),
        }
        rows.append(rec)
        print(f"[{i}/{len(filings)}] {f['ticker']:5} {f['et']:16} "
              f"base(b/b/s)={per_agent['bull']}/{per_agent['bear']}/{per_agent['skeptic']} "
              f"spawn={res['spawn_keys']} -> {rec['current_flag']}  "
              f"fwd_vol={rec['fwd_vol'] if rec['fwd_vol'] is None else round(rec['fwd_vol'],4)}")
    wall = time.perf_counter() - t0
    json.dump({"rows": rows, "wall_s": wall}, open(out_path, "w"), indent=2)
    print(f"\ncaptured {len(rows)} filings in {wall:.0f}s -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
