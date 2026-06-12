"""YUCLAW C6 Evidence-Component Deep Dive — read-only research analysis.

Why is C6 (event_impact) NEGATIVELY correlated with next-period return? Five
views, run against signal_snapshots + events + price_history (READ ONLY):

  1. sign/aggregation audit  — trace C6 end-to-end for 5 names (incl. AMD), and
     independently recompute the stored c6 from its linked events to rule out a
     sign/aggregation bug.
  2. horizon sweep           — C6 IC vs forward return at 1w/2w/4w/8w/13w.
  3. event-type breakdown    — C6 IC / forward return by event composition
     (insider-sell-dominated vs has-material-non-insider).
  4. risk view               — C6 vs subsequent realized volatility + max drawdown.
  5. conditional view        — double-sort: within C1 (momentum) quintiles, does
     C6 separate forward returns?

Descriptive statistics only; no raw prices printed (derived returns/correlations).

Run:  python3 -m v3.lab.c6_investigation
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from v3.lab.cohort_engine import _connect, _entry_date, _period_return, load_prices
from v3.lab.analytics import spearman, _stdev
from v3.lab.granularity_investigation import kendall_tau_b

HORIZONS = [("1w", 5), ("2w", 10), ("4w", 20), ("8w", 40), ("13w", 65)]
HALF_LIFE_DAYS = 7.0
LN2 = math.log(2.0)
INSIDER_CAP = 0.5
INSIDER_TYPES = frozenset(("INSIDER_BUY", "INSIDER_SELL"))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ---- loaders ---------------------------------------------------------------
def load_events_index() -> dict:
    q = ("SELECT event_id, ticker, event_type, direction, magnitude, "
         "llm_confidence, available_as_of FROM events")
    out = {}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(q)
        for eid, tk, et, d, mag, conf, avail in cur.fetchall():
            out[eid] = {"ticker": tk, "type": et, "direction": int(d or 0),
                        "magnitude": float(mag or 0.0), "conf": float(conf or 0.0),
                        "avail": avail}
    return out


def load_snaps(panel: str) -> dict:
    """{date: {ticker: {c6, c1, score, eids:[...], time}}}."""
    is_backfill = (panel == "in_sample")
    q = ("SELECT signal_time, signal_time::date AS d, ticker, c6_event_impact, "
         "c1_price_momentum, total_score, evidence_event_ids "
         "FROM signal_snapshots WHERE is_backfill=%s")
    out: dict = {}
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(q, (is_backfill,))
        for st, d, tk, c6, c1, score, eids in cur.fetchall():
            out.setdefault(d, {})[tk] = {
                "c6": None if c6 is None else float(c6),
                "c1": None if c1 is None else float(c1),
                "score": float(score), "eids": list(eids or []), "time": st}
    return out


# ---- price-path helpers ----------------------------------------------------
def horizon_return(px: dict, tds: list, d0, h: int):
    if d0 not in set(tds):
        d0 = _entry_date(tds, d0)
    if d0 is None:
        return None
    i = tds.index(d0)
    if i + h >= len(tds):
        return None
    return _period_return(px, d0, tds[i + h])


def path_risk(px: dict, tds: list, d0, h: int):
    """(realized vol of daily returns, max drawdown) over next h trading days."""
    if d0 not in set(tds):
        d0 = _entry_date(tds, d0)
    if d0 is None:
        return None, None
    i = tds.index(d0)
    window = tds[i:i + h + 1]
    closes = [px[d] for d in window if d in px]
    if len(closes) < 3:
        return None, None
    rets = [closes[k] / closes[k - 1] - 1 for k in range(1, len(closes))]
    vol = _stdev(rets)
    peak, mdd, cum = closes[0], 0.0, closes[0]
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    return vol, mdd


# ---- 1. SIGN / AGGREGATION AUDIT -------------------------------------------
def sign_audit(snaps: dict, eidx: dict, names: list[str]) -> list[dict]:
    """For a chosen rebalance per name, recompute c6 from linked events and
    compare to the stored value. Confirms the direction convention + no bug."""
    rows = []
    for tk in names:
        # first in-sample date where this name has linked events
        chosen = None
        for d in sorted(snaps):
            rec = snaps[d].get(tk)
            if rec and rec["eids"]:
                chosen = (d, rec)
                break
        if not chosen:
            # fall back to first date present (c6 should be ~0, no events)
            for d in sorted(snaps):
                if tk in snaps[d]:
                    chosen = (d, snaps[d][tk]); break
        if not chosen:
            continue
        d, rec = chosen
        as_of = rec["time"]
        as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        ins_sum = oth_sum = 0.0
        by_type = defaultdict(int)
        for eid in rec["eids"]:
            ev = eidx.get(eid)
            if not ev:
                continue
            by_type[ev["type"]] += 1
            avail = ev["avail"] if ev["avail"].tzinfo else ev["avail"].replace(tzinfo=timezone.utc)
            age = max(0.0, (as_of - avail).total_seconds() / 86400.0)
            rw = math.exp(-LN2 * age / HALF_LIFE_DAYS)
            impact = ev["direction"] * ev["magnitude"] * ev["conf"] * rw
            if ev["type"] in INSIDER_TYPES:
                ins_sum += impact
            else:
                oth_sum += impact
        capped = max(-INSIDER_CAP, min(INSIDER_CAP, ins_sum))
        recomputed = math.tanh(capped + oth_sum)
        rows.append({
            "ticker": tk, "date": d.isoformat(), "n_events": len(rec["eids"]),
            "types": dict(by_type), "insider_sum": ins_sum, "capped": capped,
            "other_sum": oth_sum, "recomputed_c6": recomputed,
            "stored_c6": rec["c6"],
            "match": (rec["c6"] is not None and abs(recomputed - rec["c6"]) < 1e-3),
            "score": rec["score"]})
    return rows


# ---- 2. HORIZON SWEEP ------------------------------------------------------
def horizon_sweep(snaps: dict, px_all, tds) -> dict:
    rdates = sorted(snaps)
    out = {}
    for lab, h in HORIZONS:
        ics, taus, ns = [], [], []
        for rd in rdates:
            d0 = _entry_date(tds, rd)
            if d0 is None:
                continue
            c6s, rets = [], []
            for tk, rec in snaps[rd].items():
                if rec["c6"] is None:
                    continue
                r = horizon_return(px_all.get(tk, {}), tds, d0, h)
                if r is not None:
                    c6s.append(rec["c6"]); rets.append(r)
            if len(c6s) >= 10:
                s = spearman(c6s, rets)
                t = kendall_tau_b(c6s, rets)
                if s is not None:
                    ics.append(s); ns.append(len(c6s))
                if t is not None:
                    taus.append(t)
        out[lab] = {"h": h, "mean_ic": _mean(ics), "mean_tau": _mean(taus),
                    "hit": _mean([1 if i > 0 else 0 for i in ics]),
                    "n_rebalances": len(ics), "mean_names": _mean(ns)}
    return out


# ---- 3. EVENT-TYPE BREAKDOWN -----------------------------------------------
def event_type_breakdown(snaps: dict, eidx: dict, px_all, tds, h=20) -> dict:
    """Classify each c6!=0 name-rebalance by event composition, then compare
    forward return and within-class C6 IC."""
    classes = defaultdict(lambda: {"c6": [], "ret": []})
    for rd in sorted(snaps):
        d0 = _entry_date(tds, rd)
        if d0 is None:
            continue
        for tk, rec in snaps[rd].items():
            if not rec["eids"] or rec["c6"] is None or rec["c6"] == 0:
                continue
            types = [eidx[e]["type"] for e in rec["eids"] if e in eidx]
            dirs = [eidx[e]["direction"] for e in rec["eids"] if e in eidx]
            if not types:
                continue
            has_material = any(t not in INSIDER_TYPES for t in types)
            insider_sell = any(eidx[e]["type"] == "INSIDER_SELL" for e in rec["eids"] if e in eidx)
            if has_material:
                cls = "has_material_noninsider"
            elif insider_sell:
                cls = "insider_sell_only"
            else:
                cls = "insider_buy_only"
            r = horizon_return(px_all.get(tk, {}), tds, d0, h)
            if r is not None:
                classes[cls]["c6"].append(rec["c6"])
                classes[cls]["ret"].append(r)
    out = {}
    for cls, d in classes.items():
        out[cls] = {"n": len(d["ret"]), "mean_c6": _mean(d["c6"]),
                    "mean_ret": _mean(d["ret"]),
                    "ic": spearman(d["c6"], d["ret"]) if len(d["c6"]) >= 5 else None}
    return out


# ---- 4. RISK VIEW ----------------------------------------------------------
def risk_view(snaps: dict, px_all, tds, h=20) -> dict:
    vol_ic, mdd_ic, ret_ic = [], [], []
    for rd in sorted(snaps):
        d0 = _entry_date(tds, rd)
        if d0 is None:
            continue
        c6s, vols, mdds, rets = [], [], [], []
        for tk, rec in snaps[rd].items():
            if rec["c6"] is None:
                continue
            vol, mdd = path_risk(px_all.get(tk, {}), tds, d0, h)
            r = horizon_return(px_all.get(tk, {}), tds, d0, h)
            if vol is not None and r is not None:
                c6s.append(rec["c6"]); vols.append(vol); mdds.append(mdd); rets.append(r)
        if len(c6s) >= 10:
            for acc, series in ((vol_ic, vols), (mdd_ic, mdds), (ret_ic, rets)):
                s = spearman(c6s, series)
                if s is not None:
                    acc.append(s)
    return {"h": h,
            "ic_c6_vol": _mean(vol_ic), "ic_c6_maxdd": _mean(mdd_ic),
            "ic_c6_ret": _mean(ret_ic), "n_rebalances": len(vol_ic)}


# ---- 5. CONDITIONAL VIEW (double-sort C6 within C1 quintiles) --------------
def conditional_view(snaps: dict, px_all, tds, h=20, qn=5) -> dict:
    within_spreads = []   # per (rebalance,quintile): hiC6 ret - loC6 ret
    per_q = defaultdict(list)
    for rd in sorted(snaps):
        d0 = _entry_date(tds, rd)
        if d0 is None:
            continue
        rows = []
        for tk, rec in snaps[rd].items():
            if rec["c1"] is None or rec["c6"] is None:
                continue
            r = horizon_return(px_all.get(tk, {}), tds, d0, h)
            if r is not None:
                rows.append((rec["c1"], rec["c6"], r))
        if len(rows) < qn * 4:
            continue
        rows.sort(key=lambda x: x[0])  # by C1 ascending
        n = len(rows)
        for q in range(qn):
            seg = rows[(q * n) // qn:((q + 1) * n) // qn]
            if len(seg) < 4:
                continue
            seg_sorted = sorted(seg, key=lambda x: x[1])  # by C6
            half = len(seg_sorted) // 2
            lo = _mean([x[2] for x in seg_sorted[:half]])
            hi = _mean([x[2] for x in seg_sorted[-half:]])
            if lo is not None and hi is not None:
                within_spreads.append(hi - lo)
                per_q[q].append(hi - lo)
    return {"h": h, "qn": qn, "mean_within_c6_spread": _mean(within_spreads),
            "n_obs": len(within_spreads),
            "per_quintile": {f"C1_q{q+1}": _mean(v) for q, v in sorted(per_q.items())}}


def run(panel="in_sample") -> dict:
    eidx = load_events_index()
    snaps = load_snaps(panel)
    px_all, tds = load_prices()
    audit_names = ["AMD", "AAPL", "NVDA", "INTC", "MSFT"]
    return {
        "panel": panel,
        "sign_audit": sign_audit(snaps, eidx, audit_names),
        "horizon": horizon_sweep(snaps, px_all, tds),
        "event_type": event_type_breakdown(snaps, eidx, px_all, tds),
        "risk": risk_view(snaps, px_all, tds),
        "conditional": conditional_view(snaps, px_all, tds),
    }


def _f(x, dp=4):
    return "   None" if x is None else f"{x:+.{dp}f}"


if __name__ == "__main__":
    for panel in ("in_sample", "forward"):
        r = run(panel)
        print(f"\n{'='*72}\n=== C6 DEEP DIVE — {panel} ===\n{'='*72}")
        print("\n[1] SIGN / AGGREGATION AUDIT (recomputed c6 vs stored):")
        for a in r["sign_audit"]:
            print(f"  {a['ticker']:<5} {a['date']}  events={a['n_events']:<3} {a['types']}")
            print(f"        insider_sum={_f(a['insider_sum'])} ->capped={_f(a['capped'])} "
                  f"other={_f(a['other_sum'])} | recomputed={_f(a['recomputed_c6'])} "
                  f"stored={_f(a['stored_c6'])} MATCH={a['match']}")
        print("\n[2] HORIZON SWEEP (C6 IC vs forward return):")
        for lab, h in HORIZONS:
            d = r["horizon"][lab]
            print(f"  {lab:>4} ({h:>2}td)  meanIC={_f(d['mean_ic'])} tau={_f(d['mean_tau'])} "
                  f"hit={d['hit']} nReb={d['n_rebalances']} meanNames={d['mean_names'] and round(d['mean_names'],0)}")
        print("\n[3] EVENT-TYPE BREAKDOWN (h=20td):")
        for cls, d in r["event_type"].items():
            print(f"  {cls:<26} n={d['n']:<4} meanC6={_f(d['mean_c6'])} "
                  f"meanRet={_f(d['mean_ret'])} withinIC={_f(d['ic'])}")
        rv = r["risk"]
        print(f"\n[4] RISK VIEW (h={rv['h']}td, nReb={rv['n_rebalances']}):")
        print(f"  IC(C6, realized_vol)={_f(rv['ic_c6_vol'])}  IC(C6, max_drawdown)={_f(rv['ic_c6_maxdd'])}  "
              f"IC(C6, return)={_f(rv['ic_c6_ret'])}")
        print("  (maxdd is <=0: positive IC => higher C6 -> shallower drawdown)")
        cv = r["conditional"]
        print(f"\n[5] CONDITIONAL (double-sort, C6 within C1 quintiles, h={cv['h']}td, n={cv['n_obs']}):")
        print(f"  mean within-quintile hiC6-loC6 forward-return spread = {_f(cv['mean_within_c6_spread'])}")
        for q, v in cv["per_quintile"].items():
            print(f"    {q}: {_f(v)}")
