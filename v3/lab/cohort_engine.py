"""YUCLAW Signal Validation Lab — decile/label cohort event-study engine.

RESEARCH COHORT ANALYSIS. This is an academic event study of whether YUCLAW's
composite signal scores carry forward information — NOT a portfolio, NOT a
strategy, NOT trade advice. Cohorts are named by score decile or signal label,
never by trade direction. The market-neutral line is the "top-decile minus
bottom-decile cohort spread", never "long/short".

Data: READ-ONLY on signal_snapshots + price_history. Only DERIVED statistics
(period returns, cumulative returns, spreads, drawdowns) are produced — raw
closing prices are never returned or displayed (yfinance ToS). All outputs are
YUCLAW-generated and deterministic: every number recomputes from the DB.

Two panels are kept strictly separate and never blended:
  * in_sample  — signal_snapshots.is_backfill = TRUE  (parametric look-ahead;
                 the extraction model's training cutoff overlaps this window)
  * forward    — signal_snapshots.is_backfill = FALSE (Day 0 = 2026-05-18)
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import psycopg2

# ---- fixed, documented methodology constants (reproducibility) --------------
DSN = "dbname=yuclaw_events"
FORWARD_DAY0 = date(2026, 5, 18)
BENCHMARK = "SPY"                 # broad-market benchmark (present in price_history)
DECILE_FRACTION = 0.10           # top/bottom decile by composite total_score
TRADING_DAYS_PER_YEAR = 252
BULLISH_LABELS = ("STRONG_BULLISH", "BULLISH")
CAUTIOUS_LABELS = ("WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT")


# ---- data access (READ-ONLY) ------------------------------------------------
def _connect():
    cn = psycopg2.connect(DSN)
    cn.set_session(readonly=True)
    return cn


def load_snapshots(panel: str) -> dict[date, dict[str, dict[str, Any]]]:
    """{signal_date: {ticker: {'score': float, 'label': str}}} for one panel."""
    is_backfill = panel == "in_sample"
    out: dict[date, dict[str, dict[str, Any]]] = {}
    with _connect() as cn, cn.cursor() as cur:
        cur.execute(
            "SELECT signal_time::date, ticker, total_score, signal_label "
            "FROM signal_snapshots WHERE is_backfill = %s "
            "ORDER BY signal_time::date, ticker",
            (is_backfill,),
        )
        for d, tk, score, label in cur.fetchall():
            out.setdefault(d, {})[tk] = {"score": float(score), "label": label}
    return out


def load_prices() -> tuple[dict[str, dict[date, float]], list[date]]:
    """({ticker: {date: close}}, sorted_trade_dates). Closes used only to derive
    returns; never surfaced."""
    prices: dict[str, dict[date, float]] = {}
    dates: set[date] = set()
    with _connect() as cn, cn.cursor() as cur:
        cur.execute("SELECT ticker, trade_date, close FROM price_history "
                    "WHERE close IS NOT NULL")
        for tk, d, close in cur.fetchall():
            prices.setdefault(tk, {})[d] = float(close)
            dates.add(d)
    return prices, sorted(dates)


# ---- helpers ----------------------------------------------------------------
def _entry_date(trade_dates: list[date], on_or_before: date) -> date | None:
    """Latest trade_date <= on_or_before (price as of the signal date)."""
    chosen = None
    for d in trade_dates:
        if d <= on_or_before:
            chosen = d
        else:
            break
    return chosen


def _period_return(prices: dict[date, float], d0: date, d1: date) -> float | None:
    """close[d1]/close[d0]-1 for one ticker, or None if either price missing."""
    p0, p1 = prices.get(d0), prices.get(d1)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return p1 / p0 - 1.0


def _max_drawdown(cumulative: list[float]) -> float:
    """Most negative (cum/running_peak - 1). 0.0 if never below peak."""
    peak = -math.inf
    mdd = 0.0
    for c in cumulative:
        peak = max(peak, c)
        if peak > 0:
            mdd = min(mdd, c / peak - 1.0)
    return mdd


def _annualize(total_return: float, n_trading_days: int) -> float | None:
    if n_trading_days <= 0:
        return None
    return (1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / n_trading_days) - 1.0


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ---- cohort construction ----------------------------------------------------
def _decile_members(day_scores: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    ranked = sorted(day_scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    n = len(ranked)
    k = max(1, round(n * DECILE_FRACTION))
    top = [tk for tk, _ in ranked[:k]]
    bottom = [tk for tk, _ in ranked[-k:]]
    return top, bottom


def _label_members(day_scores: dict[str, dict[str, Any]], labels: tuple[str, ...]) -> list[str]:
    return [tk for tk, v in day_scores.items() if v["label"] in labels]


# ---- main computation -------------------------------------------------------
def compute_panel(panel: str) -> dict[str, Any]:
    """Compute cohort cumulative-return series + metrics for one panel.

    Rebalance at each distinct signal date; hold each cohort (equal-weighted)
    until the next rebalance, chaining into a cumulative series. Returns a
    fully-derived, raw-price-free result dict. If no period is evaluable (e.g.
    price_history ends before the panel's signals), returns evaluable=False.
    """
    snaps = load_snapshots(panel)
    prices, trade_dates = load_prices()
    bench_px = prices.get(BENCHMARK, {})

    rebal_dates = sorted(snaps.keys())
    cohorts = ("top_decile", "bottom_decile", "bullish_labeled", "cautious_labeled", "benchmark")
    series: dict[str, list[dict[str, Any]]] = {c: [] for c in cohorts}
    period_rets: dict[str, list[float]] = {c: [] for c in cohorts}
    spread_periods: list[float] = []
    cum: dict[str, float] = {c: 1.0 for c in cohorts}
    spread_cum = 1.0
    spread_series: list[dict[str, Any]] = []
    evaluable_periods = 0
    last_exit_date = None

    for i, rd in enumerate(rebal_dates):
        d0 = _entry_date(trade_dates, rd)
        # exit at the entry date of the next rebalance, else last available trade date
        nxt = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else None
        d1 = _entry_date(trade_dates, nxt) if nxt else (trade_dates[-1] if trade_dates else None)
        if d0 is None or d1 is None or d1 <= d0:
            continue  # no evaluable forward price window for this rebalance

        day = snaps[rd]
        top, bottom = _decile_members(day)
        members = {
            "top_decile": top,
            "bottom_decile": bottom,
            "bullish_labeled": _label_members(day, BULLISH_LABELS),
            "cautious_labeled": _label_members(day, CAUTIOUS_LABELS),
        }

        def cohort_ret(tickers: list[str]) -> float | None:
            rs = [r for tk in tickers
                  for r in [_period_return(prices.get(tk, {}), d0, d1)] if r is not None]
            return sum(rs) / len(rs) if rs else None

        bench_ret = _period_return(bench_px, d0, d1)
        if bench_ret is None:
            continue
        evaluable_periods += 1
        last_exit_date = d1

        rets = {c: cohort_ret(members[c]) if c != "benchmark" else bench_ret
                for c in cohorts}
        for c in cohorts:
            r = rets[c] if rets[c] is not None else 0.0
            cum[c] *= (1.0 + r)
            period_rets[c].append(r)
            series[c].append({"date": d1.isoformat(), "cum": cum[c],
                              "n": len(members[c]) if c != "benchmark" else 1})
        # spread = top-decile minus bottom-decile cohort (NEVER long/short)
        sp = (rets["top_decile"] or 0.0) - (rets["bottom_decile"] or 0.0)
        spread_cum *= (1.0 + sp)
        spread_periods.append(sp)
        spread_series.append({"date": d1.isoformat(), "cum": spread_cum})

    if evaluable_periods == 0:
        return {
            "panel": panel, "evaluable": False, "evaluable_periods": 0,
            "rebalance_dates": len(rebal_dates),
            "signal_date_range": [rebal_dates[0].isoformat(), rebal_dates[-1].isoformat()] if rebal_dates else None,
            "price_coverage_end": trade_dates[-1].isoformat() if trade_dates else None,
            "reason": "No evaluable forward price window: price_history coverage "
                      "ends before post-signal returns can be measured.",
        }

    # span of trading days actually covered (entry of first rebalance -> last exit)
    first_entry = _entry_date(trade_dates, rebal_dates[0])
    span_td = sum(1 for d in trade_dates if first_entry <= d <= last_exit_date)

    def metrics(c: str) -> dict[str, Any]:
        cumret = cum[c] - 1.0
        curve = [pt["cum"] for pt in series[c]]
        sizes = sorted(pt["n"] for pt in series[c])
        n_min = sizes[0] if sizes else 0
        n_max = sizes[-1] if sizes else 0
        n_med = sizes[len(sizes) // 2] if sizes else 0
        return {
            "cumulative_return": cumret,
            "annualized_return": _annualize(cumret, span_td),
            "max_drawdown": _max_drawdown(curve),
            "volatility_periodic": _stdev(period_rets[c]),
            "hit_rate_vs_benchmark": (
                sum(1 for a, b in zip(period_rets[c], period_rets["benchmark"]) if a > b)
                / len(period_rets[c]) if c != "benchmark" else None),
            # cohort-size disclosure: small-n cohorts are noisy/illustrative, not robust
            "cohort_n_min": n_min,
            "cohort_n_median": n_med,
            "cohort_n_max": n_max,
            # thin = cohort dropped below 3 names at least once -> noisy/illustrative
            "thin": (n_min < 3 and c != "benchmark"),
        }

    spread_curve = [pt["cum"] for pt in spread_series]
    return {
        "panel": panel,
        "evaluable": True,
        "evaluable_periods": evaluable_periods,
        "span_trading_days": span_td,
        "rebalance_dates": len(rebal_dates),
        "signal_date_range": [rebal_dates[0].isoformat(), rebal_dates[-1].isoformat()],
        "price_coverage_end": trade_dates[-1].isoformat(),
        "benchmark": BENCHMARK,
        "series": series,
        "spread_series": spread_series,
        "metrics": {c: metrics(c) for c in cohorts},
        "spread_metrics": {
            "cumulative_return": spread_cum - 1.0,
            "max_drawdown": _max_drawdown(spread_curve),
            "volatility_periodic": _stdev(spread_periods),
        },
    }


def compute_all() -> dict[str, Any]:
    return {"forward": compute_panel("forward"), "in_sample": compute_panel("in_sample")}


if __name__ == "__main__":
    import json
    res = compute_all()
    for panel in ("forward", "in_sample"):
        p = res[panel]
        print(f"\n=== {panel} === evaluable={p['evaluable']} periods={p.get('evaluable_periods')}")
        if p["evaluable"]:
            for c, m in p["metrics"].items():
                print(f"  {c:18s} cum={m['cumulative_return']:+.4f} "
                      f"mdd={m['max_drawdown']:+.4f} hit={m['hit_rate_vs_benchmark']}")
            print(f"  spread(top-bottom) cum={p['spread_metrics']['cumulative_return']:+.4f}")
        else:
            print(f"  {p['reason']}")
