#!/usr/bin/env python3
"""
Matched-control CAR v1 (review-completion Part E) — REGISTRY-FIRST.
Is it the events, or the kind of stocks that have them?

METHOD_SPEC (locked):
  Population: the SMH v3 extended-sleeve backfill event set (the registered
  da44ba9fae79 population). For each event (issuer i, day0 d):
  CONTROL SELECTION (deterministic): among candidate issuer-days (j, d) in
  the SAME sleeve on the SAME day0 d, j != i, where issuer j has NO accepted
  event with day0 within +/-10 trading days of d, choose the candidate
  minimizing the Euclidean distance in standardized (prior-60-trading-day
  return, trailing-20d daily vol) — factors computed exactly as in the
  momentum/robustness protocols; candidates missing either factor or a
  complete [-5,+20] CAR path are ineligible. Events with zero eligible
  candidates are EXCLUDED and counted. Same-day matching removes the
  calendar factor by construction.
  STATISTIC: per pair, event-aligned CAR minus (control CAR x event
  direction) at tau=+20 (the control path is aligned with the event's
  hypothesized direction so the difference reads as event-specific
  alignment). E4 capped-ETF weights over the event issuers. PRIMARY
  (single): matched-control-adjusted E4 at +20d, issuer-clustered
  percentile CI (B=4000, seed 20260801). Secondary: E1 event-weighted
  adjusted mean; per-pair diagnostics (median match distance); exclusion
  count. Badges locked as standing. Edits => supersession.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import WeightedClusteredCAR
from yuclaw_falsification import TargetGrid
from yuclaw_momentum_conditioning import rel_momentum

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import event_study, overlap_summary

SEED = 20260801
B = 4000
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Matched-control CAR v1"
PROTOCOL_PARAMS = {"population": "SMH v3 extended sleeve, backfill era",
                   "match_factors": ["mom60", "vol20"],
                   "exclusion_window_td": 10, "B": B, "seed": SEED}
OUT_JSON = _REPO / "output" / "oie" / "matched_control.json"


def vol20(grid, tk, i0):
    w = [grid.ret[tk].get(grid.dates[j]) for j in range(max(0, i0 - 20), i0)]
    w = [x for x in w if x is not None]
    if len(w) < 15:
        return None
    m = sum(w) / len(w)
    return math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Same-day nearest-neighbor controls (momentum+vol "
                          "standardized, event-free within +/-10td) for each "
                          "SMH v3 backfill event; matched-control-adjusted "
                          "E4 at +20d with issuer-clustered CI."),
            primary_endpoint=("matched-control-adjusted E4 capped-ETF-"
                              "weighted mean CAR at +20d, issuer-clustered CI"),
            secondary_endpoints=["adjusted E1 event-weighted mean",
                                 "match diagnostics + exclusion count"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE computation")
    reg.assert_registered(pid)

    ov = overlap_summary()
    covered, fund_w = ov["covered"], ov["weights_covered"]
    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    grid = TargetGrid(covered, prices, td)

    # all event day0 indices per issuer (for the event-free window rule)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_time::date FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)""",
                (covered,))
            ev_days: dict = {}
            for tk, d in cur.fetchall():
                day0 = next((x for x in td if x >= d), None)
                if day0 is not None:
                    ev_days.setdefault(tk, set()).add(idx[day0])

    rows = [r for r in event_study()["per_event_rows"] if r["era"] == "backfill"]
    # factor standardization over all candidate observations
    def factors(tk, i0):
        m = rel_momentum(grid, tk, i0, 60, 40)
        v = vol20(grid, tk, i0)
        return (m, v) if None not in (m, v) else None

    pairs, excluded, dists = [], 0, []
    fac_cache: dict = {}
    all_f = []
    ev_list = []
    for r in rows:
        d0 = next((d for d in td if d >= date.fromisoformat(r["date"])), None)
        if d0 is None:
            continue
        i0 = idx[d0]
        ev_list.append((r["ticker"], i0, r["direction"],
                        r["car20_peer_aligned_pct"]))
        for tk in covered:
            key = (tk, i0)
            if key not in fac_cache:
                fac_cache[key] = factors(tk, i0)
            if fac_cache[key] is not None:
                all_f.append(fac_cache[key])
    mm = [f[0] for f in all_f]
    vv = [f[1] for f in all_f]
    mu_m, mu_v = sum(mm) / len(mm), sum(vv) / len(vv)
    sd_m = (sum((x - mu_m) ** 2 for x in mm) / len(mm)) ** 0.5 or 1.0
    sd_v = (sum((x - mu_v) ** 2 for x in vv) / len(vv)) ** 0.5 or 1.0

    for tk, i0, dirn, car in ev_list:
        fe = fac_cache.get((tk, i0))
        if fe is None:
            excluded += 1
            continue
        best, best_d = None, None
        for cj in covered:
            if cj == tk:
                continue
            if any(abs(i0 - e) <= 10 for e in ev_days.get(cj, ())):
                continue
            fc = fac_cache.get((cj, i0))
            if fc is None:
                continue
            c_car = grid.car20(cj, i0)
            if c_car is None:
                continue
            dist = math.hypot((fe[0] - fc[0]) / sd_m, (fe[1] - fc[1]) / sd_v)
            if best_d is None or dist < best_d:
                best, best_d = (cj, c_car), dist
        if best is None:
            excluded += 1
            continue
        adj = car - best[1] * dirn
        pairs.append((tk, str(i0), adj))
        dists.append(best_d)

    def stat(kind, ev):
        wc = WeightedClusteredCAR(ev, fund_w, B=1, seed=SEED)
        w = wc._weights(ev, kind)
        sw = sum(w)
        return sum(wi * c for wi, (_t, _x, c) in zip(w, ev)) / sw if sw else None

    e4 = stat("capped", pairs)
    e1 = stat("event", pairs)
    by: dict = {}
    for t, i, c in pairs:
        by.setdefault(t, []).append((t, i, c))
    keys = sorted(by)
    rng = random.Random(f"{SEED}:mc")
    reps = []
    for _ in range(B):
        s = []
        for _ in keys:
            s += by[keys[rng.randrange(len(keys))]]
        v = stat("capped", s)
        if v is not None:
            reps.append(v)
    reps.sort()
    ci = (round(reps[int(0.025 * len(reps))], 2),
          round(reps[int(0.975 * len(reps)) - 1], 2))
    G = len(keys)
    badge = ("UNDERPOWERED" if G < 8 or len(pairs) < 10 else
             "DESCRIPTIVE" if ci[0] <= 0 <= ci[1] else "PRELIMINARY")
    dists.sort()
    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "n_pairs": len(pairs), "n_excluded": excluded, "G_issuers": G,
               "median_match_distance": round(dists[len(dists) // 2], 3) if dists else None,
               "adjusted_E4": {"mean_pct": round(e4, 2), "ci": ci,
                               "badge": badge},
               "adjusted_E1_mean_pct": round(e1, 2)}
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"SMH v3 backfill, {len(pairs)} matched pairs "
                    f"({excluded} excluded)",
        n_primary_cells=1, n_secondary_cells=3, result_hash=rh,
        note=(f"Matched-control activation: adjusted E4 {e4:+.2f}% CI {ci} "
              f"[{badge}]; median match distance "
              f"{payload['median_match_distance']}.")))
    reg.verify_chain()
    print(f"[matched] pairs={len(pairs)} excluded={excluded} G={G} "
          f"median-dist={payload['median_match_distance']}")
    print(f"[primary] adjusted E4 = {e4:+.2f}% CI{ci} [{badge}] · "
          f"adjusted E1 = {e1:+.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
