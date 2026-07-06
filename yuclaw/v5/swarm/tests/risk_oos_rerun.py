"""YUCLAW v5 Layer 1 — risk-channel OOS RE-RUN (June fuel matured; same check as 130579a5).

The 130579a5 check was INCONCLUSIVE: zero same-regime held-out filings existed (the L1
corpus == the 28-filing D5C tuning set; newest L1 event 2026-06-02). Since then, June
L1-type filings (reclassify rescues + live ingestion) have accrued forward history.

This re-run applies the EXACT frozen config (YUCLAW_RISK_AGG=count2 default, unchanged
since c28f8542 — verified) to the held-out batch:

  HELD-OUT = L1-type filings (corrected types) with event date > 2026-06-02, i.e.
  strictly after the newest tuning-set event, so the batch is disjoint from the D5C 28
  by construction. NOTHING is re-tuned; the forward-vol outcome is the frozen _fwd_vol
  (up to 20 trading days, >= 5 returns required). Filings whose 20-day window has not
  fully matured are included per the frozen outcome function with their actual forward
  trading-day count DISCLOSED per row.

  TEXT PATH = production as of v5.0 (b1b153a0): _acquire_text reads persisted
  swarm_inputs prose first ('existing'), then the exhibit extractor, then raw_cover.

  PIPELINE = full production shape: Gemma worker base agents + spawned specialists +
  count2 risk channel + 70B synthesis (synthesize=True), exactly as shipped.

Verdict logic is pre-committed (same as 130579a5): PASS = elevated rare (~20-40%) AND
correctly signed (mean fwd vol elevated > normal) with a real normal arm; INCONCLUSIVE
= arms too thin; FAIL = sign flips.

Agent-only side effects: none (persist=False; public.* read-only).
Usage: python3 -m yuclaw.v5.swarm.tests.risk_oos_rerun [out.json]
"""

from __future__ import annotations

import json
import sys
import time

import psycopg2

from yuclaw.v5.swarm.tests.validate_scale import _acquire_text, _fwd_vol, _preflight
from yuclaw.v5.swarm.specialized import run_specialized, ROLES, _RISK_AGG
from yuclaw.v5.swarm.worker import WORKER_MODEL

TUNING_SET_MAX_DATE = "2026-06-02"   # newest event in the D5C 28-filing tuning set
L1_TYPES = ("EARNINGS_RESULT", "EARNINGS_BEAT", "GUIDANCE_RAISE", "GUIDANCE_CUT",
            "M_AND_A", "FINANCING", "GOVERNANCE", "REGULATORY_ACTION")


def _held_out() -> list[dict]:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("""
        SELECT DISTINCT er.accession_number AS acc, er.ticker, er.source_type AS form,
               e.event_time::date AS evdate,
               COALESCE(c.corrected_event_type, e.event_type) AS et,
               (SELECT count(*) FROM public.price_history p
                 WHERE p.ticker = er.ticker AND p.trade_date > e.event_time::date) AS fwd_td
        FROM public.events e JOIN public.events_raw er ON er.source_url = e.source_url
        LEFT JOIN yuclaw_v5.event_type_corrected c ON c.event_id = e.event_id
        WHERE e.event_id NOT LIKE 'CASCADE%%'
          AND COALESCE(c.corrected_event_type, e.event_type) IN %s
          AND e.event_time::date > %s
        ORDER BY evdate, ticker""", (L1_TYPES, TUNING_SET_MAX_DATE))
    rows = [{"acc": a, "ticker": t, "form": fm, "evdate": d, "et": et, "fwd_td": int(n)}
            for a, t, fm, d, et, n in cur.fetchall()]
    cn.close()
    return rows


def main() -> int:
    _preflight()
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/oos_rerun.json"
    filings = _held_out()
    print(f"=== OOS RE-RUN: {len(filings)} held-out L1-type filings (evdate > {TUNING_SET_MAX_DATE}) "
          f"RISK_AGG={_RISK_AGG} WORKER={WORKER_MODEL} synth=ON ===\n")
    rows = []
    t0 = time.perf_counter()
    for i, f in enumerate(filings, 1):
        text, src = _acquire_text(f)
        if not text:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: NO TEXT"); continue
        try:
            res = run_specialized(f["acc"], text, synthesize=True)
        except Exception as e:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: FAIL {type(e).__name__}: {e}")
            continue
        per_agent = {}
        for r in ROLES:
            per_agent[r] = ((res["base"][r]["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        for k, v in res["specialists"].items():
            per_agent[f"spec:{k}"] = ((v["output"].get("risk_view") or {}).get("level") or "").strip().lower() or None
        rec = {
            "acc": f["acc"], "ticker": f["ticker"], "et": f["et"], "evdate": str(f["evdate"]),
            "fwd_td": f["fwd_td"], "text_src": src, "spawned": res["spawn_keys"],
            "per_agent_risk": per_agent,
            "flag": res["risk_channel"]["flag"],       # count2, frozen
            "level": res["risk_channel"]["level"],
            "synth_ok": bool((res.get("synthesis") or {}).get("output")),
            "fwd_vol": _fwd_vol(f["ticker"], f["evdate"]),
        }
        rows.append(rec)
        print(f"[{i}/{len(filings)}] {f['ticker']:5} {f['et']:16} src={src:9} "
              f"spawn={res['spawn_keys']} flag={rec['flag']} "
              f"fwd_vol={'-' if rec['fwd_vol'] is None else round(rec['fwd_vol'], 4)} "
              f"(fwd_td={f['fwd_td']}) synth={'ok' if rec['synth_ok'] else 'MISSING'}",
              flush=True)
    wall = time.perf_counter() - t0

    # pre-committed verdict arithmetic (flag is the string "elevated" | "normal")
    scored = [r for r in rows if r["fwd_vol"] is not None]
    elev = [r for r in scored if r["flag"] == "elevated"]
    norm = [r for r in scored if r["flag"] == "normal"]
    summary = {
        "n_run": len(rows), "n_scored": len(scored),
        "n_elevated": len(elev), "n_normal": len(norm),
        "elevated_rate": round(len(elev) / len(scored), 3) if scored else None,
        "mean_vol_elevated": (round(sum(r["fwd_vol"] for r in elev) / len(elev), 5) if elev else None),
        "mean_vol_normal": (round(sum(r["fwd_vol"] for r in norm) / len(norm), 5) if norm else None),
        "risk_agg": _RISK_AGG, "worker_model": WORKER_MODEL,
    }
    print(f"\nSUMMARY: {json.dumps(summary, indent=1)}")
    json.dump({"rows": rows, "summary": summary, "wall_s": wall}, open(out_path, "w"), indent=2)
    print(f"captured {len(rows)} filings in {wall:.0f}s -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
