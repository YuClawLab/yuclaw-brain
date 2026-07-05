"""YUCLAW Validation Lab — statistical rigor panel (Part 1 of the academic pass).

Computes, per panel (forward OOS and in-sample replay, NEVER blended):

1. Decile spread tests — top-minus-bottom and top-minus-equal-weight-universe
   per-rebalance arithmetic return spreads: mean, percentile-bootstrap 95% CI
   (i.i.d. resampling of rebalance periods, 10,000 draws, fixed seed), one-sample
   t vs 0, n periods, window dates.
2. Information coefficient — per-signal-date cross-sectional Spearman IC of
   composite total_score vs realized forward return at the track-record horizons
   (1d / 5d / 20d), Fama-MacBeth style: mean IC, t-stat across dates, T dates,
   median cross-section size. Cross-sections below MIN_UNIVERSE_FOR_DECILES
   tickers are excluded (same inclusion rule as the cohort study).
3. Market-model check — OLS of top-decile per-period cohort returns on the
   equal-weight universe (and separately on SPY): alpha (annualized via the
   panel's average holding period), beta, t(alpha), R², n. Includes a
   minimum-detectable-alpha power note for honest "not yet significant" display.

RESEARCH STATISTICS ONLY — descriptive/inferential statistics about research
cohorts; nothing here is a position, a strategy, or advice. Read-only on the DB.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg2

from v3.lab.cohort_engine import (DSN, MIN_UNIVERSE_FOR_DECILES, TRADING_DAYS_PER_YEAR,
                                  compute_panel)
from v3.lab.stats import (bootstrap_ci_mean, mde_alpha_daily, newey_west_t, ols,
                          one_sample_t, spearman)

IC_HORIZONS = (1, 5, 20)


# ---- 1. spread tests ---------------------------------------------------------
def spread_tests(panel_result: dict[str, Any]) -> dict[str, Any]:
    pr = panel_result["period_returns"]
    out = {}
    for key, a, b in (("top_minus_bottom", "top_decile", "bottom_decile"),
                      ("top_minus_universe", "top_decile", "universe_ew")):
        diffs = [pr[a][i] - pr[b][i] for i in range(len(pr[a]))]
        t = one_sample_t(diffs)
        out[key] = {
            "mean_per_period": t["mean"],
            "t_stat": t["t"],
            "p_value": t["p"],
            "n_periods": t["n"],
            "ci95": bootstrap_ci_mean(diffs),
            "bootstrap": "percentile, 10,000 i.i.d. resamples of rebalance periods, seed 20260518",
        }
    out["window"] = [panel_result["first_entry_date"], panel_result["last_exit_date"]]
    return out


# ---- 2. information coefficient ----------------------------------------------
def information_coefficient(panel: str) -> dict[int, dict[str, Any]]:
    """Per-horizon Fama-MacBeth IC from track_record (as-of matured outcomes)."""
    is_backfill = panel == "in_sample"
    out: dict[int, dict[str, Any]] = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            for h in IC_HORIZONS:
                cur.execute(
                    f"SELECT signal_date, total_score, return_{h}d "
                    f"FROM track_record WHERE is_backfill = %s AND return_{h}d IS NOT NULL "
                    f"ORDER BY signal_date",
                    (is_backfill,),
                )
                by_date: dict[Any, list[tuple[float, float]]] = {}
                for d, score, ret in cur.fetchall():
                    by_date.setdefault(d, []).append((float(score), float(ret)))
                ics, ns, ic_dates = [], [], []
                for d, rows in sorted(by_date.items()):
                    if len(rows) < MIN_UNIVERSE_FOR_DECILES:
                        continue
                    rho = spearman([r[0] for r in rows], [r[1] for r in rows])
                    if rho is not None:
                        ics.append(rho)
                        ns.append(len(rows))
                        ic_dates.append(d)
                if len(ics) >= 2:
                    t = one_sample_t(ics)
                    # Overlap correction: consecutive signal dates share most of an
                    # h-day return window, so the IC series is serially correlated
                    # and the naive t overstates significance. Use Newey-West with
                    # lag = ceil(h / average-date-spacing) - 1 (Bartlett kernel).
                    span_days = (ic_dates[-1] - ic_dates[0]).days or 1
                    avg_spacing_td = max(1.0, span_days * (5.0 / 7.0) / max(1, len(ics) - 1))
                    lag = max(0, math.ceil(h / avg_spacing_td) - 1)
                    nw = newey_west_t(ics, lag)
                    ns_sorted = sorted(ns)
                    out[h] = {
                        "mean_ic": t["mean"], "t_stat": t["t"], "p_value": t["p"],
                        "nw_lag": nw["lag"], "nw_t_stat": nw["t"], "nw_p_value": nw["p"],
                        # NW needs enough independent blocks; below ~3 the HAC SE
                        # itself is unreliable -> statistic is descriptive only
                        "t_reliable": (len(ics) / (nw["lag"] + 1)) >= 3.0,
                        "n_dates": t["n"],
                        "median_cross_section": ns_sorted[len(ns_sorted) // 2],
                        "ic_positive_share": sum(1 for x in ics if x > 0) / len(ics),
                        "date_range": [str(min(by_date)), str(max(by_date))],
                    }
                elif len(ics) == 1:
                    out[h] = {"mean_ic": ics[0], "t_stat": None, "p_value": None,
                              "n_dates": 1, "median_cross_section": ns[0],
                              "ic_positive_share": None,
                              "date_range": [str(min(by_date)), str(max(by_date))]}
                else:
                    out[h] = {"mean_ic": None, "t_stat": None, "p_value": None,
                              "n_dates": 0, "median_cross_section": None,
                              "ic_positive_share": None, "date_range": None}
    return out


# ---- 3. market model -----------------------------------------------------------
def market_model(panel_result: dict[str, Any]) -> dict[str, Any]:
    pr = panel_result["period_returns"]
    n = panel_result["evaluable_periods"]
    span = panel_result["span_trading_days"]
    periods_per_year = TRADING_DAYS_PER_YEAR / (span / n) if n else None
    out: dict[str, Any] = {"periods_per_year": periods_per_year,
                           "avg_holding_td": span / n if n else None,
                           "window": [panel_result["first_entry_date"],
                                      panel_result["last_exit_date"]]}
    for key, mkt in (("vs_universe", "universe_ew"), ("vs_spy", "benchmark")):
        r = ols(pr["top_decile"], pr[mkt])
        if r is None:
            out[key] = None
            continue
        ann = (1.0 + r["alpha"]) ** periods_per_year - 1.0 if periods_per_year else None
        mde = mde_alpha_daily(r["se_alpha"], r["n"] - 2)
        mde_ann = ((1.0 + mde) ** periods_per_year - 1.0
                   if (mde is not None and periods_per_year) else None)
        out[key] = {
            "alpha_per_period": r["alpha"], "alpha_annualized": ann,
            "beta": r["beta"], "t_alpha": r["t_alpha"], "p_alpha": r["p_alpha"],
            "r2": r["r2"], "n_periods": r["n"],
            "mde_alpha_annualized": mde_ann,   # detectable |alpha| at 80% power, 5% level
        }
    return out


# ---- assemble ------------------------------------------------------------------
def compute_rigor() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for panel in ("forward", "in_sample"):
        pres = compute_panel(panel)
        if not pres.get("evaluable"):
            out[panel] = {"evaluable": False}
            continue
        out[panel] = {
            "evaluable": True,
            "spreads": spread_tests(pres),
            "ic": information_coefficient(panel),
            "market_model": market_model(pres),
            "n_periods": pres["evaluable_periods"],
            "window": [pres["first_entry_date"], pres["last_exit_date"]],
        }
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(compute_rigor(), indent=2, default=str))
