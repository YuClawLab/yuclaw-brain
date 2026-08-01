#!/usr/bin/env python3
"""
Composite baseline comparison v1 (credibility battery Part B) —
REGISTRY-FIRST. The coin-flip question, pre-registered.

METHOD_SPEC (locked):
  Window: forward-OOS signal dates (track_record.is_backfill = false),
  dates with >= 40 scored tickers (the Lab's standing inclusion rule).
  BASELINES (per date, per ticker; deterministic, stated):
    B1 random-rank        — seeded uniform draw, seed "20260801:<date>:<ticker>"
    B2 momentum-rank      — trailing 60-trading-day return ending the day
                            before the signal date (price_history closes;
                            >= 40 usable days required, else excluded)
    B3 short-reversal     — trailing 5-trading-day return, inverted
    B4 persistence        — the ticker's total_score on the PREVIOUS signal
                            date (first date excluded)
    B5 equal-weight       — unweighted mean of the nine component scores
                            from the same snapshot (snapshot_id join)
  IC: per-date cross-sectional Spearman of strategy value vs return_kd,
  k in {1, 5, 20}; mean over dates.
  PRIMARY (single): composite IC minus BEST-baseline IC at k=5, where
  "best baseline" = the baseline with the highest point-estimate mean IC
  at k=5 (deterministic argmax over B1..B5, stated in the run note);
  ticker-clustered bootstrap CI on the difference (resample tickers with
  replacement, recompute both mean ICs per replicate over the resampled
  cross-sections; B=2000, seed 20260801; percentile 2.5/97.5).
  SECONDARY: every baseline x horizon mean-IC cell (15) plus the
  composite-minus-baseline difference at k=5 for each baseline (5) —
  ledger-counted. Badges (locked): UNDERPOWERED if < 20 dates or < 8
  clustered tickers; DESCRIPTIVE if the difference CI includes 0; else
  PRELIMINARY. A baseline that ties or beats the composite prints exactly
  as measured. Edits => supersession.
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
from v3.lab.cohort_engine import DSN, MIN_UNIVERSE_FOR_DECILES, load_prices
from v3.lab.stats import spearman

SEED = 20260801
B = 2000
KS = (1, 5, 20)
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Composite baseline comparison v1"
PROTOCOL_PARAMS = {"baselines": ["random", "momentum60", "reversal5",
                                 "persistence", "equal_weight"],
                   "ks": list(KS), "k_primary": 5, "B": B, "seed": SEED}
OUT_JSON = _REPO / "output" / "oie" / "baselines_run.json"
COMP_COLS = ("c1_price_momentum", "c2_volume_confirm", "c3_sector_velocity",
             "c4_macro_regime", "c5_oil_rates_fx", "c6_event_impact",
             "c7_peer_correlation", "c8_cascade_effect", "c9_model_trust")


def load_panel():
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(f"""
                SELECT t.signal_date, t.ticker, t.total_score,
                       t.return_1d, t.return_5d, t.return_20d,
                       {', '.join('s.' + c for c in COMP_COLS)}
                FROM track_record t JOIN signal_snapshots s
                  ON s.snapshot_id = t.snapshot_id
                WHERE t.is_backfill = false
                ORDER BY t.signal_date""")
            rows = cur.fetchall()
    by_date: dict = {}
    for r in rows:
        d, tk, score = r[0], r[1], float(r[2])
        rets = {1: r[3], 5: r[4], 20: r[5]}
        comps = [float(x) for x in r[6:] if x is not None]
        by_date.setdefault(d, {})[tk] = {
            "score": score,
            "rets": {k: float(v) for k, v in rets.items() if v is not None},
            "ew": sum(comps) / len(comps) if comps else None}
    return {d: v for d, v in by_date.items()
            if len(v) >= MIN_UNIVERSE_FOR_DECILES}


def trailing(prices, td, idx, tk, d, win):
    day_prev = None
    for i in range(idx.get(d, 0) - 1, -1, -1):
        if td[i] < d:
            day_prev = i
            break
    if day_prev is None or day_prev - win < 0:
        return None
    p0 = prices.get(tk, {}).get(td[day_prev - win])
    p1 = prices.get(tk, {}).get(td[day_prev])
    if not p0 or not p1:
        return None
    return p1 / p0 - 1


def build_strategies(panel):
    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    dates = sorted(panel)
    strat: dict = {}   # date -> ticker -> {name: value}
    prev_scores: dict = {}
    for d in dates:
        day = {}
        for tk, row in panel[d].items():
            rng = random.Random(f"{SEED}:{d}:{tk}")
            mom = trailing(prices, td, idx, tk, d, 60)
            rev = trailing(prices, td, idx, tk, d, 5)
            day[tk] = {"composite": row["score"],
                       "random": rng.random(),
                       "momentum60": mom,
                       "reversal5": (-rev if rev is not None else None),
                       "persistence": prev_scores.get(tk),
                       "equal_weight": row["ew"]}
        strat[d] = day
        prev_scores = {tk: row["score"] for tk, row in panel[d].items()}
    return strat


def mean_ic(panel, strat, name, k, mult=None):
    ics = []
    for d, day in panel.items():
        xs, ys = [], []
        for tk, row in day.items():
            v = strat[d][tk].get(name)
            r = row["rets"].get(k)
            if v is None or r is None:
                continue
            m = 1 if mult is None else mult.get(tk, 0)
            xs += [v] * m
            ys += [r] * m
        if len(xs) >= 8:
            rho = spearman(xs, ys)
            if rho is not None:
                ics.append(rho)
    return (sum(ics) / len(ics), len(ics)) if ics else (None, 0)


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Five deterministic baselines (random, momentum-60, "
                          "reversal-5, persistence, equal-weight components) "
                          "vs the composite: per-date Spearman IC, forward-"
                          "OOS; primary = composite minus best-baseline IC "
                          "at k=5 with ticker-clustered CI; every cell "
                          "ledgered; ties or losses print as measured."),
            primary_endpoint=("composite IC minus best-baseline IC at k=5, "
                              "forward-OOS, ticker-clustered CI"),
            secondary_endpoints=["baseline x horizon mean-IC cells (15)",
                                 "composite-minus-baseline diffs at k=5 (5)"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE computation")
    reg.assert_registered(pid)

    panel = load_panel()
    strat = build_strategies(panel)
    names = ["composite", "random", "momentum60", "reversal5",
             "persistence", "equal_weight"]
    table = {n: {k: mean_ic(panel, strat, n, k) for k in KS} for n in names}

    k5 = {n: table[n][5][0] for n in names if table[n][5][0] is not None}
    best_base = max((n for n in k5 if n != "composite"), key=lambda n: k5[n])
    point_diff = k5["composite"] - k5[best_base]

    tickers = sorted({tk for d in panel for tk in panel[d]})
    rng = random.Random(f"{SEED}:cluster")
    reps = []
    for _ in range(B):
        mult: dict = {}
        for _ in tickers:
            t = tickers[rng.randrange(len(tickers))]
            mult[t] = mult.get(t, 0) + 1
        a, _n1 = mean_ic(panel, strat, "composite", 5, mult)
        b2, _n2 = mean_ic(panel, strat, best_base, 5, mult)
        if a is not None and b2 is not None:
            reps.append(a - b2)
    reps.sort()
    ci = (round(reps[int(0.025 * len(reps))], 4),
          round(reps[int(0.975 * len(reps)) - 1], 4))
    n_dates = table["composite"][5][1]
    badge = ("UNDERPOWERED" if n_dates < 20 or len(tickers) < 8 else
             "DESCRIPTIVE" if ci[0] <= 0 <= ci[1] else "PRELIMINARY")

    diffs5 = {}
    for n in names:
        if n == "composite" or table[n][5][0] is None:
            continue
        rngd = random.Random(f"{SEED}:diff:{n}")
        rr = []
        for _ in range(B):
            mult = {}
            for _ in tickers:
                t = tickers[rngd.randrange(len(tickers))]
                mult[t] = mult.get(t, 0) + 1
            a, _x = mean_ic(panel, strat, "composite", 5, mult)
            bb, _y = mean_ic(panel, strat, n, 5, mult)
            if a is not None and bb is not None:
                rr.append(a - bb)
        rr.sort()
        cid = (round(rr[int(0.025 * len(rr))], 4),
               round(rr[int(0.975 * len(rr)) - 1], 4))
        diffs5[n] = {"diff": round(k5["composite"] - k5[n], 4), "ci": cid,
                     "badge": ("DESCRIPTIVE" if cid[0] <= 0 <= cid[1]
                               else "PRELIMINARY")}

    payload = {
        "protocol_id": pid, "method_hash": METHOD_HASH,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "window": {"n_dates": n_dates, "n_tickers": len(tickers)},
        "table": {n: {str(k): {"mean_ic": (round(v[0], 4)
                                           if v[0] is not None else None),
                               "n_dates": v[1]}
                      for k, v in table[n].items()} for n in names},
        "best_baseline_k5": best_base,
        "primary": {"diff": round(point_diff, 4), "ci": ci, "badge": badge},
        "diffs_k5": diffs5,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"forward-OOS, {n_dates} dates, {len(tickers)} tickers",
        n_primary_cells=1, n_secondary_cells=20, result_hash=rh,
        note=(f"Baseline comparison activation. Best baseline at k=5 (argmax "
              f"rule): {best_base}. Primary diff {point_diff:+.4f} CI {ci} "
              f"[{badge}].")))
    reg.verify_chain()
    for n in names:
        print(f"  {n:>13}: " + "  ".join(
            f"k{k}={table[n][k][0]:+.4f}" if table[n][k][0] is not None
            else f"k{k}=—" for k in KS))
    print(f"[primary] composite - {best_base} @k5 = {point_diff:+.4f} "
          f"CI{ci} [{badge}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
