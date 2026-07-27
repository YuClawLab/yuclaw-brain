#!/usr/bin/env python3
"""
Concierge BYOS dry-run (commercial lane; internal proof, no revenue).

Simulates the CAD-5,000 pilot deliverable end-to-end on a SYNTHETIC client
lens, timing every stage:

  1. Synthetic client CSV (tickers from our own universe, clearly marked
     SYNTHETIC-CLIENT — no real client data exists or is implied).
  2. CLIENT-NAMESPACE registry: a SEPARATE chained JSONL under
     output/byos_dryrun/ (user_defined=true, non_canonical=true flags in the
     protocol record). The canonical public registry is NEVER touched by
     client work — namespace isolation is a design decision, recorded in the
     gap list. Registry-first ordering is preserved inside the client chain.
  3. Admission check (yuclaw_etf_lens standard, unchanged thresholds).
  4. Multi-estimand CAR (E1-E4) on the client basket's event set.
  5. Falsification battery (date-shuffle / sign-flip / placebo).
  6. Sample anatomy + deliverable memo (deterministic template,
     hash-stamped, non-canonical banner).

Everything lands in output/byos_dryrun/ (gitignored). Nothing public, nothing
canonical, nothing committed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import (LensFacts, WeightedClusteredCAR, admit,
                             effective_n)
from yuclaw_falsification import TargetGrid, battery

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import EST_MIN

OUT_DIR = _REPO / "output" / "byos_dryrun"
SEED = 20260727

CLIENT_SPEC = """CLIENT-LENS multi-estimand CAR (user_defined=true,
non_canonical=true). Same estimator family as canonical protocol 15052741ba2a
(E1-E4 weighted direction-aligned peer-model CAR at tau=+20, issuer/date
cluster envelopes, locked badges) applied to a user-supplied basket. The peer
model is the client basket itself (EW of the other members). Falsification:
date-shuffle / sign-flip / placebo per Falsification Battery v1 machinery,
N=1000. Not part of the canonical public record; results are research
classifications for the submitting user only."""


def now():
    return time.monotonic()


def main() -> int:
    t0 = now()
    stamps = {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. synthetic client CSV ------------------------------------------
    uni = json.loads((_REPO / "v3" / "universe.json").read_text())["equities"]
    rng = random.Random(SEED)
    picks = sorted(rng.sample(uni, 10))
    weights = [rng.uniform(3, 18) for _ in picks]
    tot = sum(weights)
    weights = [round(w / tot * 100, 2) for w in weights]
    csv_path = OUT_DIR / "client_input.csv"
    with csv_path.open("w", newline="") as f:
        f.write("# SYNTHETIC-CLIENT — generated dry-run input; no real client\n")
        w = csv.writer(f)
        w.writerow(["ticker", "weight_pct", "as_of", "client_note"])
        for tk, wt in zip(picks, weights):
            w.writerow([tk, wt, "2026-07-24", "synthetic thesis placeholder"])
    stamps["1_csv"] = now() - t0
    print(f"[byos] client CSV: {picks} (SYNTHETIC-CLIENT)")

    # ---- 2. client-namespace registry, registry-first ----------------------
    reg = Registry(str(OUT_DIR / "registry_client.jsonl"))
    params = {"user_defined": True, "non_canonical": True,
              "basket": picks, "weights": weights, "seed": SEED}
    pid = protocol_id(CLIENT_SPEC, params)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid,
            name="CLIENT-LENS synthetic pilot v1 [user_defined, non_canonical]",
            method_hash=hashlib.sha256(CLIENT_SPEC.encode()).hexdigest()[:16],
            spec_summary=CLIENT_SPEC.replace("\n", " "),
            primary_endpoint=("E4 capped-weighted mean CAR at +20d on the "
                              "client basket (conservative envelope)"),
            secondary_endpoints=["E1/E2/E3 envelopes",
                                 "falsification battery (3 tests)"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
    reg.verify_chain()
    stamps["2_registry"] = now() - t0
    print(f"[byos] client-chain protocol {pid} LOCKED (registry-first, "
          f"separate namespace file)")

    # ---- 3. admission -------------------------------------------------------
    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    n_priced = sum(1 for t in picks if len(prices.get(t, {})) >= EST_MIN)
    facts = LensFacts(
        ticker="CLIENT-SYNTH", holdings_source="SYNTHETIC-CLIENT CSV upload",
        holdings_date="2026-07-24", covered_issuers=len(picks),
        covered_weight_pct=100.0, covered_weights=weights,
        price_coverage_pct=round(100 * n_priced / len(picks), 1),
        substrate_disclosed=True, reproduction_bundle=False,
        live_protocol_registered=True)
    verdict = admit(facts)
    stamps["3_admission"] = now() - t0
    print(f"[byos] admission: {verdict['label']} "
          f"N_eff={verdict['effective_issuers']} reasons={verdict.get('reasons')}")

    # ---- 4. events + estimands ---------------------------------------------
    grid = TargetGrid(picks, prices, trade_dates)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, direction, event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND direction <> 0""", (picks,))
            evs = cur.fetchall()
    events = []
    for tk, d, ev_date in evs:
        day0 = next((dd for dd in trade_dates if dd >= ev_date), None)
        if day0 is None:
            continue
        v = grid.car20(tk, idx[day0])
        if v is not None:
            events.append((tk, idx[day0], int(d), v * int(d)))
    fund_w = dict(zip(picks, weights))
    ev4 = [(t, str(i), s) for t, i, _d, s in events]
    est = {k: vars(v) for k, v in
           WeightedClusteredCAR(ev4, fund_w, B=4000, seed=SEED).run_all().items()}
    stamps["4_estimands"] = now() - t0
    print(f"[byos] estimands on n={len(events)} events, "
          f"{len({t for t, *_ in events})} issuers")

    # ---- 5. falsification ---------------------------------------------------
    fals = battery("CLIENT-SYNTH", events, grid, "capped", fund_w)
    stamps["5_falsification"] = now() - t0

    # ---- 6. anatomy + memo ---------------------------------------------------
    per_issuer = {}
    for t, *_ in events:
        per_issuer[t] = per_issuer.get(t, 0) + 1
    results = {"facts": vars(facts), "verdict": verdict, "estimands": est,
               "falsification": fals, "events_per_issuer": per_issuer}
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2,
                                                     default=str))
    result_hash = hashlib.sha256(
        json.dumps(results, sort_keys=True, default=str).encode()).hexdigest()[:16]
    line = reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"client basket events through {trade_dates[-1].isoformat()}",
        n_primary_cells=1, n_secondary_cells=6, result_hash=result_hash,
        note="BYOS dry-run deliverable (synthetic client)."))
    reg.verify_chain()

    e4 = est["capped"]
    ds = fals["date_shuffle"]
    memo_lines = [
        "# Research Memo — Client-Defined Lens (PILOT DRY-RUN)",
        "",
        "> **User-defined research lens — not part of the canonical public "
        "record.** SYNTHETIC-CLIENT input; this memo is an internal "
        "dry-run artifact. Research classifications, not recommendations; "
        "not investment advice.",
        "",
        f"- Client chain: protocol `{pid}` · run line `{line[:16]}` · "
        f"result hash `{result_hash}`",
        f"- Basket: {', '.join(picks)} (10 names, synthetic weights)",
        "",
        "## 1 · Admission",
        f"Verdict: **{verdict['label']}** · effective issuers "
        f"{verdict['effective_issuers']} · reasons: "
        f"{verdict.get('reasons') or 'none'}",
        "",
        "## 2 · Sample anatomy",
        f"Directional events with complete +20d windows: {len(events)} across "
        f"{len(per_issuer)} issuers "
        f"({', '.join(f'{t}:{n}' for t, n in sorted(per_issuer.items(), key=lambda kv: -kv[1]))})",
        "",
        "## 3 · Multi-estimand CAR at +20d",
        "| Estimand | Mean | Envelope | Badge |",
        "|---|---|---|---|",
    ]
    for k, lbl in (("event", "E1 event"), ("issuer", "E2 issuer"),
                   ("etf", "E3 basket-weighted"), ("capped", "E4 capped (primary)")):
        r = est[k]
        memo_lines.append(f"| {lbl} | {r['mean_pct']:+.2f}% | "
                          f"({r['envelope'][0]:+.2f}, {r['envelope'][1]:+.2f}) | "
                          f"{r['badge']} |")
    memo_lines += [
        "",
        "## 4 · Falsification",
        f"Date-shuffle percentile {ds['percentile_in_null']:.3f} "
        f"(null {ds['null']['mean']:+.2f}±{ds['null']['sd']:.2f}); "
        f"sign-flip {fals['sign_flip']['percentile_in_null']:.3f}; "
        f"placebo −20d {fals['placebo_minus20d']['value_pct']} "
        f"(pct {fals['placebo_minus20d']['percentile_in_shuffle_null']}). "
        "Two-sided extremity; mid-range percentiles mean the value is "
        "unremarkable within its null.",
        "",
        "## 5 · Limitations",
        "- Peer model is the client basket itself; idiosyncratic basket "
        "composition shifts the abnormal-return baseline.",
        "- Badges are locked; UNDERPOWERED cells mean the basket cannot "
        "support standalone inference at current cluster counts.",
        "- No reproduction bundle in the pilot tier (gap item).",
        "",
    ]
    memo = "\n".join(memo_lines)
    memo += (f"\n---\nMemo hash: `{hashlib.sha256(memo.encode()).hexdigest()[:16]}` · "
             f"generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
             "deterministic template v1\n")
    (OUT_DIR / "CLIENT_MEMO.md").write_text(memo)
    stamps["6_memo"] = now() - t0

    print("[byos] memo written; stage wall-clock (cumulative seconds):")
    for k, v in stamps.items():
        print(f"    {k:>16}: {v:7.1f}s")
    print(f"[byos] TOTAL: {stamps['6_memo']:.1f}s")
    e4s = est["capped"]
    print(f"[byos] E4={e4s['mean_pct']:+.2f}% env{e4s['envelope']} "
          f"[{e4s['badge']}] · shuffle-pct={ds['percentile_in_null']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
