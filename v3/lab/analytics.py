"""YUCLAW Validation Lab — academic analytics (decile spectrum, information
coefficient, event study, turnover/stability).

RESEARCH COHORT ANALYSIS — descriptive statistics only. Cohorts/deciles are
formed by composite score rank; nothing here is a position, a strategy, or trade
advice. Only DERIVED statistics (ranks, returns, spreads, correlations) are
produced — raw prices are never returned. Read-only on signal_snapshots +
price_history. Two panels ('in_sample', 'forward') are computed separately and
never blended.

Reuses cohort_engine's loaders/helpers so the return convention is identical to
the cohort spread (close-to-close, point-in-time entry on/<= the signal date).
"""

from __future__ import annotations

import math
from typing import Any

from v3.lab.cohort_engine import (
    BENCHMARK, _entry_date, _period_return, load_prices, load_snapshots,
)

N_DECILES = 10
EVENT_HORIZON = 20  # trading days tracked after a decile-entry event


# ---- rank statistics (no scipy) --------------------------------------------
def _ranks(xs: list[float]) -> list[float]:
    """Average (fractional) ranks, ties shared."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation = Pearson on ranks."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ---- per-rebalance data (the spine for IC / decile / turnover) -------------
def per_rebalance(panel: str) -> list[dict[str, Any]]:
    """For each rebalance date: list of (ticker, score, fwd_return) over the
    next inter-rebalance period, plus the benchmark return. Rebalances with no
    evaluable forward price window are dropped."""
    snaps = load_snapshots(panel)
    prices, trade_dates = load_prices()
    bench_px = prices.get(BENCHMARK, {})
    rdates = sorted(snaps.keys())
    out = []
    for i, rd in enumerate(rdates):
        d0 = _entry_date(trade_dates, rd)
        nxt = rdates[i + 1] if i + 1 < len(rdates) else None
        d1 = _entry_date(trade_dates, nxt) if nxt else (trade_dates[-1] if trade_dates else None)
        if d0 is None or d1 is None or d1 <= d0:
            continue
        bench_ret = _period_return(bench_px, d0, d1)
        if bench_ret is None:
            continue
        items = []
        for tk, v in snaps[rd].items():
            r = _period_return(prices.get(tk, {}), d0, d1)
            if r is not None:
                items.append((tk, float(v["score"]), r))
        if len(items) >= N_DECILES:
            out.append({"date": rd, "items": items, "bench_ret": bench_ret})
    return out


# ---- (a) full decile spectrum ----------------------------------------------
def decile_spectrum(panel: str) -> dict[str, Any]:
    """D1(top score)..D10(bottom): pooled mean next-period return per decile.
    Monotonicity = Spearman rho between score-decile order and mean return."""
    rebs = per_rebalance(panel)
    if not rebs:
        return {"evaluable": False, "n_rebalances": 0}
    bucket_rets: list[list[float]] = [[] for _ in range(N_DECILES)]
    for reb in rebs:
        ranked = sorted(reb["items"], key=lambda t: t[1], reverse=True)  # top score first
        n = len(ranked)
        for k in range(N_DECILES):
            lo = (k * n) // N_DECILES
            hi = ((k + 1) * n) // N_DECILES
            seg = ranked[lo:hi]
            if seg:
                bucket_rets[k].append(sum(t[2] for t in seg) / len(seg))
    decile_mean = [(sum(b) / len(b)) if b else None for b in bucket_rets]
    # monotonicity: x = decile score-strength (10=top..1=bottom), y = mean return
    xs = [N_DECILES - k for k in range(N_DECILES) if decile_mean[k] is not None]
    ys = [decile_mean[k] for k in range(N_DECILES) if decile_mean[k] is not None]
    rho = spearman([float(x) for x in xs], ys)
    d_top, d_bot = decile_mean[0], decile_mean[-1]
    # count monotonic-decreasing steps D1->D10 (top should beat next, etc.)
    mono_steps = sum(1 for k in range(N_DECILES - 1)
                     if decile_mean[k] is not None and decile_mean[k + 1] is not None
                     and decile_mean[k] >= decile_mean[k + 1])
    return {
        "evaluable": True, "n_rebalances": len(rebs),
        "decile_mean_return": decile_mean,          # index 0 = D1 (top)
        "spearman_rho": rho,                         # >0 = higher score -> higher return
        "top_minus_bottom": (d_top - d_bot) if (d_top is not None and d_bot is not None) else None,
        "monotonic_steps": mono_steps, "max_steps": N_DECILES - 1,
    }


# ---- (b) information coefficient --------------------------------------------
def information_coefficient(panel: str) -> dict[str, Any]:
    """Per-rebalance Spearman IC (score vs next-period return). Descriptive."""
    rebs = per_rebalance(panel)
    series = []
    for reb in rebs:
        scores = [t[1] for t in reb["items"]]
        rets = [t[2] for t in reb["items"]]
        ic = spearman(scores, rets)
        if ic is not None:
            series.append({"date": reb["date"].isoformat(), "ic": ic, "n": len(reb["items"])})
    ics = [s["ic"] for s in series]
    mean_ic = (sum(ics) / len(ics)) if ics else None
    std_ic = _stdev(ics) if len(ics) >= 2 else None
    return {
        "evaluable": bool(series), "series": series, "n_points": len(series),
        "mean_ic": mean_ic, "std_ic": std_ic,
        "hit_rate_pos": (sum(1 for i in ics if i > 0) / len(ics)) if ics else None,
        "icir": (mean_ic / std_ic) if (mean_ic is not None and std_ic) else None,
    }


# ---- (c) event study --------------------------------------------------------
def event_study(panel: str, which: str = "top") -> dict[str, Any]:
    """Average cumulative return RELATIVE TO SPY in event time (days 0..H) after
    a name ENTERS the top (or bottom) decile. ±1 stdev band. Descriptive."""
    snaps = load_snapshots(panel)
    prices, trade_dates = load_prices()
    bench_px = prices.get(BENCHMARK, {})
    rdates = sorted(snaps.keys())

    def decile_members(day: dict, top: bool) -> set:
        ranked = sorted(day.items(), key=lambda kv: kv[1]["score"], reverse=True)
        n = len(ranked)
        k = max(1, n // N_DECILES)
        seg = ranked[:k] if top else ranked[-k:]
        return {tk for tk, _ in seg}

    # entries: in the decile at t but NOT at t-1
    entries: list[tuple[Any, str]] = []
    prev: set = set()
    for rd in rdates:
        cur = decile_members(snaps[rd], which == "top")
        for tk in (cur - prev):
            entries.append((rd, tk))
        prev = cur

    # for each entry, cumulative (ticker - SPY) return over event days 0..H
    paths: list[list[float]] = []
    for rd, tk in entries:
        d0 = _entry_date(trade_dates, rd)
        if d0 is None:
            continue
        future = [d for d in trade_dates if d >= d0][:EVENT_HORIZON + 1]
        if len(future) < 3:  # need a few days to be meaningful
            continue
        p = prices.get(tk, {})
        path = []
        for d in future:
            tr = _period_return(p, d0, d)
            br = _period_return(bench_px, d0, d)
            if tr is None or br is None:
                break
            path.append((tr - br))  # excess vs SPY, cumulative from day 0
        if len(path) >= 3:
            paths.append(path)

    H = max((len(p) for p in paths), default=0)
    mean_curve, band = [], []
    for day in range(H):
        vals = [p[day] for p in paths if len(p) > day]
        if vals:
            m = sum(vals) / len(vals)
            mean_curve.append(m)
            band.append(_stdev(vals))
    return {
        "evaluable": bool(mean_curve), "which": which, "n_events": len(paths),
        "mean_curve": mean_curve, "stdev_band": band, "horizon": len(mean_curve),
    }


# ---- (e) cohort stability / turnover ---------------------------------------
def turnover(panel: str) -> dict[str, Any]:
    """Per-rebalance top-decile turnover (% of names replaced vs prior rebalance)
    + average holding persistence (rebalances a name stays in the top decile)."""
    snaps = load_snapshots(panel)
    rdates = sorted(snaps.keys())

    def top_decile(day: dict) -> set:
        ranked = sorted(day.items(), key=lambda kv: kv[1]["score"], reverse=True)
        k = max(1, len(ranked) // N_DECILES)
        return {tk for tk, _ in ranked[:k]}

    series, prev = [], None
    membership_runs: dict[str, int] = {}
    runs: list[int] = []
    for rd in rdates:
        cur = top_decile(snaps[rd])
        if prev is not None and prev:
            replaced = len(prev - cur)
            series.append({"date": rd.isoformat(), "turnover": replaced / len(prev),
                           "n": len(cur)})
        # persistence runs
        for tk in list(membership_runs):
            if tk not in cur:
                runs.append(membership_runs.pop(tk))
        for tk in cur:
            membership_runs[tk] = membership_runs.get(tk, 0) + 1
        prev = cur
    runs.extend(membership_runs.values())
    tos = [s["turnover"] for s in series]
    return {
        "evaluable": bool(series), "series": series, "n_points": len(series),
        "mean_turnover": (sum(tos) / len(tos)) if tos else None,
        "mean_persistence": (sum(runs) / len(runs)) if runs else None,
    }


def compute_all_analytics() -> dict[str, Any]:
    out = {}
    for panel in ("forward", "in_sample"):
        out[panel] = {
            "decile_spectrum": decile_spectrum(panel),
            "ic": information_coefficient(panel),
            "event_top": event_study(panel, "top"),
            "event_bottom": event_study(panel, "bottom"),
            "turnover": turnover(panel),
        }
    return out


if __name__ == "__main__":
    a = compute_all_analytics()
    for panel in ("in_sample", "forward"):
        p = a[panel]
        ds, ic = p["decile_spectrum"], p["ic"]
        print(f"\n=== {panel} ===")
        if ds["evaluable"]:
            print("  decile D1..D10 mean ret:", [f"{x:+.3f}" if x is not None else "—" for x in ds["decile_mean_return"]])
            print(f"  spearman(score-decile, return)={ds['spearman_rho']}  top-bottom={ds['top_minus_bottom']}  mono_steps={ds['monotonic_steps']}/{ds['max_steps']}")
        if ic["evaluable"]:
            print(f"  IC: n={ic['n_points']} mean={ic['mean_ic']} hit>0={ic['hit_rate_pos']} ICIR={ic['icir']}")
        print(f"  turnover mean={p['turnover']['mean_turnover']} persistence={p['turnover']['mean_persistence']}")
        print(f"  event(top) n_events={p['event_top']['n_events']} horizon={p['event_top']['horizon']}")
