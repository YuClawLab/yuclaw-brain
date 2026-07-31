#!/usr/bin/env python3
"""
Cross-lens reversal coherence v1 — REGISTERED TODAY, COMPUTED NO EARLIER THAN
2026-09-01. This module deliberately contains NO analysis code; the guard in
run() is the only executable behavior until the compute date. The registry's
second deliberately-waiting protocol (pattern: C6 Risk Gate, 0df6fc002d79).

WHY THIS EXISTS. The 2026-07-27 momentum-conditioning run (protocol
dfee13621c33) found, in EXPLORATORY secondary cells, that the W=60
winners-minus-losers aligned-CAR difference was negative in all five targets
(SMH-E4, XEG, ZEO, GDX, URNM), with conservative envelopes excluding zero in
three. Re-testing that pattern on the same data would be confirmation
laundering. Hypothesis from exploration; confirmation only on data that does
not exist yet.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

METHOD_SPEC = """
CROSS-LENS REVERSAL COHERENCE — pre-committed specification (v1)
Hypothesis (from exploration, dfee13621c33 secondary cells, 2026-07-27):
prior-60-trading-day issuer-vs-peer winners deliver LOWER direction-aligned
peer-model CAR at tau=+20 than prior losers, coherently across unrelated
lenses.
Data: ONLY events whose day0 falls on/after 2026-07-27 (forward accrual;
none of it exists at registration). Targets: SMH-E4 (capped-ETF weights,
covered sleeve), XEG, ZEO, GDX, URNM (pooled event-weighted). Estimand and
momentum machinery identical to protocols 15052741ba2a / dfee13621c33:
direction-aligned peer-model CAR at +20; relative momentum = compounded
issuer minus EW-peer return over [day0-60, day0-1], >=40 usable paired days;
median split within each target's accrued set.
MINIMUM WINDOW (pre-specified): compute no earlier than 2026-09-01, AND a
target qualifies only with >=15 events that have complete +20 windows and
momentum data. If fewer than 3 targets qualify: verdict INSUFFICIENT —
report accrual counts, no coherence claim, wait.
PRIMARY (single): sign-coherence = number of qualifying targets with a
NEGATIVE winners-minus-losers difference. Verdict labels (locked):
  COHERENT      — all qualifying targets negative AND >=4 qualify
  LEANING       — >=75% of qualifying targets negative (>=3 qualify)
  NOT_COHERENT  — otherwise
  INSUFFICIENT  — <3 qualifying targets
One-sided sign-test p (H0: P(negative)=0.5, independence across targets
stated as an approximation) reported beside the verdict, never replacing it.
SECONDARY (ledger-counted): per-target differences with issuer+date cluster
envelopes (machinery of dfee13621c33); per-target ns; W=20 variant
(disclosed, no verdict weight). B=4000, seed 20260901. No interim peeks:
the first computation IS the verdict computation.
Edits to this spec => supersession, never amendment.
"""
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
COMPUTE_NOT_BEFORE = date(2026, 9, 1)
ACCRUAL_START = date(2026, 7, 27)

PROTOCOL_NAME = "Cross-lens reversal coherence v1"
PROTOCOL_PARAMS = {
    "targets": ["SMH-E4", "XEG", "ZEO", "GDX", "URNM"],
    "accrual_start": "2026-07-27", "compute_not_before": "2026-09-01",
    "momentum_window": 60, "min_events_per_target": 15,
    "min_qualifying_targets": 3, "horizon_tau": 20,
    "B": 4000, "seed": 20260901,
}


def register() -> str:
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if reg.get_protocol(pid):
        print(f"[registry] protocol {pid} already LOCKED")
        return pid
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=("Forward-accrual confirmation of the exploratory W=60 "
                      "cross-lens reversal pattern: sign-coherence of "
                      "winners-minus-losers aligned-CAR differences across "
                      "five targets, events from 2026-07-27 only, computed "
                      "no earlier than 2026-09-01, >=15 events/target, "
                      "verdict labels locked."),
        primary_endpoint=("sign-coherence count of negative W=60 "
                          "winners-minus-losers differences across "
                          "qualifying targets (verdict per locked labels)"),
        secondary_endpoints=[
            "per-target differences with issuer+date cluster envelopes",
            "per-target accrual counts",
            "W=20 variant (disclosed, no verdict weight)",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — ZERO runs until >= {COMPUTE_NOT_BEFORE}")
    return pid


MIN_EVENTS_PER_TARGET = 15
MIN_QUALIFYING_TARGETS = 3


def coherence_verdict(diffs_by_target: dict) -> dict:
    """Pure spec-conformant verdict computation. diffs_by_target:
    {target: {"n": int, "diff": float|None}} where diff is the W=60
    winners-minus-losers difference and n the events with complete +20
    windows AND momentum data. Floors and verdict labels exactly per the
    locked METHOD_SPEC; no other labels exist."""
    qualifying = {t: v for t, v in diffs_by_target.items()
                  if v["n"] >= MIN_EVENTS_PER_TARGET and v["diff"] is not None}
    if len(qualifying) < MIN_QUALIFYING_TARGETS:
        return {"verdict": "INSUFFICIENT",
                "qualifying": sorted(qualifying),
                "accrual": {t: v["n"] for t, v in diffs_by_target.items()},
                "note": "fewer than 3 qualifying targets — report accrual, "
                        "no coherence claim, wait"}
    neg = [t for t, v in qualifying.items() if v["diff"] < 0]
    frac = len(neg) / len(qualifying)
    if len(neg) == len(qualifying) and len(qualifying) >= 4:
        verdict = "COHERENT"
    elif frac >= 0.75 and len(qualifying) >= 3:
        verdict = "LEANING"
    else:
        verdict = "NOT_COHERENT"
    # one-sided sign test at p=0.5, independence across targets (stated
    # approximation in the spec)
    import math
    n, k = len(qualifying), len(neg)
    p = sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n
    return {"verdict": verdict, "n_qualifying": n, "n_negative": k,
            "negative_targets": sorted(neg),
            "coherence_fraction": round(frac, 3),
            "sign_test_p_one_sided": round(p, 4),
            "accrual": {t: v["n"] for t, v in diffs_by_target.items()}}


def _selftest():
    # coherent-by-construction: 5 qualifying, all negative
    r1 = coherence_verdict({t: {"n": 20, "diff": -2.0}
                            for t in ("A", "B", "C", "D", "E")})
    assert r1["verdict"] == "COHERENT", r1
    # mixed: 5 qualifying, 2 negative
    r2 = coherence_verdict({"A": {"n": 20, "diff": -2.0},
                            "B": {"n": 20, "diff": 1.0},
                            "C": {"n": 20, "diff": 0.5},
                            "D": {"n": 20, "diff": -1.0},
                            "E": {"n": 20, "diff": 2.0}})
    assert r2["verdict"] == "NOT_COHERENT", r2
    # leaning: 4 qualifying, 3 negative (75%)
    r3 = coherence_verdict({"A": {"n": 20, "diff": -2.0},
                            "B": {"n": 20, "diff": -1.0},
                            "C": {"n": 20, "diff": -0.5},
                            "D": {"n": 20, "diff": 1.0},
                            "E": {"n": 5, "diff": -9.0}})   # E below floor
    assert r3["verdict"] == "LEANING", r3
    # thin: only 2 targets qualify
    r4 = coherence_verdict({"A": {"n": 20, "diff": -2.0},
                            "B": {"n": 20, "diff": -1.0},
                            "C": {"n": 8, "diff": -3.0},
                            "D": {"n": 2, "diff": 1.0},
                            "E": {"n": 0, "diff": None}})
    assert r4["verdict"] == "INSUFFICIENT", r4
    # determinism
    assert coherence_verdict({t: {"n": 20, "diff": -2.0}
                              for t in ("A", "B", "C", "D", "E")}) == r1
    print("[OK] coherent · mixed->NOT_COHERENT · leaning · thin->INSUFFICIENT "
          "· determinism")


def _real_diffs():
    """Forward-accrual W=60 winners-minus-losers differences per target,
    events with day0 >= 2026-07-27 ONLY — machinery identical to
    dfee13621c33 (momentum conditioning). Reached ONLY through run()'s
    guard; never callable on real data before the compute date."""
    from datetime import date as _date
    import psycopg2
    from yuclaw_falsification import TargetGrid
    from yuclaw_momentum_conditioning import rel_momentum
    from yuclaw_etf_lens import WeightedClusteredCAR
    from v3.lab.cohort_engine import DSN, load_prices
    from v3.lab.etf_evidence import canada_lens_holdings, overlap_summary

    prices, td = load_prices()
    idx = {d: i for i, d in enumerate(td)}
    targets = {"SMH-E4": ("capped", overlap_summary()["covered"],
                          overlap_summary()["weights_covered"])}
    for lens, hold in canada_lens_holdings().items():
        targets[lens] = ("event", sorted(hold), {})
    out = {}
    for name, (kind, covered, fund_w) in targets.items():
        grid = TargetGrid(covered, prices, td)
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ticker, direction, event_time::date
                       FROM events WHERE event_status='accepted'
                         AND ticker = ANY(%s) AND direction <> 0
                         AND event_time::date >= %s""",
                    (covered, ACCRUAL_START))
                evs = cur.fetchall()
        rows = []
        for tk, dirn, ev_date in evs:
            day0 = next((d for d in td if d >= ev_date), None)
            if day0 is None:
                continue
            v = grid.car20(tk, idx[day0])
            m = rel_momentum(grid, tk, idx[day0], 60, 40)
            if v is not None and m is not None:
                rows.append((tk, v * int(dirn), m))
        if len(rows) < 4:
            out[name] = {"n": len(rows), "diff": None}
            continue
        moms = sorted(m for *_x, m in rows)
        med = moms[len(moms) // 2]
        hi = [(t, c) for t, c, m in rows if m > med]
        lo = [(t, c) for t, c, m in rows if m <= med]

        def stat(obs):
            if not obs:
                return None
            if kind == "capped":
                ev = [(t, str(i), c) for i, (t, c) in enumerate(obs)]
                wc = WeightedClusteredCAR(ev, fund_w, B=1, seed=20260901)
                w = wc._weights(ev, "capped")
                sw = sum(w)
                return (sum(wi * c for wi, (_t, _x, c) in zip(w, ev)) / sw
                        if sw else None)
            return sum(c for _t, c in obs) / len(obs)
        a, b = stat(hi), stat(lo)
        out[name] = {"n": len(rows),
                     "diff": (a - b) if None not in (a, b) else None}
    return out


def run():
    """The 2026-09-01+ computation enters HERE and nowhere else. The
    verdict machinery above is synthetic-tested; real data flows only
    through this guard."""
    today = datetime.now(timezone.utc).date()
    if today < COMPUTE_NOT_BEFORE:
        raise RuntimeError(
            f"Cross-lens reversal coherence is guarded: computation is "
            f"scheduled no earlier than {COMPUTE_NOT_BEFORE} on forward "
            f"accrual from {ACCRUAL_START}. Today is {today}. No interim "
            f"peeks — the first computation is the verdict computation.")
    from yuclaw_protocol_registry import Registry
    Registry(str(_REPO / "registry" / "protocols.jsonl")).assert_registered(
        "ea120b0a6b52")
    return coherence_verdict(_real_diffs())


if __name__ == "__main__":
    register()
    try:
        run()
    except RuntimeError as e:
        print(f"[guard] {e}")
