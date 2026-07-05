"""YUCLAW AI-ETF Evidence Module — SMH-class semiconductor theme, done as an
event study on EDGAR-filing constituents.

Scope (stated honestly, and rendered on the page):
  * Theme instrument: SMH (VanEck Semiconductor ETF). Constituent list is a
    DATED public fund-disclosure snapshot (holdings as of 2026-07-03, 26
    holdings, 25 disclosed below; the remaining sliver is undisclosed in the
    free listing). Fund holdings/weights are issuer disclosures, not exchange
    market data — no market-data vendor content is stored or re-published.
  * Evidence coverage = SMH constituents ∩ YUCLAW's 79-ticker universe
    (8 U.S. EDGAR filers). Foreign-domiciled constituents (TSM, ASML, STM,
    NXPI) file 20-F/6-K annually/occasionally, not the 8-K + Form 4 event
    stream this pipeline consumes — they are out of evidence scope, which is
    why foreign-holdings ETFs (e.g. KORU-class country funds) cannot be
    covered by this methodology at all: their constituents produce no EDGAR
    event substrate.

Event study: cumulative abnormal returns (CAR) around accepted L1 evidence
events on covered constituents.
  * DEDUP: multiple filings for the same (ticker, event type, day) — common
    for Form 4 batches — collapse to ONE event observation; both counts are
    reported. Without this, insider-sell clusters pseudo-replicate.
  * TWO abnormal-return models, shown side by side, never averaged:
      - peer model (headline): market = equal-weight of the OTHER covered
        semiconductor constituents that day (excludes the event ticker), so
        the sector melt-up/melt-down factor is removed. This is the fair
        test of whether the evidence adds information BEYOND the theme move.
      - SPY market model (secondary): classic market model; in a strong
        sector regime its "abnormal" return is dominated by the sector
        factor, which is exactly what it shows.
  * Estimation: up to 60 trading days ending 6 days before day 0 (min 30
    obs). Day 0 = first trading day on/after the event timestamp's date.
    CAR window [-5, +20] event-time days. Mean CAR per event type with a
    normal-approximation 95% CI across events, n disclosed at every horizon.
  * Direction-aligned pooled CAR (AR x direction, direction != 0) is the
    "does evidence detection precede full price adjustment" test.
  * Cross-sectional clustering caveat: distinct ticker-days can still share
    calendar days across tickers; CIs assume independence and are therefore
    optimistic. Stated on the page.

RESEARCH STATISTICS ONLY. Derived statistics (returns, CARs, counts, grades);
raw prices never returned. Read-only on the DB.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import psycopg2

from v3.lab.cohort_engine import DSN, FORWARD_DAY0, _grade_label, load_prices
from v3.lab.stats import mean as _mean
from v3.lab.stats import ols, stdev

# ---- dated SMH constituent snapshot (issuer fund disclosure) -----------------
SMH_AS_OF = "2026-07-03"
SMH_SOURCE = "VanEck fund holdings disclosure (25 of 26 holdings public in the free listing)"
SMH_HOLDINGS: dict[str, float] = {
    "NVDA": 19.01, "TSM": 9.40, "AVGO": 5.61, "AMD": 5.58, "MU": 5.34,
    "AMAT": 5.33, "ASML": 4.99, "INTC": 4.88, "KLAC": 4.73, "LRCX": 4.68,
    "TXN": 4.56, "MRVL": 4.27, "ADI": 4.23, "QCOM": 3.97, "CDNS": 2.38,
    "SNPS": 1.95, "STM": 1.28, "TER": 1.27, "MPWR": 1.26, "NXPI": 1.24,
    "ALAB": 1.19, "ARM": 1.15, "MCHP": 0.93, "ON": 0.62, "SWKS": 0.16,
}
FOREIGN_DOMICILED = {"TSM", "ASML", "STM", "NXPI"}  # 20-F/6-K filers, no 8-K/Form-4 stream

CAR_PRE, CAR_POST = 5, 20          # CAR window [-5, +20] in event-time trading days
EST_WIN, EST_GAP, EST_MIN = 60, 6, 30  # market-model estimation window parameters
MARKET = "SPY"


def _universe() -> list[str]:
    import json
    from pathlib import Path
    u = json.loads((Path(__file__).resolve().parents[1] / "universe.json").read_text())
    return u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"]


def overlap_summary() -> dict[str, Any]:
    uni = set(_universe())
    covered = sorted(t for t in SMH_HOLDINGS if t in uni)
    uncovered = sorted(t for t in SMH_HOLDINGS if t not in uni)
    w_cov = sum(SMH_HOLDINGS[t] for t in covered)
    return {
        "etf": "SMH", "as_of": SMH_AS_OF, "source": SMH_SOURCE,
        "n_holdings_disclosed": len(SMH_HOLDINGS),
        "covered": covered, "n_covered": len(covered),
        "covered_weight_pct": round(w_cov, 2),
        "uncovered": uncovered,
        "foreign_uncovered": sorted(FOREIGN_DOMICILED),
        "weights_covered": {t: SMH_HOLDINGS[t] for t in covered},
    }


# ---- current evidence posture -------------------------------------------------
def evidence_rollup() -> dict[str, Any]:
    """Latest forward snapshot per covered constituent + trailing event counts,
    plus a weight-normalized ETF-level rollup. Derived data only."""
    ov = overlap_summary()
    covered = ov["covered"]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (s.ticker)
                       s.ticker, s.signal_time::date, s.signal_label, s.total_score,
                       s.c6_event_impact, s.composite_confidence,
                       COALESCE(array_length(s.evidence_event_ids,1),0),
                       (SELECT count(*) FROM events e
                          WHERE e.event_id = ANY(s.evidence_event_ids)
                            AND e.llm_confidence >= 0.7)
                   FROM signal_snapshots s
                   WHERE s.is_backfill = false AND s.ticker = ANY(%s)
                   ORDER BY s.ticker, s.signal_time DESC""",
                (covered,),
            )
            snap_rows = cur.fetchall()
            cur.execute(
                """SELECT ticker, event_type, count(*),
                          count(*) FILTER (WHERE event_time >= now() - interval '30 days')
                   FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)
                   GROUP BY 1, 2""",
                (covered,),
            )
            ev_rows = cur.fetchall()

    events_by_tk: dict[str, dict[str, dict[str, int]]] = {}
    for tk, et, n_all, n_30 in ev_rows:
        events_by_tk.setdefault(tk, {})[et] = {"total": int(n_all), "last_30d": int(n_30)}

    members = []
    for tk, as_of, label, score, c6, conf, evc, strong in snap_rows:
        members.append({
            "ticker": tk, "as_of": as_of.isoformat(),
            "label": label, "score": float(score),
            "c6": float(c6) if c6 is not None else None,
            "grade": _grade_label(float(conf) if conf is not None else None,
                                  int(evc or 0), int(strong or 0)),
            "weight_pct": SMH_HOLDINGS[tk],
            "events": events_by_tk.get(tk, {}),
            "events_total": sum(v["total"] for v in events_by_tk.get(tk, {}).values()),
            "events_30d": sum(v["last_30d"] for v in events_by_tk.get(tk, {}).values()),
        })
    members.sort(key=lambda m: -m["weight_pct"])

    w_sum = sum(m["weight_pct"] for m in members) or 1.0
    rollup = {
        "weighted_score": sum(m["score"] * m["weight_pct"] for m in members) / w_sum,
        "weighted_c6": (sum((m["c6"] or 0.0) * m["weight_pct"] for m in members) / w_sum),
        "events_total": sum(m["events_total"] for m in members),
        "events_30d": sum(m["events_30d"] for m in members),
        "as_of": max(m["as_of"] for m in members) if members else None,
        "weight_basis_pct": round(w_sum, 2),
    }
    return {"overlap": ov, "members": members, "rollup": rollup}


# ---- event study ---------------------------------------------------------------
def _daily_returns(px: dict[date, float], dates: list[date]) -> dict[date, float]:
    out = {}
    prev = None
    for d in dates:
        p = px.get(d)
        if p is not None and prev is not None and prev[1] != 0:
            out[d] = p / prev[1] - 1.0
        if p is not None:
            prev = (d, p)
    return out


def event_study() -> dict[str, Any]:
    ov = overlap_summary()
    covered = ov["covered"]
    prices, trade_dates = load_prices()
    spy_ret = _daily_returns(prices.get(MARKET, {}), trade_dates)
    tk_ret = {tk: _daily_returns(prices.get(tk, {}), trade_dates) for tk in covered}
    td_index = {d: i for i, d in enumerate(trade_dates)}

    # peer market: for each covered ticker, EW mean of the OTHER covered tickers
    def peer_ret(tk: str) -> dict[date, float]:
        out = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in covered if o != tk]
            vals = [v for v in vals if v is not None]
            if vals:
                out[d] = sum(vals) / len(vals)
        return out
    peer_by_tk = {tk: peer_ret(tk) for tk in covered}

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            # DEDUP at the source: one observation per (ticker, type, direction, day)
            cur.execute(
                """SELECT ticker, event_type, direction, event_time::date AS d,
                          count(*) AS n_filings
                   FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)
                   GROUP BY 1, 2, 3, 4
                   ORDER BY 4""",
                (covered,),
            )
            events = cur.fetchall()
            cur.execute(
                """SELECT count(*) FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)""",
                (covered,),
            )
            n_raw_filings = cur.fetchone()[0]

    skipped_est, skipped_range = 0, 0
    per_event: list[dict[str, Any]] = []
    for tk, et, direction, ev_date, n_filings in events:
        # day 0 = first trading day on/after the event date
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            skipped_range += 1
            continue
        i0 = td_index[day0]
        est_days = trade_dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        ars_by_model: dict[str, dict[int, float]] = {}
        for model, mret in (("peer", peer_by_tk[tk]), ("spy", spy_ret)):
            pairs = [(tk_ret[tk].get(d), mret.get(d)) for d in est_days]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if len(pairs) < EST_MIN:
                continue
            reg = ols([a for a, _ in pairs], [b for _, b in pairs])
            if reg is None:
                continue
            ars = {}
            for tau in range(-CAR_PRE, CAR_POST + 1):
                j = i0 + tau
                if 0 <= j < len(trade_dates):
                    d = trade_dates[j]
                    r, m = tk_ret[tk].get(d), mret.get(d)
                    if r is not None and m is not None:
                        ars[tau] = r - (reg["alpha"] + reg["beta"] * m)
            if ars:
                ars_by_model[model] = ars
        if not ars_by_model:
            skipped_est += 1
            continue
        per_event.append({
            "ticker": tk, "type": et, "direction": int(direction),
            "date": ev_date.isoformat(), "n_filings": int(n_filings),
            "ars_peer": ars_by_model.get("peer"), "ars_spy": ars_by_model.get("spy"),
            "era": "backfill" if ev_date < FORWARD_DAY0 else "live",
        })

    def car_curve(evts: list[dict], signed: bool, model: str) -> dict[str, Any]:
        """Mean CAR path with per-tau n and 95% CI across events."""
        key = f"ars_{model}"
        taus = list(range(-CAR_PRE, CAR_POST + 1))
        curves: list[dict[int, float]] = []
        for e in evts:
            ars = e.get(key)
            if not ars:
                continue
            c, cum = {}, 0.0
            sign = e["direction"] if signed else 1
            for tau in taus:
                if tau not in ars:
                    if tau > min(ars):   # path ended (recent event, short window)
                        break
                    continue
                cum += ars[tau] * sign
                c[tau] = cum
            if c:
                curves.append(c)
        pts = []
        for tau in taus:
            vals = [c[tau] for c in curves if tau in c]
            n = len(vals)
            if n == 0:
                continue
            m = _mean(vals)
            se = (stdev(vals) / math.sqrt(n)) if n >= 3 else None
            pts.append({"tau": tau, "mean_car": m, "n": n,
                        "ci_lo": m - 1.96 * se if se is not None else None,
                        "ci_hi": m + 1.96 * se if se is not None else None})
        return {"points": pts, "n_events": len(curves)}

    def both_models(evts: list[dict], signed: bool) -> dict[str, Any]:
        out = {"peer": car_curve(evts, signed, "peer"),
               "spy": car_curve(evts, signed, "spy")}
        out["date_range"] = ([min(e["date"] for e in evts), max(e["date"] for e in evts)]
                             if evts else None)
        return out

    by_type: dict[str, Any] = {}
    type_counts: dict[str, int] = {}
    for e in per_event:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
    for et, cnt in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        by_type[et] = both_models([e for e in per_event if e["type"] == et], signed=False)

    directional = [e for e in per_event if e["direction"] != 0]
    return {
        "params": {"window": [-CAR_PRE, CAR_POST],
                   "models": {"peer": "EW of the other covered constituents (sector factor removed)",
                              "spy": f"{MARKET} classic market model"},
                   "estimation": f"up to {EST_WIN} trading days ending {EST_GAP} days pre-event, min {EST_MIN} obs",
                   "day0": "first trading day on/after the event timestamp's date",
                   "dedup": "one observation per (ticker, event type, direction, day)"},
        "n_raw_filings": int(n_raw_filings),
        "n_events_deduped": len(events),
        "n_events_used": len(per_event),
        "skipped_insufficient_estimation": skipped_est,
        "skipped_out_of_price_range": skipped_range,
        "by_type": by_type,
        "pooled_directional": both_models(directional, signed=True),
        "pooled_directional_live": both_models([e for e in directional if e["era"] == "live"], signed=True),
        "pooled_directional_backfill": both_models([e for e in directional if e["era"] == "backfill"], signed=True),
        "insider_stream_note": ("Form 4 (insider) events are a parsed batch covering "
                                "2026-02-18 to 2026-05-15; live Form-4 ingestion is a "
                                "tracked pipeline item, so the live-era sample is 8-K "
                                "derived and small."),
        "price_coverage": [trade_dates[0].isoformat(), trade_dates[-1].isoformat()] if trade_dates else None,
    }


def compute_all() -> dict[str, Any]:
    return {"rollup": evidence_rollup(), "event_study": event_study()}


if __name__ == "__main__":
    res = compute_all()
    ov = res["rollup"]["overlap"]
    print(f"SMH coverage: {ov['n_covered']}/{ov['n_holdings_disclosed']} holdings, "
          f"{ov['covered_weight_pct']}% of weight: {ov['covered']}")
    es = res["event_study"]
    print(f"events: raw_filings={es['n_raw_filings']} deduped={es['n_events_deduped']} "
          f"used={es['n_events_used']} skipped_est={es['skipped_insufficient_estimation']}")

    def show(tag, c):
        for model in ("peer", "spy"):
            pts = c[model]["points"]
            if not pts:
                print(f"  {tag:24s} [{model}] no points")
                continue
            last = pts[-1]
            ci = (f"ci=({last['ci_lo']:+.4f},{last['ci_hi']:+.4f})"
                  if last["ci_lo"] is not None else "ci=n/a")
            print(f"  {tag:24s} [{model}] n={c[model]['n_events']:3d} "
                  f"CAR[tau={last['tau']}]={last['mean_car']:+.4f} {ci} n@end={last['n']}")

    for et, c in es["by_type"].items():
        show(et, c)
    for key in ("pooled_directional", "pooled_directional_live", "pooled_directional_backfill"):
        show(key, es[key])
