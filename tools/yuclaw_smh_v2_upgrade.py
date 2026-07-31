#!/usr/bin/env python3
"""
SMH multi-estimand CAR v2 upgrade (v5.2 Part 3c) — method extension via
SUPERSESSION: v1 (15052741ba2a) + the formal CGM two-way interval reported
beside the retained conservative envelope (yuclaw_etf_lens.V2_AMENDMENT,
verbatim in METHOD_SPEC_V2). Registers v2 BEFORE recomputation, recomputes
the estimand table with both intervals, records the run under v2, updates
the recorded artifact, and re-renders the SMH preview.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import (METHOD_HASH_V2, METHOD_SPEC_V2,
                             WeightedClusteredCAR, cgm_two_way)
from yuclaw_smh_lens_run import (PROTOCOL_PARAMS, SEED, breadth_states,
                                 facts_and_admission, render_preview,
                                 run_estimands)

from v3.lab.cohort_engine import load_prices
from v3.lab.etf_evidence import event_study

PARAMS_V2 = dict(PROTOCOL_PARAMS, two_way="CGM sandwich (issuer x date)")
OUT_JSON = _REPO / "output" / "oie" / "smh_lens_run.json"


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid_v2 = protocol_id(METHOD_SPEC_V2, PARAMS_V2)
    if not reg.get_protocol(pid_v2):
        reg.supersede("15052741ba2a", Protocol(
            protocol_id=pid_v2, name="SMH multi-estimand CAR v2",
            method_hash=METHOD_HASH_V2,
            spec_summary=("v1 inherited verbatim; amendment adds the formal "
                          "CGM two-way interval (V_issuer + V_date - "
                          "V_intersection, small-G guard, degeneracy "
                          "disclosed) beside the retained conservative "
                          "envelope."),
            primary_endpoint=("E4 capped-ETF-weighted mean CAR at tau=+20d, "
                              "backfill era, conservative envelope "
                              "(inherited; two-way reported beside)"),
            secondary_endpoints=["E1/E2/E3 envelopes (inherited)",
                                 "formal two-way cells, all four estimands"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            version=2))
        reg.verify_chain()
        print(f"[registry] SUPERSESSION: {pid_v2} (SMH multi-estimand CAR v2) "
              f"supersedes 15052741ba2a — registered BEFORE recomputation")
    reg.assert_registered(pid_v2)

    # recompute under v2
    ov, facts, verdict, anatomy, top = facts_and_admission()
    br, states = breadth_states(ov)
    es = event_study()
    est = run_estimands(es)

    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    bf = [r for r in es["per_event_rows"] if r["era"] == "backfill"]
    ev = []
    for r in bf:
        d0 = next((d for d in td if d >= date.fromisoformat(r["date"])), None)
        if d0 is not None:
            ev.append((r["ticker"], r["date"], r["car20_peer_aligned_pct"]))
    fund_w = ov["weights_covered"]
    for kind in ("event", "issuer", "etf", "capped"):
        est["backfill"][kind]["two_way"] = cgm_two_way(ev, fund_w, kind)

    payload = json.loads(OUT_JSON.read_text())
    payload["protocol_id"] = pid_v2
    payload["method_hash"] = METHOD_HASH_V2
    payload["estimands"] = est
    payload["built_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    line = reg.record_run(Run(
        protocol_id=pid_v2,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window="backfill era (v1 window), recomputed under v2",
        n_primary_cells=1, n_secondary_cells=19, result_hash=rh,
        note=("v2 activation: envelopes unchanged from v1 numbers; formal "
              "two-way cells added (4).")))
    reg.verify_chain()

    render_preview(reg.get_protocol(pid_v2), verdict, facts, anatomy, top,
                   br, states, est, es, line[:16])
    for kind in ("event", "issuer", "etf", "capped"):
        r = est["backfill"][kind]
        tw = r["two_way"]
        print(f"[{kind:>7}] mean={r['mean_pct']:+.2f}% env{r['envelope']} | "
              f"two-way CI({tw['ci'][0]:+.2f},{tw['ci'][1]:+.2f}) "
              f"G_min={tw['G_min']} [{tw['badge']}]"
              f"{' DEGENERATE' if tw['degenerate'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
