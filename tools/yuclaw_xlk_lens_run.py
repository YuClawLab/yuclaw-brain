#!/usr/bin/env python3
"""
XLK lens activation (post-flip consolidation Part C) — REGISTRY-FIRST.

XLK is the second sector lens, chosen because it passed the published
admission standard (EXPLORATORY, N_eff 5.58 on the 2026-07-29 issuer
holdings snapshot) — admission-standard-driven expansion, not popularity.

METHOD_SPEC (locked): the SMH multi-estimand CAR v2 estimator family
applied to the XLK covered sleeve — sleeve = XLK issuer-disclosed holdings
(data/holdings/XLK.json, dated) intersected with the 79-ticker scoring
universe; deduped accepted directional events with complete tau=+20
peer-model windows; E1 event / E2 issuer / E3 ETF / E4 capped-at-20%
weightings; issuer- and date-cluster bootstrap envelopes (wider of the two,
labeled conservative) AND the formal CGM two-way interval beside (small-G
guard, degeneracy disclosed); locked badges. B=4000, seed 20260731.
Secondary, ledger-counted, computed with the standing engine machinery
under THIS protocol: falsification battery (date-shuffle / sign-flip /
placebo, N=1000), evidence-geometry read (story clustering + N_eff), and
the per-type lifecycle table (n>=15 floor). Era split: backfill
(2026-02-18..2026-05-15) primary, matching the SMH convention; live
disclosed. Edits => supersession.
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

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import (LensFacts, WeightedClusteredCAR, admit,
                             cgm_two_way, coverage_anatomy, UncoveredSlice)
from yuclaw_falsification import TargetGrid, battery
from yuclaw_evidence_geometry import geometry
from yuclaw_evidence_lifecycle import type_path

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import (CAR_POST, CAR_PRE, EST_GAP, EST_MIN,
                                 EST_WIN, _universe)
from v3.lab.stats import ols

SEED = 20260731
BACKFILL_LO, BACKFILL_HI = date(2026, 2, 18), date(2026, 5, 15)
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "XLK multi-estimand CAR v1"
HOLD = json.loads((_REPO / "data" / "holdings" / "XLK.json").read_text())
PROTOCOL_PARAMS = {"lens": "XLK", "holdings_as_of": HOLD["as_of"],
                   "sleeve": "XLK issuer holdings x 79-ticker scoring universe",
                   "estimands": ["event", "issuer", "etf", "capped"],
                   "cap_pct_of_sleeve": 20, "car_horizon_tau": 20,
                   "B": 4000, "seed": SEED, "n_null": 1000}
OUT_JSON = _REPO / "output" / "oie" / "xlk_lens_run.json"


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("SMH-v2 estimator family on the XLK covered sleeve "
                          "(issuer holdings x scoring universe): E1-E4 with "
                          "conservative envelopes + formal CGM two-way; "
                          "falsification battery, geometry, and lifecycle "
                          "as ledgered secondaries under this protocol."),
            primary_endpoint=("E4 capped-ETF-weighted mean CAR at tau=+20d, "
                              "backfill era, conservative envelope"),
            secondary_endpoints=[
                "E1/E2/E3 envelopes + 4 formal two-way cells",
                "falsification battery (date-shuffle/sign-flip/placebo)",
                "evidence-geometry read (stories, N_eff, concentration)",
                "lifecycle per-type table (n>=15 floor)",
            ],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE computation")
    reg.assert_registered(pid)

    uni = set(_universe())
    cov_w = {t: w for t, w in HOLD["holdings"].items() if t in uni}
    covered = sorted(cov_w)
    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    grid = TargetGrid(covered, prices, td)

    # facts + admission (re-derived live)
    n_priced = sum(1 for t in covered if len(prices.get(t, {})) >= EST_MIN)
    facts = LensFacts(
        ticker="XLK", holdings_source=HOLD["source_url"],
        holdings_date=HOLD["as_of"], covered_issuers=len(covered),
        covered_weight_pct=round(sum(cov_w.values()), 2),
        covered_weights=sorted(cov_w.values(), reverse=True),
        price_coverage_pct=round(100 * n_priced / len(covered), 1),
        substrate_disclosed=True, reproduction_bundle=True,
        live_protocol_registered=True)
    verdict = admit(facts)
    unc = [(t, w) for t, w in HOLD["holdings"].items() if t not in uni]
    anatomy = coverage_anatomy(
        facts,
        [UncoveredSlice("outside the 79-ticker scoring universe",
                        round(sum(w for _t, w in unc), 2), len(unc)),
         UncoveredSlice("not disclosed / rounding residual",
                        round(100 - HOLD["weight_sum_pct"], 2), 1)],
        sorted(cov_w.items(), key=lambda kv: -kv[1]))

    # event set
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_type, direction,
                          event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND direction <> 0""", (covered,))
            evs = cur.fetchall()
    rows_bf, rows_all = [], []
    for tk, et, dirn, ev_date in evs:
        day0 = next((d for d in td if d >= ev_date), None)
        if day0 is None:
            continue
        v = grid.car20(tk, idx[day0])
        if v is None:
            continue
        row = (tk, idx[day0], int(dirn), v * int(dirn), et, ev_date)
        rows_all.append(row)
        if BACKFILL_LO <= ev_date <= BACKFILL_HI:
            rows_bf.append(row)

    ev4 = [(t, str(i), s) for t, i, _d, s, _et, _dt in rows_bf]
    est = {k: vars(v) for k, v in
           WeightedClusteredCAR(ev4, cov_w, B=4000, seed=SEED).run_all().items()}
    ev_tw = [(t, dt.isoformat(), s) for t, _i, _d, s, _et, dt in rows_bf]
    for kind in ("event", "issuer", "etf", "capped"):
        est[kind]["two_way"] = cgm_two_way(ev_tw, cov_w, kind)

    fals = battery("XLK", [(t, i, d, s) for t, i, d, s, _et, _dt in rows_bf],
                   grid, "capped", cov_w)
    geo = geometry([(t, i, et, s) for t, i, _d, s, et, _dt in rows_all],
                   "real:XLK-v1")

    # lifecycle per type (backfill, n>=15)
    paths: dict = {}
    for tk, i0, _d, _s, et, ev_date in rows_bf:
        est_days = td[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        pairs = [(grid.ret[tk].get(d), grid.peer[tk].get(d)) for d in est_days]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < EST_MIN:
            continue
        r = ols([a for a, _ in pairs], [b for _, b in pairs])
        if r is None:
            continue
        cum, rowp = 0.0, [None] * 21
        for tau in range(0, CAR_POST + 1):
            j = i0 + tau
            if j >= len(td):
                break
            d = td[j]
            rr, m = grid.ret[tk].get(d), grid.peer[tk].get(d)
            if rr is None or m is None:
                continue
            cum += rr - (r["alpha"] + r["beta"] * m)
            rowp[tau] = cum * 100.0
        if rowp[20] is not None:
            paths.setdefault(et, []).append(rowp)
    lifecycle = {}
    thin = {}
    for et, rws in sorted(paths.items(), key=lambda kv: -len(kv[1])):
        if len(rws) >= 15:
            tp = type_path(rws)
            tp["n"] = len(rws)
            lifecycle[et] = tp
        else:
            thin[et] = {"n": len(rws), "badge": "UNDERPOWERED"}

    payload = {
        "protocol_id": pid, "method_hash": METHOD_HASH,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "holdings": {"as_of": HOLD["as_of"],
                     "retrieved": HOLD["retrieved_utc"],
                     "n_holdings": HOLD["n_holdings"]},
        "facts": vars(facts), "verdict": verdict, "anatomy": anatomy,
        "n_events_backfill": len(rows_bf), "n_events_all": len(rows_all),
        "estimands": est, "falsification": fals, "geometry": geo,
        "lifecycle": lifecycle, "lifecycle_thin": thin,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"backfill era n={len(rows_bf)}, all-era n="
                     f"{len(rows_all)}, prices through {td[-1].isoformat()}"),
        n_primary_cells=1, n_secondary_cells=22, result_hash=rh,
        note=("XLK activation run: E1-E4 envelopes+two-way (7 sec cells) + "
              "falsification (3) + geometry (3) + lifecycle cells + "
              "admission facts.")))
    reg.verify_chain()
    print(f"[xlk] verdict={verdict['label']} N_eff={verdict['effective_issuers']} "
          f"events bf/all={len(rows_bf)}/{len(rows_all)}")
    for k in ("event", "issuer", "etf", "capped"):
        r = est[k]
        tw = r["two_way"]
        print(f"  {k:>7}: {r['mean_pct']:+.2f}% env{r['envelope']} "
              f"tw({tw['ci'][0]:+.2f},{tw['ci'][1]:+.2f}) [{r['badge']}]")
    print(f"  falsification: shuffle {fals['date_shuffle']['percentile_in_null']}, "
          f"flip {fals['sign_flip']['percentile_in_null']}, "
          f"placebo {fals['placebo_minus20d']['value_pct']}")
    print(f"  geometry: {geo['n_events']} events -> {geo['n_stories']} stories "
          f"-> N_eff {geo['n_eff_story']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
