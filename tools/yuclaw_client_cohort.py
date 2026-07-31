#!/usr/bin/env python3
"""
User-defined cohorts in the client lab (E-tranche Part 4d).

A client defines a cohort as a ticker set (CSV: ticker[,weight_pct]) and
receives the full client-lab suite on it: client-namespace registration
(guarded chain), admission under the client standard (EXPLORATORY (CLIENT)
ceiling — existing ceilings apply unchanged), multi-estimand CAR with
envelopes, and the falsification battery. Everything lands in the given
output directory (box-local; gitignore it for real clients).

CLI: python3 tools/yuclaw_client_cohort.py <cohort.csv> <out_dir>
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import LensFacts, WeightedClusteredCAR, admit_client
from yuclaw_falsification import TargetGrid, battery

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import EST_MIN

SEED = 20260731

COHORT_SPEC = """CLIENT-COHORT suite (user_defined=true, non_canonical=true).
User-supplied ticker-set cohort analyzed with the standing client-lab
machinery: admission under the client standard (EXPLORATORY (CLIENT)
ceiling), E1-E4 direction-aligned peer-model CAR at tau=+20 with cluster
envelopes, falsification battery (date-shuffle / sign-flip / placebo,
N=1000). Peer model = the cohort itself. Not part of the canonical public
record; results are research classifications for the submitting user only."""


def load_cohort(path: Path):
    rows = []
    with path.open() as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    for r in csv.DictReader(lines):
        cols = {k.strip().lower(): (v or "").strip() for k, v in r.items()}
        if cols.get("ticker"):
            rows.append((cols["ticker"].upper(),
                         float(cols["weight_pct"]) if cols.get("weight_pct")
                         else None))
    tickers = [t for t, _w in rows]
    if any(w is not None for _t, w in rows):
        weights = {t: (w if w is not None else 0.0) for t, w in rows}
    else:
        weights = {t: 100.0 / len(tickers) for t in tickers}
    tot = sum(weights.values()) or 1
    return tickers, {t: round(100 * w / tot, 4) for t, w in weights.items()}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: yuclaw_client_cohort.py <cohort.csv> <out_dir>")
        return 2
    csv_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    tickers, weights = load_cohort(csv_path)
    print(f"[cohort] {len(tickers)} tickers: {tickers}")

    reg = Registry(str(out_dir / "registry_client.jsonl"), namespace="client")
    params = {"user_defined": True, "non_canonical": True,
              "cohort_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
              "tickers": tickers, "seed": SEED}
    pid = protocol_id(COHORT_SPEC, params)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid,
            name="CLIENT-COHORT suite v1 [user_defined, non_canonical]",
            method_hash=hashlib.sha256(COHORT_SPEC.encode()).hexdigest()[:16],
            spec_summary=COHORT_SPEC.replace("\n", " "),
            primary_endpoint="E4 capped-weighted mean CAR at +20d (envelope)",
            secondary_endpoints=["E1/E2/E3 envelopes",
                                 "falsification battery (3 tests)"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
    reg.verify_chain()
    reg.assert_registered(pid)

    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    n_priced = sum(1 for t in tickers if len(prices.get(t, {})) >= EST_MIN)
    facts = LensFacts(
        ticker="CLIENT-COHORT", holdings_source="client cohort CSV",
        holdings_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        covered_issuers=len(tickers), covered_weight_pct=100.0,
        covered_weights=sorted(weights.values(), reverse=True),
        price_coverage_pct=round(100 * n_priced / len(tickers), 1),
        substrate_disclosed=True, reproduction_bundle=True,
        live_protocol_registered=True)
    verdict = admit_client(facts)
    print(f"[cohort] admission: {verdict['label']} "
          f"N_eff={verdict['effective_issuers']}")

    grid = TargetGrid(tickers, prices, td)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, direction, event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND direction <> 0""", (tickers,))
            evs = cur.fetchall()
    events = []
    for tk, d, ev_date in evs:
        day0 = next((dd for dd in td if dd >= ev_date), None)
        if day0 is None:
            continue
        v = grid.car20(tk, idx[day0])
        if v is not None:
            events.append((tk, idx[day0], int(d), v * int(d)))
    if len(events) < 4:
        print(f"[cohort] only {len(events)} directional events with complete "
              "windows — estimands not computable; admission + counts only")
        est, fals = None, None
    else:
        ev4 = [(t, str(i), s) for t, i, _d, s in events]
        est = {k: vars(v) for k, v in
               WeightedClusteredCAR(ev4, weights, B=4000,
                                    seed=SEED).run_all().items()}
        fals = battery("CLIENT-COHORT", events, grid, "capped", weights)
        e4 = est["capped"]
        print(f"[cohort] E4={e4['mean_pct']:+.2f}% env{e4['envelope']} "
              f"[{e4['badge']}] · shuffle-pct="
              f"{fals['date_shuffle']['percentile_in_null']}")

    results = {"facts": vars(facts), "verdict": verdict, "estimands": est,
               "falsification": fals, "n_events": len(events)}
    (out_dir / "cohort_results.json").write_text(
        json.dumps(results, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(results, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"cohort events through {td[-1].isoformat()}",
        n_primary_cells=1, n_secondary_cells=6, result_hash=rh,
        note="client cohort suite run"))
    reg.verify_chain()
    print(f"[cohort] results -> {out_dir / 'cohort_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
