#!/usr/bin/env python3
"""
Evidence Lifecycle v1 (Fields-review build Part 4) — REGISTRY-FIRST.
Question: how does evidence impact emerge, peak, and fade?

STANDING RULE RESTATED: C6 and C8 inputs are untouched — the diffusion
section is a DISPLAY-ONLY read of already-persisted cascade rows; nothing
here writes to the database or feeds any scoring path.

METHOD_SPEC (locked):
  Populations: the five lens covered sets (SMH, XEG, ZEO, GDX, URNM),
  deduped accepted events, BACKFILL ERA (event date 2026-02-18..2026-05-15),
  peer-model abnormal returns per the standing estimation rules.
  (a) IMPACT PATH per event type: path(tau) = mean over events of the
      ABSOLUTE cumulative abnormal return from day 0 through tau,
      tau = 0..20 (accumulation starts at day 0; the pre-event days are not
      part of the lifecycle read). Types qualify at n >= 15 within a
      population for panel display and n >= 15 pooled across populations
      for the primary; thinner types are LISTED with their n and marked
      UNDERPOWERED — never plotted as if powered.
  (b) TIME-TO-PEAK = argmax over tau of path(tau); HALF-LIFE = first tau
      after the peak where path(tau) <= half the peak value; reported as
      "not reached within window" when no such tau exists by tau=20.
  (c) DIFFUSION (display-only): per SOURCE event type, the count of
      depth-1 cascade descendants (events.cascade_depth = 1 joined on
      parent_event_id) and the median lag in calendar days between parent
      and child event times.
  (d) STALENESS: per lens, ages (days) of each covered member's latest
      accepted event: median age, share <= 7 days, share > 30 days.
Primary endpoint: median time-to-peak across qualifying event types,
pooled backfill era (types with pooled n >= 15). Everything else secondary,
ledger-counted. Edits => supersession.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

SEED = 20260730
N_FLOOR = 15
BACKFILL_LO, BACKFILL_HI = date(2026, 2, 18), date(2026, 5, 15)

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Evidence Lifecycle v1"
PROTOCOL_PARAMS = {"n_floor": N_FLOOR, "tau_range": [0, 20],
                   "era": "backfill", "seed": SEED,
                   "populations": ["SMH", "XEG", "ZEO", "GDX", "URNM"]}
OUT_JSON = _REPO / "output" / "oie" / "evidence_lifecycle.json"


# ------------------------------------------------------------ core
def type_path(cum_paths):
    """cum_paths: list of per-event lists [cum at tau 0..20] (None where the
    path did not print). Returns {path, peak_tau, peak_value, half_life}."""
    T = 21
    path = []
    for tau in range(T):
        vals = [abs(p[tau]) for p in cum_paths if p[tau] is not None]
        path.append(round(sum(vals) / len(vals), 4) if vals else None)
    usable = [(t, v) for t, v in enumerate(path) if v is not None]
    if not usable:
        return None
    peak_tau, peak_val = max(usable, key=lambda tv: tv[1])
    half = None
    for t, v in usable:
        if t > peak_tau and v <= peak_val / 2:
            half = t
            break
    return {"path": path, "peak_tau": peak_tau,
            "peak_value_pct": round(peak_val, 3),
            "half_life_tau": half,
            "half_life": (str(half) if half is not None
                          else "not reached within window")}


# ------------------------------------------------------------ self-tests
def _selftest():
    # T1 front-loaded: jump at tau=1, decays fast -> early peak, short HL
    front = [[0, 5.0, 4.0, 2.4, 1.8, 1.2] + [1.0] * 15 for _ in range(20)]
    r1 = type_path(front)
    assert r1["peak_tau"] <= 2, r1
    assert r1["half_life_tau"] is not None and r1["half_life_tau"] <= 4, r1
    # T2 slow build: linear ramp -> peak at 20, half-life not reached
    slow = [[t * 0.3 for t in range(21)] for _ in range(20)]
    r2 = type_path(slow)
    assert r2["peak_tau"] == 20 and r2["half_life_tau"] is None, r2
    # T3 n-floor enforcement is a caller rule — verify the qualifying filter
    counts = {"A": 20, "B": 7}
    qual = [t for t, n in counts.items() if n >= N_FLOOR]
    assert qual == ["A"]
    # T4 determinism
    assert type_path(front) == r1 and type_path(slow) == r2
    print("[OK] T1 front-loaded recovered · T2 slow-build recovered · "
          "T3 n-floor · T4 determinism")


# ------------------------------------------------------------ real data
def event_paths():
    """(population, type) -> list of per-event cum paths (tau 0..20),
    backfill era. Accumulation starts at day 0 per the locked spec."""
    import psycopg2
    from yuclaw_falsification import TargetGrid
    from v3.lab.cohort_engine import DSN, load_prices
    from v3.lab.etf_evidence import (CAR_POST, EST_GAP, EST_MIN, EST_WIN,
                                     canada_lens_holdings, overlap_summary)
    from v3.lab.stats import ols

    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    pops = {"SMH": overlap_summary()["covered"],
            **{k: sorted(v) for k, v in canada_lens_holdings().items()}}
    out = {}
    for lens, covered in pops.items():
        grid = TargetGrid(covered, prices, td)
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ticker, event_type, direction,
                              event_time::date
                       FROM events WHERE event_status='accepted'
                         AND ticker = ANY(%s)
                         AND event_time::date BETWEEN %s AND %s""",
                    (covered, BACKFILL_LO, BACKFILL_HI))
                evs = cur.fetchall()
        for tk, et, _dirn, ev_date in evs:
            day0 = next((d for d in td if d >= ev_date), None)
            if day0 is None:
                continue
            i0 = idx[day0]
            est = td[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
            pairs = [(grid.ret[tk].get(d), grid.peer[tk].get(d)) for d in est]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if len(pairs) < EST_MIN:
                continue
            reg = ols([a for a, _ in pairs], [b for _, b in pairs])
            if reg is None:
                continue
            cum, row = 0.0, [None] * 21
            for tau in range(0, CAR_POST + 1):
                j = i0 + tau
                if j >= len(td):
                    break
                d = td[j]
                r, m = grid.ret[tk].get(d), grid.peer[tk].get(d)
                if r is None or m is None:
                    continue
                cum += r - (reg["alpha"] + reg["beta"] * m)
                row[tau] = cum * 100.0
            if row[20] is not None:
                out.setdefault((lens, et), []).append(row)
    return out


def diffusion():
    import psycopg2
    from v3.lab.cohort_engine import DSN
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT p.event_type,
                          count(*),
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY
                              EXTRACT(EPOCH FROM (c.event_time - p.event_time))
                              / 86400.0)
                   FROM events c JOIN events p ON c.parent_event_id = p.event_id
                   WHERE c.cascade_depth = 1
                   GROUP BY 1 ORDER BY 2 DESC""")
            return [{"source_type": t, "depth1_descendants": int(n),
                     "median_lag_days": round(float(lag), 1)}
                    for t, n, lag in cur.fetchall()]


def staleness():
    import psycopg2
    from v3.lab.cohort_engine import DSN
    from v3.lab.etf_evidence import canada_lens_holdings, overlap_summary
    pops = {"SMH": overlap_summary()["covered"],
            **{k: sorted(v) for k, v in canada_lens_holdings().items()}}
    today = datetime.now(timezone.utc).date()
    out = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            for lens, covered in pops.items():
                cur.execute(
                    """SELECT ticker, max(event_time)::date FROM events
                       WHERE event_status='accepted' AND ticker = ANY(%s)
                       GROUP BY 1""", (covered,))
                ages = sorted((today - d).days for _t, d in cur.fetchall())
                if not ages:
                    out[lens] = None
                    continue
                out[lens] = {
                    "n_members_with_events": len(ages),
                    "median_age_days": ages[len(ages) // 2],
                    "share_le_7d_pct": round(100 * sum(1 for a in ages if a <= 7) / len(ages), 1),
                    "share_gt_30d_pct": round(100 * sum(1 for a in ages if a > 30) / len(ages), 1),
                }
    return out


def main() -> int:
    _selftest()
    from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Per-type absolute-CAR impact paths day 0..20 "
                          "(backfill era, n>=15 floor), time-to-peak and "
                          "half-life, display-only depth-1 cascade diffusion "
                          "counts, per-lens evidence staleness."),
            primary_endpoint=("median time-to-peak across qualifying event "
                              "types, pooled backfill era (pooled n >= 15)"),
            secondary_endpoints=[
                "per-type peak/half-life cells (pooled + per population)",
                "diffusion depth-1 counts + median lags per source type",
                "staleness cells per lens (median age, <=7d, >30d)",
            ],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) method={METHOD_HASH} "
              "— registered BEFORE computation")
    reg.assert_registered(pid)

    paths = event_paths()
    # pooled across populations by type
    pooled = {}
    for (lens, et), rows in paths.items():
        pooled.setdefault(et, []).extend(rows)
    pooled_types, thin_types = {}, {}
    for et, rows in sorted(pooled.items(), key=lambda kv: -len(kv[1])):
        if len(rows) >= N_FLOOR:
            r = type_path(rows)
            r["n"] = len(rows)
            pooled_types[et] = r
        else:
            thin_types[et] = {"n": len(rows), "badge": "UNDERPOWERED"}
    peaks = sorted(v["peak_tau"] for v in pooled_types.values())
    median_ttp = peaks[len(peaks) // 2] if peaks else None

    per_pop = {}
    for (lens, et), rows in paths.items():
        if len(rows) >= N_FLOOR:
            r = type_path(rows)
            r["n"] = len(rows)
            per_pop.setdefault(lens, {})[et] = r
        else:
            per_pop.setdefault(lens, {})[et] = {"n": len(rows),
                                                "badge": "UNDERPOWERED"}

    diff = diffusion()
    stale = staleness()

    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "median_time_to_peak_pooled": median_ttp,
               "pooled_types": pooled_types, "thin_types": thin_types,
               "per_population": per_pop,
               "diffusion_depth1": diff, "staleness": stale}
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    n_sec = (len(pooled_types) * 2 + len(per_pop) + len(diff) + len(stale))
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"backfill era {BACKFILL_LO}..{BACKFILL_HI}, 5 populations",
        n_primary_cells=1, n_secondary_cells=n_sec, result_hash=rh,
        note=(f"Evidence Lifecycle activation: primary = pooled median "
              f"time-to-peak ({median_ttp}); secondary = per-type peak+HL "
              f"cells, per-population tables, diffusion, staleness.")))
    reg.verify_chain()
    print("[registry] run recorded, chain OK")

    print(f"[lifecycle] median time-to-peak (pooled, {len(pooled_types)} "
          f"qualifying types): {median_ttp} trading days")
    for et, r in pooled_types.items():
        print(f"  {et:>18}: n={r['n']} peak tau={r['peak_tau']} "
              f"({r['peak_value_pct']}%) half-life={r['half_life']}")
    for et, r in thin_types.items():
        print(f"  {et:>18}: n={r['n']} UNDERPOWERED (below n>=15 floor)")
    print(f"[diffusion] {diff}")
    print(f"[staleness] {json.dumps(stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
