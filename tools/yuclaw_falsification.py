#!/usr/bin/env python3
"""
Falsification Battery v1 (ORDER v5.1 Part B) — REGISTRY-FIRST.

Targets (all direction-aligned peer-model CAR at tau=+20):
  SMH  : E4 capped-ETF-weighted mean over the backfill-era covered-sleeve
         event set (2026-02-18..2026-05-15) — the registered SMH primary
         estimand (protocol 15052741ba2a).
  XEG / ZEO / GDX / URNM : pooled event-weighted mean over each lens's
         directional event set — the published lens statistic
         (per tools/yuclaw_synthesis_run.per_event_cars, mirrored exactly:
         missing days skipped with `continue`; an event enters the +20 pool
         only if tau=+20 itself has returns).

Tests per target (N=1000 per null, seed 20260727):
  T1 date-shuffle null (PRIMARY for SMH): each event's day0 is resampled
     uniformly from its ticker's eligible day0 grid — estimation window
     >= 30 paired obs, tau=+20 reachable, day0 inside the target's observed
     event-date support [min real day0, max real day0]. Unsigned grid CAR
     x the event's real direction; statistic recomputed per replicate.
     Report: percentile of the real value in the null.
  T2 direction-permutation null: independent Rademacher sign flips on the
     per-event aligned CARs (equivalent to flipping hypothesized direction).
     Observed directions are nearly all -1, so permuting direction labels
     is degenerate; the sign-flip variant is the informative one — stated.
  T3 pre-event placebo (-20 trading days): every day0 shifted back 20
     trading days; events whose shifted day0 is ineligible are dropped and
     counted; the placebo statistic is reported and located within the T1
     null distribution.

Extremity is read two-sided: percentiles near 0 and near 100 are both
extreme. All cells exploratory and ledger-counted except the registered
primary (SMH T1 percentile).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import WeightedClusteredCAR

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import (CAR_PRE, CAR_POST, EST_GAP, EST_MIN, EST_WIN,
                                 canada_lens_holdings, event_study,
                                 overlap_summary)
from v3.lab.stats import ols

SEED = 20260727
N_NULL = 1000
REGISTRY_PATH = str(_REPO / "registry" / "protocols.jsonl")
OUT_JSON = _REPO / "output" / "oie" / "falsification_run.json"

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Falsification Battery v1"
PROTOCOL_PARAMS = {
    "targets": ["SMH-E4", "XEG", "ZEO", "GDX", "URNM"],
    "horizon_tau": 20, "n_null": N_NULL, "seed": SEED,
    "tests": ["date-shuffle", "direction-sign-flip", "placebo-minus-20d"],
}

CANADA = ("XEG", "ZEO", "GDX", "URNM")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def register_first(reg: Registry) -> dict:
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if (p := reg.get_protocol(pid)):
        print(f"[registry] protocol {pid} already LOCKED (idempotent rerun)")
        return p
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=(
            "Date-shuffle, direction-sign-flip, and -20d placebo nulls for "
            "the SMH E4 estimand and each Canada lens pooled CAR at +20d. "
            "N=1000 per null, seed 20260727; day0 grids restricted to each "
            "target's observed event-date support; two-sided extremity."),
        primary_endpoint=(
            "event-date-shuffle null percentile of the SMH E4 capped-ETF-"
            "weighted mean CAR at +20d (backfill era)"),
        secondary_endpoints=[
            "SMH direction-sign-flip null percentile",
            "SMH -20d placebo value + location in date-shuffle null",
            "XEG/ZEO/GDX/URNM pooled CAR: date-shuffle percentile each",
            "XEG/ZEO/GDX/URNM pooled CAR: sign-flip percentile each",
            "XEG/ZEO/GDX/URNM pooled CAR: -20d placebo each",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — registered BEFORE computation")
    return reg.get_protocol(pid)


# ------------------------------------------------------------ CAR machinery
def daily_returns(px, dates):
    out, prev = {}, None
    for d in dates:
        p = px.get(d)
        if p is not None and prev is not None and prev != 0:
            out[d] = p / prev - 1.0
        if p is not None:
            prev = p
    return out


class TargetGrid:
    """Unsigned aligned CAR at +20 for every eligible (ticker, i0) of a
    covered group — mirrors per_event_cars exactly (continue on missing,
    +20 must print)."""

    def __init__(self, covered, prices, trade_dates):
        self.covered = covered
        self.dates = trade_dates
        self.idx = {d: i for i, d in enumerate(trade_dates)}
        self.ret = {tk: daily_returns(prices.get(tk, {}), trade_dates)
                    for tk in covered}
        self.peer = {}
        for tk in covered:
            others = [o for o in covered if o != tk]
            pr = {}
            for d in trade_dates:
                vals = [self.ret[o].get(d) for o in others]
                vals = [v for v in vals if v is not None]
                if vals:
                    pr[d] = sum(vals) / len(vals)
            self.peer[tk] = pr
        self._car = {}   # (tk, i0) -> unsigned car20 (pct) or None

    def car20(self, tk, i0):
        key = (tk, i0)
        if key in self._car:
            return self._car[key]
        val = self._compute(tk, i0)
        self._car[key] = val
        return val

    def _compute(self, tk, i0):
        if not (0 <= i0 and i0 + CAR_POST < len(self.dates)):
            return None
        est = self.dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        pairs = [(self.ret[tk].get(d), self.peer[tk].get(d)) for d in est]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < EST_MIN:
            return None
        reg = ols([a for a, _ in pairs], [b for _, b in pairs])
        if reg is None:
            return None
        cum, printed20 = 0.0, False
        for tau in range(-CAR_PRE, CAR_POST + 1):
            j = i0 + tau
            if not (0 <= j < len(self.dates)):
                break
            d = self.dates[j]
            r, m = self.ret[tk].get(d), self.peer[tk].get(d)
            if r is None or m is None:
                continue
            cum += r - (reg["alpha"] + reg["beta"] * m)
            if tau == CAR_POST:
                printed20 = True
        return round(cum * 100.0, 4) if printed20 else None

    def eligible(self, tk, lo, hi):
        return [i for i in range(lo, hi + 1) if self.car20(tk, i) is not None]


def battery(name, events, grid, weight_kind, fund_w, dropped_note=""):
    """events: [(ticker, i0, direction, signed_car_pct)]. Returns panel dict."""
    def stat(cars):
        if weight_kind == "capped":
            ev = [(t, str(i), c) for (t, i, _d, _s), c in zip(events, cars)]
            wc = WeightedClusteredCAR(ev, fund_w, B=1, seed=SEED)
            w = wc._weights(ev, "capped")
            sw = sum(w)
            return sum(wi * c for wi, c in zip(w, cars)) / sw if sw else 0.0
        return sum(cars) / len(cars)

    real_cars = [s for (_t, _i, _d, s) in events]
    real = stat(real_cars)

    lo = min(i for _t, i, _d, _s in events)
    hi = max(i for _t, i, _d, _s in events)
    elig = {tk: grid.eligible(tk, lo, hi)
            for tk in sorted({t for t, _i, _d, _s in events})}

    rng = random.Random(f"{SEED}:shuffle:{name}")
    null_shuffle = []
    for _ in range(N_NULL):
        cars = []
        for tk, _i, d, _s in events:
            pool = elig[tk]
            i_new = pool[rng.randrange(len(pool))]
            cars.append(grid.car20(tk, i_new) * d)
        null_shuffle.append(stat(cars))
    pct_shuffle = sum(1 for v in null_shuffle if v < real) / N_NULL

    rng2 = random.Random(f"{SEED}:signflip:{name}")
    null_flip = []
    for _ in range(N_NULL):
        cars = [s if rng2.random() < 0.5 else -s for s in real_cars]
        null_flip.append(stat(cars))
    pct_flip = sum(1 for v in null_flip if v < real) / N_NULL

    placebo_cars, placebo_dropped = [], 0
    for tk, i0, d, _s in events:
        v = grid.car20(tk, i0 - 20)
        if v is None:
            placebo_dropped += 1
        else:
            placebo_cars.append(v * d)
    placebo = stat(placebo_cars) if placebo_cars else None
    pct_placebo_in_null = (sum(1 for v in null_shuffle if v < placebo) / N_NULL
                           if placebo is not None else None)

    def summ(xs):
        m = sum(xs) / len(xs)
        sd = (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
        return {"mean": round(m, 3), "sd": round(sd, 3),
                "p2_5": round(sorted(xs)[int(0.025 * len(xs))], 3),
                "p97_5": round(sorted(xs)[int(0.975 * len(xs)) - 1], 3)}

    return {
        "target": name, "real_pct": round(real, 3), "n_events": len(events),
        "n_issuers": len(elig),
        "eligible_grid_days": {tk: len(v) for tk, v in elig.items()},
        "date_shuffle": {"null": summ(null_shuffle),
                         "percentile_in_null": round(pct_shuffle, 3)},
        "sign_flip": {"null": summ(null_flip),
                      "percentile_in_null": round(pct_flip, 3)},
        "placebo_minus20d": {"value_pct": (round(placebo, 3)
                                           if placebo is not None else None),
                             "dropped": placebo_dropped,
                             "percentile_in_shuffle_null":
                                 (round(pct_placebo_in_null, 3)
                                  if pct_placebo_in_null is not None else None)},
        "note": "two-sided extremity, exploratory" + dropped_note,
    }


def main() -> int:
    reg = Registry(REGISTRY_PATH)
    proto = register_first(reg)
    reg.assert_registered(proto["protocol_id"])

    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    panels = {}

    # ---- SMH E4 (backfill era)
    smh_cov = overlap_summary()["covered"]
    fund_w = overlap_summary()["weights_covered"]
    grid = TargetGrid(smh_cov, prices, trade_dates)
    rows = [r for r in event_study()["per_event_rows"] if r["era"] == "backfill"]
    events, mism = [], 0
    from datetime import date as _date
    for r in rows:
        ev_date = _date.fromisoformat(r["date"])
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            continue
        i0 = idx[day0]
        g = grid.car20(r["ticker"], i0)
        signed = r["car20_peer_aligned_pct"]
        if g is not None and abs(g * r["direction"] - signed) > 0.05:
            mism += 1
        events.append((r["ticker"], i0, r["direction"], signed))
    print(f"[SMH] {len(events)} events, grid cross-check mismatches: {mism}")
    panels["SMH-E4"] = battery("SMH-E4", events, grid, "capped", fund_w)

    # ---- Canada lenses (pooled event-weighted)
    lens_hold = canada_lens_holdings()
    for lens in CANADA:
        covered = sorted(lens_hold[lens])
        g = TargetGrid(covered, prices, trade_dates)
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ticker, event_type, direction,
                              event_time::date
                       FROM events WHERE event_status='accepted'
                         AND ticker = ANY(%s) AND direction <> 0
                       ORDER BY 4""", (covered,))
                evs = cur.fetchall()
        lens_events = []
        for tk, _et, d, ev_date in evs:
            day0 = next((dd for dd in trade_dates if dd >= ev_date), None)
            if day0 is None:
                continue
            i0 = idx[day0]
            v = g.car20(tk, i0)
            if v is None:
                continue
            lens_events.append((tk, i0, int(d), v * int(d)))
        pooled = sum(s for *_x, s in lens_events) / len(lens_events)
        print(f"[{lens}] n={len(lens_events)} pooled+20={pooled:+.2f}% "
              f"(snapshot cross-check target)")
        panels[lens] = battery(lens, lens_events, g, "event", {})

    payload = {"protocol_id": proto["protocol_id"], "method_hash": METHOD_HASH,
               "built_utc": utc_now(), "n_null": N_NULL, "seed": SEED,
               "panels": panels}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    line = reg.record_run(Run(
        protocol_id=proto["protocol_id"],
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=("SMH backfill era + 4 Canada lens event sets, "
                     "prices through " + trade_dates[-1].isoformat()),
        n_primary_cells=1,
        n_secondary_cells=14,
        result_hash=result_hash,
        note=("ORDER v5.1 Part B. Primary = SMH-E4 date-shuffle percentile. "
              "Secondary = SMH sign-flip + placebo (2) + 4 lenses x 3 tests "
              "(12). Panels render into previews from "
              "output/oie/falsification_run.json."),
    ))
    reg.verify_chain()
    print(f"[registry] run recorded, line {line[:16]}…, chain OK")

    for name, p in panels.items():
        print(f"[{name}] real={p['real_pct']:+.2f}%  "
              f"shuffle-pct={p['date_shuffle']['percentile_in_null']:.3f}  "
              f"flip-pct={p['sign_flip']['percentile_in_null']:.3f}  "
              f"placebo={p['placebo_minus20d']['value_pct']}  "
              f"(dropped {p['placebo_minus20d']['dropped']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
