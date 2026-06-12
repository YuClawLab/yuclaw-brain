"""YUCLAW Signal Granularity Investigation — resolve the spread-vs-IC puzzle.

Pure research analysis, READ-ONLY on signal_snapshots + price_history. Determines
whether the near-zero Spearman IC (despite a positive top-minus-bottom decile
spread) is caused by (A) coarse score quantization / ties corrupting rank
statistics, or (B) a genuinely flat cross-sectional signal.

Run:  python3 -m v3.lab.granularity_investigation
Prints a structured report; numbers are transcribed into
docs/methodology/granularity_investigation.md.

Descriptive statistics only. No raw prices are printed (only derived returns and
correlations).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Any

import psycopg2

from v3.lab.cohort_engine import (
    _connect, _entry_date, _period_return, load_prices, BENCHMARK,
)
from v3.lab.analytics import spearman, _stdev

COMPONENTS = ["c1_price_momentum", "c2_volume_confirm", "c3_sector_velocity",
              "c4_macro_regime", "c5_oil_rates_fx", "c6_event_impact",
              "c7_peer_correlation", "c8_cascade_effect", "c9_model_trust"]
CSHORT = {c: c.split("_", 1)[0].upper() for c in COMPONENTS}  # c1_... -> C1
N_DECILES = 10


# ---- loaders ---------------------------------------------------------------
def load_full(panel: str) -> dict:
    """{date: {ticker: {'score':..,'label':..,'comps':{c:..}}}} for a panel."""
    is_backfill = (panel == "in_sample")
    cols = ", ".join(COMPONENTS)
    q = (f"SELECT signal_time::date AS d, ticker, total_score, signal_label, {cols} "
         f"FROM signal_snapshots WHERE is_backfill = %s ORDER BY d, ticker")
    out: dict = {}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(q, (is_backfill,))
        for row in cur.fetchall():
            d, tk, score, label = row[0], row[1], float(row[2]), row[3]
            comps = {COMPONENTS[i]: (None if row[4 + i] is None else float(row[4 + i]))
                     for i in range(len(COMPONENTS))}
            out.setdefault(d, {})[tk] = {"score": score, "label": label, "comps": comps}
    return out


def joined(panel: str) -> list[dict]:
    """Per rebalance: items [(ticker, score, comps, fwd_ret)] over the next
    inter-rebalance period (names with an evaluable forward window only)."""
    snaps = load_full(panel)
    prices, tds = load_prices()
    rdates = sorted(snaps.keys())
    out = []
    for i, rd in enumerate(rdates):
        d0 = _entry_date(tds, rd)
        nxt = rdates[i + 1] if i + 1 < len(rdates) else None
        d1 = _entry_date(tds, nxt) if nxt else (tds[-1] if tds else None)
        if d0 is None or d1 is None or d1 <= d0:
            continue
        items = []
        for tk, v in snaps[rd].items():
            r = _period_return(prices.get(tk, {}), d0, d1)
            if r is not None:
                items.append({"tk": tk, "score": v["score"], "comps": v["comps"], "ret": r})
        if len(items) >= N_DECILES:
            out.append({"date": rd, "items": items})
    return out


# ---- tie-aware statistics --------------------------------------------------
def kendall_tau_b(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    P = Q = Tx = Ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = xs[i] - xs[j], ys[i] - ys[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                Tx += 1
            elif dy == 0:
                Ty += 1
            elif (dx > 0) == (dy > 0):
                P += 1
            else:
                Q += 1
    denom = math.sqrt((P + Q + Tx) * (P + Q + Ty))
    return None if denom == 0 else (P - Q) / denom


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


# ---- PHASE 1: granularity audit --------------------------------------------
def phase1(panel: str) -> dict:
    snaps = load_full(panel)
    rows = []
    comp_distinct = {c: [] for c in COMPONENTS}
    for d in sorted(snaps):
        names = snaps[d]
        scores = [v["score"] for v in names.values()]
        n = len(scores)
        cnt = Counter(round(s, 6) for s in scores)
        distinct = len(cnt)
        biggest_val, biggest = cnt.most_common(1)[0]
        # where do ties sit? rank the distinct score levels; for each tied group
        # (size>1) record the mean percentile of its members in the score order.
        order = sorted(scores)
        tie_mid = tie_ext = 0
        for val, c in cnt.items():
            if c < 2:
                continue
            # percentile band of this score level
            idx = [i for i, s in enumerate(order) if round(s, 6) == val]
            pct = (sum(idx) / len(idx)) / max(n - 1, 1)
            if 0.25 <= pct <= 0.75:
                tie_mid += c
            else:
                tie_ext += c
        tied_total = sum(c for c in cnt.values() if c >= 2)
        rows.append({"date": d.isoformat(), "n": n, "distinct": distinct,
                     "biggest_tie": biggest, "tied_names": tied_total,
                     "tie_mid": tie_mid, "tie_ext": tie_ext})
        for c in COMPONENTS:
            vals = [v["comps"][c] for v in names.values() if v["comps"][c] is not None]
            comp_distinct[c].append(len(set(round(x, 6) for x in vals)) if vals else 0)
    comp_summary = {c: {"mean_distinct": _mean(comp_distinct[c]),
                        "max_distinct": max(comp_distinct[c]) if comp_distinct[c] else 0}
                    for c in COMPONENTS}
    return {"rows": rows, "comp_distinct": comp_summary,
            "mean_distinct": _mean([r["distinct"] for r in rows]),
            "mean_biggest_tie": _mean([r["biggest_tie"] for r in rows]),
            "mean_tied_names": _mean([r["tied_names"] for r in rows]),
            "tie_mid_total": sum(r["tie_mid"] for r in rows),
            "tie_ext_total": sum(r["tie_ext"] for r in rows)}


# ---- PHASE 2: tie-aware statistics -----------------------------------------
def phase2(panel: str) -> dict:
    rebs = joined(panel)
    spear, tau, diff_ic = [], [], []
    diff_ns = []
    for reb in rebs:
        sc = [it["score"] for it in reb["items"]]
        rt = [it["ret"] for it in reb["items"]]
        s = spearman(sc, rt)
        t = kendall_tau_b(sc, rt)
        if s is not None:
            spear.append(s)
        if t is not None:
            tau.append(t)
        # differentiated subset: scores that are unique at this rebalance
        c = Counter(round(x, 6) for x in sc)
        idx = [i for i, x in enumerate(sc) if c[round(x, 6)] == 1]
        if len(idx) >= 3:
            ds = spearman([sc[i] for i in idx], [rt[i] for i in idx])
            if ds is not None:
                diff_ic.append(ds)
                diff_ns.append(len(idx))
    return {
        "n": len(rebs),
        "spearman_mean": _mean(spear), "spearman_hit": _mean([1 if x > 0 else 0 for x in spear]),
        "tau_mean": _mean(tau), "tau_hit": _mean([1 if x > 0 else 0 for x in tau]),
        "diff_ic_mean": _mean(diff_ic), "diff_ic_hit": _mean([1 if x > 0 else 0 for x in diff_ic]),
        "diff_n_mean": _mean(diff_ns), "diff_points": len(diff_ic),
    }


# ---- PHASE 3: decile robustness under random tie-breaking ------------------
def _deciles_with_seed(items, rng):
    """Return list of 10 buckets (lists of items), top score = D1."""
    keyed = sorted(items, key=lambda it: (it["score"], rng.random()), reverse=True)
    n = len(keyed)
    return [keyed[(k * n) // N_DECILES:((k + 1) * n) // N_DECILES] for k in range(N_DECILES)]


def phase3(panel: str, seeds: int = 200) -> dict:
    rebs = joined(panel)
    rhos, spreads, topcums = [], [], []
    for seed in range(seeds):
        rng = random.Random(seed)
        bucket_means = [[] for _ in range(N_DECILES)]
        top_periods = []
        for reb in rebs:
            buckets = _deciles_with_seed(reb["items"], rng)
            for k, b in enumerate(buckets):
                if b:
                    bucket_means[k].append(_mean([it["ret"] for it in b]))
            if buckets[0]:
                top_periods.append(_mean([it["ret"] for it in buckets[0]]))
        dmean = [_mean(b) for b in bucket_means]
        xs = [N_DECILES - k for k in range(N_DECILES) if dmean[k] is not None]
        ys = [dmean[k] for k in range(N_DECILES) if dmean[k] is not None]
        rhos.append(spearman([float(x) for x in xs], ys))
        spreads.append(dmean[0] - dmean[-1])
        cum = 1.0
        for r in top_periods:
            cum *= (1 + r)
        topcums.append(cum - 1)

    def dist(a):
        a = [x for x in a if x is not None]
        a_sorted = sorted(a)
        return {"mean": _mean(a), "std": _stdev(a), "min": min(a), "max": max(a),
                "p05": a_sorted[int(0.05 * len(a))], "p95": a_sorted[int(0.95 * len(a))],
                "frac_pos": _mean([1 if x > 0 else 0 for x in a])}
    return {"seeds": seeds, "rho": dist(rhos), "spread": dist(spreads), "topcum": dist(topcums)}


# ---- PHASE 4: extremes vs middle -------------------------------------------
def phase4(panel: str, k: int = 8) -> dict:
    rebs = joined(panel)
    ext_ic, mid_ic = [], []
    top_rets, bot_rets, mid_rets = [], [], []
    for reb in rebs:
        srt = sorted(reb["items"], key=lambda it: it["score"], reverse=True)
        n = len(srt)
        if n < 2 * k + 4:
            continue
        top, bot, mid = srt[:k], srt[-k:], srt[k:n - k]
        ext = top + bot
        e = spearman([it["score"] for it in ext], [it["ret"] for it in ext])
        m = spearman([it["score"] for it in mid], [it["ret"] for it in mid])
        if e is not None:
            ext_ic.append(e)
        if m is not None:
            mid_ic.append(m)
        top_rets.append(_mean([it["ret"] for it in top]))
        bot_rets.append(_mean([it["ret"] for it in bot]))
        mid_rets.append(_mean([it["ret"] for it in mid]))
    return {
        "k": k, "n": len(top_rets),
        "ext_ic_mean": _mean(ext_ic), "ext_ic_hit": _mean([1 if x > 0 else 0 for x in ext_ic]),
        "mid_ic_mean": _mean(mid_ic), "mid_ic_hit": _mean([1 if x > 0 else 0 for x in mid_ic]),
        "top_ret_mean": _mean(top_rets), "bot_ret_mean": _mean(bot_rets),
        "mid_ret_mean": _mean(mid_rets),
        "tail_spread": (_mean(top_rets) - _mean(bot_rets)) if top_rets else None,
    }


# ---- PHASE 5: period attribution -------------------------------------------
def phase5(panel: str, k_frac: int = N_DECILES) -> dict:
    rebs = joined(panel)
    contrib = []
    for reb in rebs:
        srt = sorted(reb["items"], key=lambda it: it["score"], reverse=True)
        n = len(srt)
        kk = max(1, n // k_frac)
        top = srt[:kk]
        bot = srt[-kk:]
        sp = _mean([it["ret"] for it in top]) - _mean([it["ret"] for it in bot])
        contrib.append({"date": reb["date"].isoformat(), "spread": sp})
    total = sum(c["spread"] for c in contrib)
    ranked = sorted(contrib, key=lambda c: abs(c["spread"]), reverse=True)
    top3 = sum(c["spread"] for c in ranked[:3])
    return {"n": len(contrib), "total_spread": total, "contrib": contrib,
            "top3_share": (top3 / total) if total else None,
            "top3_dates": [c["date"] for c in ranked[:3]],
            "max_single": ranked[0] if ranked else None}


# ---- PHASE 6: component-level IC -------------------------------------------
def phase6(panel: str) -> dict:
    rebs = joined(panel)
    per_comp_spear = {c: [] for c in COMPONENTS}
    per_comp_tau = {c: [] for c in COMPONENTS}
    for reb in rebs:
        rt = [it["ret"] for it in reb["items"]]
        for c in COMPONENTS:
            vals = [it["comps"][c] for it in reb["items"]]
            if any(v is None for v in vals):
                continue
            s = spearman(vals, rt)
            t = kendall_tau_b(vals, rt)
            if s is not None:
                per_comp_spear[c].append(s)
            if t is not None:
                per_comp_tau[c].append(t)
    table = []
    for c in COMPONENTS:
        table.append({"comp": CSHORT[c], "name": c,
                      "spearman_mean": _mean(per_comp_spear[c]),
                      "tau_mean": _mean(per_comp_tau[c]),
                      "n": len(per_comp_spear[c])})
    table.sort(key=lambda r: (r["spearman_mean"] if r["spearman_mean"] is not None else 0),
               reverse=True)
    return {"table": table}


def run() -> dict:
    res = {}
    for panel in ("in_sample", "forward"):
        res[panel] = {
            "p1": phase1(panel), "p2": phase2(panel),
            "p3": phase3(panel), "p4": phase4(panel),
            "p5": phase5(panel), "p6": phase6(panel),
        }
    return res


def _f(x, dp=4):
    return "    None" if x is None else f"{x:+.{dp}f}"


if __name__ == "__main__":
    res = run()
    for panel in ("in_sample", "forward"):
        p = res[panel]
        print(f"\n{'='*70}\n=== PANEL: {panel} ===\n{'='*70}")
        p1 = p["p1"]
        print(f"\n[P1 GRANULARITY] mean distinct scores/79: {p1['mean_distinct']:.1f} · "
              f"mean biggest tie-group: {p1['mean_biggest_tie']:.1f} · "
              f"mean tied names: {p1['mean_tied_names']:.1f}")
        print(f"  ties location: mid-distribution={p1['tie_mid_total']} vs extremes={p1['tie_ext_total']}")
        print("  component distinct-value counts (mean/max per rebalance):")
        for c in COMPONENTS:
            cs = p1["comp_distinct"][c]
            print(f"    {CSHORT[c]:>3} {c:<20} mean={cs['mean_distinct']:.1f} max={cs['max_distinct']}")
        p2 = p["p2"]
        print(f"\n[P2 TIE-AWARE] n={p2['n']}")
        print(f"  Spearman mean IC : {_f(p2['spearman_mean'])}  hit={p2['spearman_hit']}")
        print(f"  Kendall tau-b    : {_f(p2['tau_mean'])}  hit={p2['tau_hit']}")
        print(f"  Differentiated-subset IC: {_f(p2['diff_ic_mean'])}  hit={p2['diff_ic_hit']}  "
              f"(mean subset n={p2['diff_n_mean']}, points={p2['diff_points']})")
        p3 = p["p3"]
        print(f"\n[P3 DECILE ROBUSTNESS] {p3['seeds']} tie-break seeds")
        for key, lab in [("rho", "monotonicity rho"), ("spread", "D1-D10 spread"), ("topcum", "top-decile cum")]:
            d = p3[key]
            print(f"  {lab:<18} mean={_f(d['mean'])} std={d['std']:.4f} "
                  f"[p05={_f(d['p05'])}, p95={_f(d['p95'])}] frac_pos={d['frac_pos']:.2f}")
        p4 = p["p4"]
        print(f"\n[P4 EXTREMES vs MIDDLE] k={p4['k']} n={p4['n']}")
        print(f"  extremes IC (top+bot {2*p4['k']}): {_f(p4['ext_ic_mean'])}  hit={p4['ext_ic_hit']}")
        print(f"  middle IC ({p4['n'] and ''}~63):        {_f(p4['mid_ic_mean'])}  hit={p4['mid_ic_hit']}")
        print(f"  top{p4['k']} ret={_f(p4['top_ret_mean'])} bot{p4['k']} ret={_f(p4['bot_ret_mean'])} "
              f"mid ret={_f(p4['mid_ret_mean'])} tail-spread={_f(p4['tail_spread'])}")
        p5 = p["p5"]
        print(f"\n[P5 PERIOD ATTRIBUTION] n={p5['n']} total spread sum={_f(p5['total_spread'])}")
        print(f"  top-3 periods share of total: {p5['top3_share']}  dates={p5['top3_dates']}")
        print(f"  single biggest: {p5['max_single']}")
        print("  per-period spread contribution:")
        for c in p5["contrib"]:
            print(f"    {c['date']}  {_f(c['spread'])}")
        p6 = p["p6"]
        print(f"\n[P6 COMPONENT IC] ranked by mean Spearman:")
        for r in p6["table"]:
            print(f"    {r['comp']:>3} {r['name']:<20} spearman={_f(r['spearman_mean'])} "
                  f"tau={_f(r['tau_mean'])} n={r['n']}")
