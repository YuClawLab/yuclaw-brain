#!/usr/bin/env python3
"""
SMH multi-estimand CAR v3 upgrade (Part B close-out) — population
supersession: v2 (271e52f494c7) pinned the sleeve to "US EDGAR filers in
the 79-ticker universe"; the 2026-07-31 foreign-filer extension changes
that population, so the spec language REQUIRES supersession (checked, not
assumed). v3 inherits v2 verbatim plus the single sleeve amendment below.
Registered BEFORE recomputation on the extended sleeve.
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
from yuclaw_etf_lens import METHOD_SPEC_V2, WeightedClusteredCAR, cgm_two_way
from yuclaw_smh_lens_run import (SEED, breadth_states, facts_and_admission,
                                 render_preview, run_estimands)

from v3.lab.cohort_engine import load_prices
from v3.lab.etf_evidence import event_study

V3_AMENDMENT = """
AMENDMENT (v3, 2026-07-31): SLEEVE REDEFINITION (the only change). The
covered sleeve is SMH disclosed holdings intersected with (the 79-ticker
scoring universe UNION the smh_foreign evidence tier: ASML, NXPI, STM, TSM
— evidence coverage only, never scored). Foreign-filer events enter through
the same accepted/dedup/estimation rules; the peer model is the extended
sleeve. Historical statistics recorded under v1/v2 remain as recorded on
the 8-issuer sleeve and are never restated. All other clauses of v2
inherited verbatim."""
METHOD_SPEC_V3 = METHOD_SPEC_V2 + V3_AMENDMENT
METHOD_HASH_V3 = hashlib.sha256(METHOD_SPEC_V3.encode()).hexdigest()[:16]
PARAMS_V3 = {"lens": "SMH", "holdings_as_of": "2026-07-03",
             "sleeve": ("covered (US EDGAR filers in the 79-ticker universe "
                        "UNION smh_foreign evidence tier)"),
             "car_horizon_tau": 20, "car_window": [-5, 20], "ar_model": "peer",
             "alignment": "direction-aligned (AR x direction, direction != 0)",
             "primary_era": "backfill (2026-02-18..2026-05-15)",
             "estimands": ["event", "issuer", "etf", "capped"],
             "cap_pct_of_sleeve": 20, "B": 4000, "seed": SEED,
             "two_way": "CGM sandwich (issuer x date)"}
OUT_JSON = _REPO / "output" / "oie" / "smh_lens_run.json"


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC_V3, PARAMS_V3)
    if not reg.get_protocol(pid):
        reg.supersede("271e52f494c7", Protocol(
            protocol_id=pid, name="SMH multi-estimand CAR v3",
            method_hash=METHOD_HASH_V3,
            spec_summary=("v2 inherited verbatim; single amendment redefines "
                          "the sleeve to include the smh_foreign evidence "
                          "tier (ASML/NXPI/STM/TSM — evidence only, never "
                          "scored). v1/v2 numbers stand as recorded."),
            primary_endpoint=("E4 capped-ETF-weighted mean CAR at tau=+20d, "
                              "backfill era, conservative envelope (two-way "
                              "beside; inherited)"),
            secondary_endpoints=["E1/E2/E3 envelopes + two-way (inherited)",
                                 "sleeve-composition disclosure cells"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            version=3))
        reg.verify_chain()
        print(f"[registry] SUPERSESSION: {pid} (SMH v3) supersedes "
              f"271e52f494c7 — registered BEFORE recomputation")
    reg.assert_registered(pid)

    ov, facts, verdict, anatomy, top = facts_and_admission()
    br, states = breadth_states(ov)
    es = event_study()
    est = run_estimands(es)
    prices, td = load_prices()
    bf = [r for r in es["per_event_rows"] if r["era"] == "backfill"]
    ev = [(r["ticker"], r["date"], r["car20_peer_aligned_pct"]) for r in bf]
    for kind in ("event", "issuer", "etf", "capped"):
        est["backfill"][kind]["two_way"] = cgm_two_way(
            ev, ov["weights_covered"], kind)

    payload = json.loads(OUT_JSON.read_text())
    payload.update(protocol_id=pid, method_hash=METHOD_HASH_V3,
                   estimands=est, facts=vars(facts), verdict=verdict,
                   anatomy=anatomy,
                   built_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"extended sleeve ({ov['n_covered']} issuers, "
                     f"{ov['covered_weight_pct']}% weight), backfill era "
                     f"n={len(bf)}"),
        n_primary_cells=1, n_secondary_cells=19, result_hash=rh,
        note=("v3 activation on the extended sleeve; foreign-filer events "
              "included per the sleeve amendment.")))
    reg.verify_chain()
    render_preview(reg.get_protocol(pid), verdict, facts, anatomy, top,
                   br, states, est, es, "")
    print(f"[v3] sleeve {ov['n_covered']} issuers / "
          f"{ov['covered_weight_pct']}% · verdict {verdict['label']} "
          f"N_eff={verdict['effective_issuers']}")
    for k in ("event", "issuer", "etf", "capped"):
        r = est["backfill"][k]
        print(f"  {k:>7}: {r['mean_pct']:+.2f}% env{r['envelope']} "
              f"[{r['badge']}] n={r['n_events']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
