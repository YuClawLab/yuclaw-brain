"""Panel 4 — Evidence-Qualified Protocol Candidate cohort.

Same decile methodology as the main Lab, restricted to names meeting minimum
evidence criteria AS OF each signal date (point-in-time; no hindsight):

  QUALIFIED(date, ticker) iff
      grade in (A, B)                      -- evidence-quality grade rubric
   OR cited_filings >= 1                   -- snapshot cites >= 1 filing
   OR last SourceLock-accepted event within the trailing 30 days
  AND grade != "Insufficient"              -- composite_confidence >= 0.30

"SourceLock-accepted" = the event passed the deterministic R1–R8 extraction
validator (v3/extract/sourcelock.py); every accepted row in `events` did.

SCOPE (honest, structural): evidence-quality fields (composite_confidence,
evidence_event_ids) exist only from the v4.0 launch on 2026-06-01, so this
panel is FORWARD-ONLY from that date. No in-sample variant is possible
without fabricating grades retroactively — so none is shown.

Outputs are derived statistics only. Read-only on the DB.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import psycopg2

from v3.lab.cohort_engine import (DECILE_FRACTION, DSN, _entry_date, _grade_label,
                                  _max_drawdown, _period_return, load_prices)
from v3.lab.stats import mean as _mean
from v3.lab.stats import stdev

QUALIFIED_START = date(2026, 6, 1)   # first date with evidence-quality fields
EVIDENCE_FRESH_DAYS = 30             # trailing SourceLock-evidence window
STALE_DAYS = 90                      # evidence-age stale flag threshold


def _load_qualified_snapshots() -> dict[date, dict[str, dict[str, Any]]]:
    """{signal_date: {ticker: {...}}} for forward dates >= QUALIFIED_START,
    latest snapshot per (date, ticker), with point-in-time evidence fields."""
    q = """
        SELECT DISTINCT ON (s.signal_time::date, s.ticker)
               s.signal_time::date AS d, s.ticker, s.total_score, s.signal_label,
               s.composite_confidence,
               COALESCE(array_length(s.evidence_event_ids, 1), 0) AS evc,
               (SELECT count(*) FROM events e
                  WHERE e.event_id = ANY(s.evidence_event_ids)
                    AND e.llm_confidence >= 0.7) AS strong,
               s.c6_event_impact,
               (SELECT max(e2.event_time)::date FROM events e2
                  WHERE e2.ticker = s.ticker AND e2.event_status = 'accepted'
                    AND e2.event_time::date <= s.signal_time::date) AS last_ev
        FROM signal_snapshots s
        WHERE s.is_backfill = false AND s.signal_time::date >= %s
        ORDER BY s.signal_time::date, s.ticker, s.signal_time DESC
    """
    out: dict[date, dict[str, dict[str, Any]]] = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(q, (QUALIFIED_START,))
            for d, tk, score, label, conf, evc, strong, c6, last_ev in cur.fetchall():
                conf_f = float(conf) if conf is not None else None
                grade = _grade_label(conf_f, int(evc or 0), int(strong or 0))
                age = (d - last_ev).days if last_ev else None
                qualified = (
                    grade in ("Grade A", "Grade B")
                    or int(evc or 0) >= 1
                    or (age is not None and age <= EVIDENCE_FRESH_DAYS)
                ) and grade != "Insufficient"
                out.setdefault(d, {})[tk] = {
                    "score": float(score), "label": label, "grade": grade,
                    "evc": int(evc or 0), "c6": float(c6) if c6 is not None else None,
                    "evidence_age": age, "qualified": qualified,
                }
    return out


def compute_qualified() -> dict[str, Any]:
    snaps = _load_qualified_snapshots()
    prices, trade_dates = load_prices()
    rebal_dates = sorted(snaps.keys())

    cum = {"qualified_ew": 1.0, "qualified_top": 1.0, "universe_ew": 1.0}
    series = {c: [] for c in cum}
    period_rets = {c: [] for c in cum}
    pool_sizes, top_sizes, ages_all, c6_flags = [], [], [], []
    evaluable = 0
    first_entry = last_exit = None

    for i, rd in enumerate(rebal_dates):
        d0 = _entry_date(trade_dates, rd)
        nxt = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else None
        d1 = _entry_date(trade_dates, nxt) if nxt else (trade_dates[-1] if trade_dates else None)
        if d0 is None or d1 is None or d1 <= d0:
            continue
        day = snaps[rd]
        pool = {tk: v for tk, v in day.items() if v["qualified"]}
        if not pool:
            continue
        k = max(1, round(len(pool) * DECILE_FRACTION))
        top = [tk for tk, _ in sorted(pool.items(), key=lambda kv: kv[1]["score"],
                                      reverse=True)[:k]]

        def cret(tks):
            vals = [r for tk in tks
                    for r in [_period_return(prices.get(tk, {}), d0, d1)] if r is not None]
            return sum(vals) / len(vals) if vals else None

        rets = {"qualified_ew": cret(list(pool)), "qualified_top": cret(top),
                "universe_ew": cret(list(day))}
        if rets["universe_ew"] is None:
            continue
        evaluable += 1
        if first_entry is None:
            first_entry = d0
        last_exit = d1
        pool_sizes.append(len(pool))
        top_sizes.append(len(top))
        ages_all.extend(v["evidence_age"] for v in pool.values()
                        if v["evidence_age"] is not None)
        c6_flags.append(sum(1 for v in pool.values() if v["c6"]) / len(pool))
        for c in cum:
            r = rets[c] if rets[c] is not None else 0.0
            cum[c] *= (1.0 + r)
            period_rets[c].append(r)
            series[c].append({"date": d1.isoformat(), "cum": cum[c],
                              "n": len(pool) if c == "qualified_ew"
                                   else (len(top) if c == "qualified_top" else len(day))})

    if evaluable == 0:
        return {"evaluable": False, "reason": "no qualified rebalances"}

    ages_sorted = sorted(ages_all)
    pool_sorted = sorted(pool_sizes)

    def metrics(c):
        curve = [pt["cum"] for pt in series[c]]
        return {"cumulative_return": cum[c] - 1.0,
                "max_drawdown": _max_drawdown(curve),
                "volatility_periodic": stdev(period_rets[c])}

    # current membership (latest rebalance date)
    latest = rebal_dates[-1]
    day = snaps[latest]
    members = sorted((dict(v, ticker=tk) for tk, v in day.items() if v["qualified"]),
                     key=lambda m: -m["score"])
    k_latest = max(1, round(len(members) * DECILE_FRACTION))

    return {
        "evaluable": True,
        "start": QUALIFIED_START.isoformat(),
        "window": [first_entry.isoformat(), last_exit.isoformat()],
        "evaluable_periods": evaluable,
        "pool": {"min": pool_sorted[0], "median": pool_sorted[len(pool_sorted) // 2],
                 "max": pool_sorted[-1]},
        "top_n": {"min": min(top_sizes), "max": max(top_sizes)},
        "universe_n": 79,
        "coverage_median": pool_sorted[len(pool_sorted) // 2] / 79,
        "median_evidence_age": ages_sorted[len(ages_sorted) // 2] if ages_sorted else None,
        "c6_coverage_mean": _mean(c6_flags) if c6_flags else None,
        "series": series,
        "period_returns": period_rets,
        "metrics": {c: metrics(c) for c in cum},
        "members": members,
        "k_latest": k_latest,
        "as_of": latest.isoformat(),
        "criteria": ("grade A/B OR >=1 cited filing OR SourceLock-accepted event "
                     f"within {EVIDENCE_FRESH_DAYS}d; grade 'Insufficient' excluded"),
        "stale_days": STALE_DAYS,
    }


if __name__ == "__main__":
    import json
    r = compute_qualified()
    if r["evaluable"]:
        print(f"window {r['window']} periods={r['evaluable_periods']} "
              f"pool median={r['pool']['median']} (min {r['pool']['min']}, max {r['pool']['max']}) "
              f"top n={r['top_n']} median_age={r['median_evidence_age']}d "
              f"c6_cov={r['c6_coverage_mean']:.2f}")
        for c, m in r["metrics"].items():
            print(f"  {c:14s} cum={m['cumulative_return']:+.4f} mdd={m['max_drawdown']:+.4f} "
                  f"vol={m['volatility_periodic']*100:.2f}%")
        print(f"  members as of {r['as_of']}: {len(r['members'])} qualified, "
              f"top decile k={r['k_latest']}: {[m['ticker'] for m in r['members'][:r['k_latest']]]}")
    else:
        print(r)