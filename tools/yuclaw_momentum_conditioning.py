#!/usr/bin/env python3
"""
Pre-event momentum conditioning v1 (ORDER sharper-hypothesis Part B) —
REGISTRY-FIRST.

Tests whether the era-generic adverse alignment (the −6.72% date-shuffle null
mean) is momentum continuation wearing an event costume: if the adverse
aligned CAR concentrates in events on issuers that had ALREADY outperformed
their peer basket before the event (insiders sell winners; winners keep
winning vs peers), momentum conditioning explains the effect.

Momentum (pre-committed): relative pre-event momentum = compounded issuer
return minus compounded EW-peer-basket return over trading days
[day0−W, day0−1], W=60 primary (>=40 usable paired days required) and W=20
variant (>=14 required); events failing the data requirement are excluded
and counted. Within each target's event set, events are split at the MEDIAN
relative momentum (halves; median disclosed). Statistic per half: the
target's own registered estimand (SMH: E4 capped-ETF weights; Canada lenses:
pooled event-weighted mean) of direction-aligned peer-model CAR at tau=+20.
Difference = outperformed-half minus underperformed-half, with issuer- and
date-cluster bootstrap CIs on the difference (union resample; replicates
missing a half are dropped and counted) and the conservative envelope.
B=4000, seed 20260727. Backfill era for SMH (parent-estimand consistency);
full observed event sets for the Canada lenses (their published pooled
statistic's window).
"""
from __future__ import annotations

import hashlib
import json
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
from yuclaw_falsification import TargetGrid, daily_returns

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import (canada_lens_holdings, event_study,
                                 overlap_summary)

SEED = 20260727
B = 4000
WINDOWS = {60: 40, 20: 14}   # window -> min usable paired days
REGISTRY_PATH = str(_REPO / "registry" / "protocols.jsonl")
OUT_JSON = _REPO / "output" / "oie" / "momentum_conditioning.json"

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Pre-event momentum conditioning v1"
PROTOCOL_PARAMS = {"targets": ["SMH-E4", "XEG", "ZEO", "GDX", "URNM"],
                   "windows": [60, 20], "split": "median halves",
                   "horizon_tau": 20, "B": B, "seed": SEED}
CANADA = ("XEG", "ZEO", "GDX", "URNM")


def register_first(reg):
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if (p := reg.get_protocol(pid)):
        print(f"[registry] protocol {pid} already LOCKED (idempotent rerun)")
        return p
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=("Median split of each target's registered pooled CAR "
                      "estimand by prior-60d (and 20d) issuer-vs-peer relative "
                      "momentum; outperformed-minus-underperformed difference "
                      "with issuer+date cluster CIs and envelope."),
        primary_endpoint=("SMH E4 estimand: outperformed-half minus "
                          "underperformed-half difference at W=60, backfill "
                          "era, conservative envelope"),
        secondary_endpoints=[
            "SMH per-half E4 values with envelopes (2 cells)",
            "SMH W=20 variant (diff + halves, 3 cells)",
            "XEG/ZEO/GDX/URNM pooled-CAR diff at W=60 and W=20 (8 cells)",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — registered BEFORE computation")
    return reg.get_protocol(pid)


def rel_momentum(grid: TargetGrid, tk: str, i0: int, W: int, min_days: int):
    """Compounded issuer minus compounded peer return over [i0-W, i0-1]."""
    if i0 - W < 0:
        return None
    c_tk = c_pr = 1.0
    used = 0
    for j in range(i0 - W, i0):
        d = grid.dates[j]
        r, m = grid.ret[tk].get(d), grid.peer[tk].get(d)
        if r is None or m is None:
            continue
        c_tk *= 1 + r
        c_pr *= 1 + m
        used += 1
    if used < min_days:
        return None
    return (c_tk - c_pr) * 100.0


def stat_fn(kind, fund_w):
    def f(events):   # [(tk, key, car)]
        if not events:
            return None
        if kind == "capped":
            wc = WeightedClusteredCAR(events, fund_w, B=1, seed=SEED)
            w = wc._weights(events, "capped")
            sw = sum(w)
            return sum(wi * c for wi, (_, _, c) in zip(w, events)) / sw if sw else None
        return sum(c for _, _, c in events) / len(events)
    return f


def condition(events, grid, W, min_days, kind, fund_w, tag):
    """events: [(tk, i0, car_signed)]. Returns dict for one (target, window)."""
    with_mom, dropped = [], 0
    for tk, i0, car in events:
        m = rel_momentum(grid, tk, i0, W, min_days)
        if m is None:
            dropped += 1
        else:
            with_mom.append((tk, i0, car, m))
    if len(with_mom) < 4:
        return {"n_usable": len(with_mom), "n_dropped": dropped,
                "note": "too few events with momentum data"}
    moms = sorted(m for *_x, m in with_mom)
    median = moms[len(moms) // 2] if len(moms) % 2 else \
        (moms[len(moms) // 2 - 1] + moms[len(moms) // 2]) / 2
    hi = [(t, i, c) for t, i, c, m in with_mom if m > median]
    lo = [(t, i, c) for t, i, c, m in with_mom if m <= median]
    sf = stat_fn(kind, fund_w)
    ev = lambda xs: [(t, str(i), c) for t, i, c in xs]
    v_hi, v_lo = sf(ev(hi)), sf(ev(lo))
    diff = v_hi - v_lo

    def boot(cluster_idx):
        byk_h, byk_l = {}, {}
        for t, i, c in hi:
            byk_h.setdefault((t, i)[cluster_idx], []).append((t, str(i), c))
        for t, i, c in lo:
            byk_l.setdefault((t, i)[cluster_idx], []).append((t, str(i), c))
        keys = sorted(set(byk_h) | set(byk_l))
        rng = random.Random(f"{SEED}:mom:{tag}:{cluster_idx}")
        reps, drop = [], 0
        for _ in range(B):
            sh, sl = [], []
            for _ in keys:
                k = keys[rng.randrange(len(keys))]
                sh += byk_h.get(k, [])
                sl += byk_l.get(k, [])
            if not sh or not sl:
                drop += 1
                continue
            a, b2 = sf(sh), sf(sl)
            if a is not None and b2 is not None:
                reps.append(a - b2)
        reps.sort()
        return ((reps[int(0.025 * len(reps))], reps[int(0.975 * len(reps)) - 1]),
                drop)

    ci_i, dr_i = boot(0)
    ci_d, dr_d = boot(1)
    return {
        "n_usable": len(with_mom), "n_dropped": dropped,
        "median_rel_momentum_pct": round(median, 2),
        "outperformed": {"n": len(hi), "value_pct": round(v_hi, 3)},
        "underperformed": {"n": len(lo), "value_pct": round(v_lo, 3)},
        "difference": {"value": round(diff, 3),
                       "issuer_ci": [round(x, 2) for x in ci_i],
                       "date_ci": [round(x, 2) for x in ci_d],
                       "envelope": [round(min(ci_i[0], ci_d[0]), 2),
                                    round(max(ci_i[1], ci_d[1]), 2)],
                       "replicates_dropped": {"issuer": dr_i, "date": dr_d}},
    }


def main() -> int:
    reg = Registry(REGISTRY_PATH)
    proto = register_first(reg)
    reg.assert_registered(proto["protocol_id"])

    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    out = {}

    # SMH (E4, backfill directional set)
    ov = overlap_summary()
    grid = TargetGrid(ov["covered"], prices, trade_dates)
    smh_events = []
    for r in event_study()["per_event_rows"]:
        if r["era"] != "backfill":
            continue
        d0 = next((d for d in trade_dates if d >= date.fromisoformat(r["date"])), None)
        if d0 is not None:
            smh_events.append((r["ticker"], idx[d0], r["car20_peer_aligned_pct"]))
    out["SMH-E4"] = {f"W{W}": condition(smh_events, grid, W, mn, "capped",
                                        ov["weights_covered"], f"SMH:{W}")
                     for W, mn in WINDOWS.items()}

    # Canada lenses (pooled event-weighted)
    for lens in CANADA:
        covered = sorted(canada_lens_holdings()[lens])
        g = TargetGrid(covered, prices, trade_dates)
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ticker, direction, event_time::date
                       FROM events WHERE event_status='accepted'
                         AND ticker = ANY(%s) AND direction <> 0""", (covered,))
                evs = cur.fetchall()
        lens_events = []
        for tk, dirn, ev_date in evs:
            d0 = next((dd for dd in trade_dates if dd >= ev_date), None)
            if d0 is None:
                continue
            v = g.car20(tk, idx[d0])
            if v is not None:
                lens_events.append((tk, idx[d0], v * int(dirn)))
        out[lens] = {f"W{W}": condition(lens_events, g, W, mn, "event", {},
                                        f"{lens}:{W}")
                     for W, mn in WINDOWS.items()}

    payload = {"protocol_id": proto["protocol_id"], "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "results": out}
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    line = reg.record_run(Run(
        protocol_id=proto["protocol_id"],
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=("SMH backfill set + 4 lens sets, prices through "
                     + trade_dates[-1].isoformat()),
        n_primary_cells=1, n_secondary_cells=13, result_hash=result_hash,
        note=("Sharper-hypothesis Part B. Primary = SMH W=60 diff envelope. "
              "Secondary = SMH halves (2) + SMH W=20 (3) + lens diffs 4x2 (8)."),
    ))
    reg.verify_chain()
    print(f"[registry] run recorded, line {line[:16]}…, chain OK")

    for tgt, ws in out.items():
        for wk, r in ws.items():
            if "difference" not in r:
                print(f"[{tgt} {wk}] {r}")
                continue
            d = r["difference"]
            print(f"[{tgt} {wk}] median-mom={r['median_rel_momentum_pct']:+.1f}%  "
                  f"out={r['outperformed']['value_pct']:+.2f}% (n={r['outperformed']['n']})  "
                  f"under={r['underperformed']['value_pct']:+.2f}% (n={r['underperformed']['n']})  "
                  f"diff={d['value']:+.2f}pp env({d['envelope'][0]:+.2f},{d['envelope'][1]:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
