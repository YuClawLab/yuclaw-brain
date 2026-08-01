#!/usr/bin/env python3
"""
Neutralized IC v1 (review-completion Part A) — REGISTRY-FIRST.
Is the composite's association with forward returns just factor exposure?

METHOD_SPEC (locked; own-data version):
  Window: forward-OOS signal dates with >= 40 scored tickers.
  Strategies: the composite plus each of the nine component scores
  (signal_snapshots columns, snapshot_id join).
  NEUTRALIZERS (cross-sectional, per date; k=5 forward returns):
    N1 market beta   — trailing-60-trading-day OLS beta vs SPY daily
                       returns ending the day before the signal date.
                       Computability bound stated honestly: SPY's own
                       series begins 2026-02-02, so 60d betas exist from
                       late April onward — which covers the entire forward
                       window (first forward date 2026-05-20); no forward
                       date is lost to the bound.
    N2 momentum      — prior-60-trading-day return, cross-sectional rank
    N3 volatility    — trailing-20d daily-return stdev, cross-sectional rank
    N4 sector        — NOT COMPUTABLE from owned config: the universe file
                       carries no per-equity sector mapping (verified);
                       the sector cell is reported as such, never proxied.
  Procedure: per date, residualize return_5d on the neutralizer(s) by
  cross-sectional OLS (with intercept); IC = Spearman(strategy score,
  residual); mean over dates. Variants: each computable neutralizer alone,
  and ALL-JOINTLY (N1+N2+N3). PRIMARY (single): composite all-jointly-
  neutralized IC at k=5, ticker-clustered bootstrap CI (B=2000, seed
  20260801). All other strategy x neutralizer cells secondary, ledgered.
  Badges: UNDERPOWERED if < 20 dates or < 8 clustered tickers; DESCRIPTIVE
  if the CI includes 0; else PRELIMINARY. Edits => supersession.
"""
from __future__ import annotations

import hashlib
import json
import math
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
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Neutralized IC v1"
PROTOCOL_PARAMS = {"k": 5, "neutralizers": ["beta60", "mom60", "vol20",
                                            "joint"], "sector": "not_computable",
                   "B": B, "seed": SEED}
OUT_JSON = _REPO / "output" / "oie" / "neutralized_ic.json"
COMP_COLS = ("c1_price_momentum", "c2_volume_confirm", "c3_sector_velocity",
             "c4_macro_regime", "c5_oil_rates_fx", "c6_event_impact",
             "c7_peer_correlation", "c8_cascade_effect", "c9_model_trust")


def _multi_ols_resid(y, X):
    """Residuals of y on X (with intercept) via normal equations."""
    n, p = len(y), len(X[0]) + 1
    A = [[1.0] + list(row) for row in X]
    AtA = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(p)]
           for a in range(p)]
    Aty = [sum(A[i][a] * y[i] for i in range(n)) for a in range(p)]
    # gaussian elimination with tiny ridge for stability
    for d in range(p):
        AtA[d][d] += 1e-9
    for col in range(p):
        piv = max(range(col, p), key=lambda r: abs(AtA[r][col]))
        AtA[col], AtA[piv] = AtA[piv], AtA[col]
        Aty[col], Aty[piv] = Aty[piv], Aty[col]
        if abs(AtA[col][col]) < 1e-12:
            return None
        for r in range(p):
            if r != col:
                f = AtA[r][col] / AtA[col][col]
                for c2 in range(col, p):
                    AtA[r][c2] -= f * AtA[col][c2]
                Aty[r] -= f * Aty[col]
    beta = [Aty[i] / AtA[i][i] for i in range(p)]
    return [y[i] - sum(beta[j] * A[i][j] for j in range(p)) for i in range(n)]


def build_data():
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(f"""
                SELECT t.signal_date, t.ticker, t.total_score, t.return_5d,
                       {', '.join('s.' + c for c in COMP_COLS)}
                FROM track_record t JOIN signal_snapshots s
                  ON s.snapshot_id = t.snapshot_id
                WHERE t.is_backfill = false AND t.return_5d IS NOT NULL""")
            rows = cur.fetchall()
    prices, td = load_prices()
    spy = prices["SPY"]
    idx = {d: i for i, d in enumerate(td)}

    def rets(tk):
        out, prev = {}, None
        for d in td:
            px = prices.get(tk, {}).get(d)
            if px is not None and prev not in (None, 0):
                out[d] = px / prev - 1
            if px is not None:
                prev = px
        return out
    spy_r = rets("SPY")
    cache: dict = {}

    def factors(tk, d):
        key = (tk, d)
        if key in cache:
            return cache[key]
        if tk not in cache.setdefault("_r", {}):
            cache["_r"][tk] = rets(tk)
        rr = cache["_r"][tk]
        i0 = None
        for i in range(idx.get(d, len(td)) - 1, -1, -1):
            if td[i] < d:
                i0 = i
                break
        out = None
        if i0 is not None and i0 >= 60:
            xs, ys = [], []
            for j in range(i0 - 59, i0 + 1):
                a, b2 = rr.get(td[j]), spy_r.get(td[j])
                if a is not None and b2 is not None:
                    xs.append(b2)
                    ys.append(a)
            if len(xs) >= 40:
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                vx = sum((x - mx) ** 2 for x in xs)
                beta = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx
                        if vx > 0 else None)
                p0 = prices.get(tk, {}).get(td[i0 - 59])
                p1 = prices.get(tk, {}).get(td[i0])
                mom = p1 / p0 - 1 if p0 and p1 else None
                w = [rr.get(td[j]) for j in range(i0 - 19, i0 + 1)]
                w = [x for x in w if x is not None]
                vol = None
                if len(w) >= 15:
                    mw = sum(w) / len(w)
                    vol = math.sqrt(sum((x - mw) ** 2 for x in w) / (len(w) - 1))
                if None not in (beta, mom, vol):
                    out = (beta, mom, vol)
        cache[key] = out
        return out

    panel: dict = {}
    for r in rows:
        d, tk, score, r5 = r[0], r[1], float(r[2]), float(r[3])
        f = factors(tk, d)
        if f is None:
            continue
        comps = {c: (float(v) if v is not None else None)
                 for c, v in zip(COMP_COLS, r[4:])}
        panel.setdefault(d, {})[tk] = {"score": score, "r5": r5,
                                       "beta": f[0], "mom": f[1],
                                       "vol": f[2], **comps}
    return {d: v for d, v in panel.items()
            if len(v) >= MIN_UNIVERSE_FOR_DECILES}


def _rank(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    rk = [0.0] * len(vals)
    for pos, i in enumerate(order):
        rk[i] = pos
    return rk


def ic(panel, strat_key, neutral, mult=None):
    ics = []
    for d, day in panel.items():
        rows = [(tk, v) for tk, v in day.items()
                if v.get(strat_key) is not None]
        xs, ys, F = [], [], []
        for tk, v in rows:
            m = 1 if mult is None else mult.get(tk, 0)
            for _ in range(m):
                xs.append(v[strat_key])
                ys.append(v["r5"])
                F.append((v["beta"], v["mom"], v["vol"]))
        if len(xs) < 10:
            continue
        if neutral == "raw":
            resid = ys
        else:
            mom_rk = _rank([f[1] for f in F])
            vol_rk = _rank([f[2] for f in F])
            cols = {"beta60": [[f[0]] for f in F],
                    "mom60": [[mr] for mr in mom_rk],
                    "vol20": [[vr] for vr in vol_rk],
                    "joint": [[f[0], mr, vr] for f, mr, vr
                              in zip(F, mom_rk, vol_rk)]}[neutral]
            resid = _multi_ols_resid(ys, cols)
            if resid is None:
                continue
        rho = spearman(xs, resid)
        if rho is not None:
            ics.append(rho)
    return (sum(ics) / len(ics), len(ics)) if ics else (None, 0)


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Forward-OOS IC after cross-sectional "
                          "residualization on beta60 / momentum-rank / "
                          "vol-rank, singly and jointly, for the composite "
                          "and each component; sector cell honestly "
                          "not-computable (no owned mapping); primary = "
                          "composite jointly-neutralized IC at k=5, "
                          "ticker-clustered CI."),
            primary_endpoint=("composite all-jointly-neutralized IC at k=5, "
                              "ticker-clustered CI"),
            secondary_endpoints=["strategy x neutralizer cells (10 x 4 raw+3)",
                                 "component neutralized cells"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE computation")
    reg.assert_registered(pid)

    panel = build_data()
    strategies = ["score"] + list(COMP_COLS)
    variants = ["raw", "beta60", "mom60", "vol20", "joint"]
    table = {}
    for s in strategies:
        table[s] = {v: ic(panel, s, v) for v in variants}
        print(f"  {s:>20}: " + "  ".join(
            f"{v}={table[s][v][0]:+.4f}" if table[s][v][0] is not None
            else f"{v}=—" for v in variants))

    tickers = sorted({tk for d in panel for tk in panel[d]})
    rng = random.Random(f"{SEED}:neutral")
    reps = []
    for _ in range(B):
        mult: dict = {}
        for _ in tickers:
            t = tickers[rng.randrange(len(tickers))]
            mult[t] = mult.get(t, 0) + 1
        v, _n = ic(panel, "score", "joint", mult)
        if v is not None:
            reps.append(v)
    reps.sort()
    ci = (round(reps[int(0.025 * len(reps))], 4),
          round(reps[int(0.975 * len(reps)) - 1], 4))
    n_dates = table["score"]["joint"][1]
    badge = ("UNDERPOWERED" if n_dates < 20 or len(tickers) < 8 else
             "DESCRIPTIVE" if ci[0] <= 0 <= ci[1] else "PRELIMINARY")

    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "window": {"n_dates": n_dates, "n_tickers": len(tickers)},
               "sector_cell": "not computable from owned config (no "
                              "per-equity sector mapping) — stated, not proxied",
               "table": {s: {v: {"mean_ic": (round(x[0], 4)
                                             if x[0] is not None else None),
                                 "n_dates": x[1]}
                             for v, x in row.items()}
                         for s, row in table.items()},
               "primary": {"joint_ic_k5": round(table["score"]["joint"][0], 4),
                           "ci": ci, "badge": badge}}
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"forward-OOS, {n_dates} dates, {len(tickers)} tickers",
        n_primary_cells=1, n_secondary_cells=49, result_hash=rh,
        note=(f"Neutralized IC activation: composite raw "
              f"{table['score']['raw'][0]:+.4f} -> joint "
              f"{table['score']['joint'][0]:+.4f} CI {ci} [{badge}]. "
              f"Sector cell not computable (disclosed).")))
    reg.verify_chain()
    print(f"[primary] composite joint-neutralized IC k5 = "
          f"{table['score']['joint'][0]:+.4f} CI{ci} [{badge}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
