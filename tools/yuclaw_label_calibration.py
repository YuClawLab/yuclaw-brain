#!/usr/bin/env python3
"""
Label calibration v1 (credibility battery Part C) — REGISTRY-FIRST.
Do the locked public labels mean anything, measured on the forward ledger?

METHOD_SPEC (locked):
  Window: forward-OOS ledger rows (track_record.is_backfill = false).
  Per locked label: n snapshot-outcomes, mean forward BENCHMARK-RELATIVE
  return (excess_return_kd columns, k in {1, 5, 20} — the ledger's recorded horizons), and — for
  DIRECTIONAL labels only — the direction-consistency rate: share of
  outcomes where sign(excess_return_kd) matches the label's direction.
  DIRECTION MAPPING (locked, from the public vocabulary's construction):
    positive: STRONG_BULLISH, BULLISH
    negative: WEAKENING, NEGATIVE_EVENT, BEARISH_WATCH
    non-directional (no consistency claim, outcomes still shown):
    NEUTRAL, WATCH, RISK_ALERT (risk-state, not direction — per the C6
    doctrine).
  Inference: ticker-clustered bootstrap CIs (B=2000, seed 20260801,
  percentile 2.5/97.5) on each mean and each consistency rate. Badges
  (locked): UNDERPOWERED if a label has < 30 outcomes or < 8 clustered
  tickers (most labels will be — that prints); DESCRIPTIVE if the CI
  includes the null (0 for means, 0.5 for consistency); else PRELIMINARY.
  PRIMARY (single): pooled direction-consistency of the full directional
  label set at k=20, ticker-clustered CI. (v1.1 supersession note: v1
  named k=10, a horizon the forward ledger does not record — corrected
  BEFORE any computation was recorded under v1.) Everything else secondary,
  ledger-counted. Edits => supersession.
"""
from __future__ import annotations

import hashlib
import json
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
from v3.lab.cohort_engine import DSN

SEED = 20260801
B = 2000
KS = (1, 5, 20)
POS = {"STRONG_BULLISH", "BULLISH"}
NEG = {"WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH"}
NONDIR = {"NEUTRAL", "WATCH", "RISK_ALERT"}
METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Label calibration v1.1"
PROTOCOL_PARAMS = {"ks": list(KS), "k_primary": 20, "B": B, "seed": SEED,
                   "positive": sorted(POS), "negative": sorted(NEG),
                   "non_directional": sorted(NONDIR)}
OUT_JSON = _REPO / "output" / "oie" / "label_calibration.json"


def boot_ci(obs, stat_fn, tag):
    """obs: [(ticker, value)]; percentile CI via ticker-cluster bootstrap."""
    by: dict = {}
    for tk, v in obs:
        by.setdefault(tk, []).append(v)
    keys = sorted(by)
    rng = random.Random(f"{SEED}:{tag}")
    reps = []
    for _ in range(B):
        s = []
        for _ in keys:
            s += by[keys[rng.randrange(len(keys))]]
        v = stat_fn(s)
        if v is not None:
            reps.append(v)
    reps.sort()
    return (round(reps[int(0.025 * len(reps))], 4),
            round(reps[int(0.975 * len(reps)) - 1], 4))


def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Per-label forward outcomes on the ledger: n, mean "
                          "excess return k in {5,10,20}, direction-"
                          "consistency for directional labels; ticker-"
                          "clustered CIs; thin labels print UNDERPOWERED."),
            primary_endpoint=("pooled direction-consistency of the "
                              "directional label set at k=20, "
                              "ticker-clustered CI"),
            secondary_endpoints=["per-label mean excess cells (labels x 3 ks)",
                                 "per-label consistency cells",
                                 "non-directional label outcome cells"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) "
              f"method={METHOD_HASH} — registered BEFORE computation")
    reg.assert_registered(pid)

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT signal_label, ticker,
                          excess_return_1d, excess_return_5d,
                          excess_return_20d
                   FROM track_record WHERE is_backfill = false""")
            rows = cur.fetchall()

    by_label: dict = {}
    for lbl, tk, e1, e5, e20 in rows:
        by_label.setdefault(lbl, []).append(
            (tk, {1: e1, 5: e5, 20: e20}))

    mean = lambda xs: sum(xs) / len(xs) if xs else None
    table = {}
    for lbl, obs in sorted(by_label.items(), key=lambda kv: -len(kv[1])):
        row = {"n": len(obs),
               "directional": ("positive" if lbl in POS else
                               "negative" if lbl in NEG else "none")}
        tickers = {tk for tk, _ in obs}
        for k in KS:
            vals = [(tk, float(r[k])) for tk, r in obs if r[k] is not None]
            if not vals:
                row[f"k{k}"] = None
                continue
            m = mean([v for _t, v in vals])
            ci = boot_ci(vals, mean, f"{lbl}:m:{k}")
            cell = {"mean_excess": round(m, 4), "ci": ci, "n": len(vals)}
            if lbl in POS or lbl in NEG:
                want = 1 if lbl in POS else -1
                cons = [(tk, 1.0 if (v > 0) == (want > 0) else 0.0)
                        for tk, v in vals if v != 0]
                if cons:
                    cr = mean([c for _t, c in cons])
                    cci = boot_ci(cons, mean, f"{lbl}:c:{k}")
                    cell["consistency"] = round(cr, 4)
                    cell["consistency_ci"] = cci
            badge = ("UNDERPOWERED" if len(vals) < 30 or len(tickers) < 8 else
                     "DESCRIPTIVE" if ci[0] <= 0 <= ci[1] else "PRELIMINARY")
            cell["badge"] = badge
            row[f"k{k}"] = cell
        table[lbl] = row

    # primary: pooled directional consistency at k=10
    pooled = []
    for lbl, obs in by_label.items():
        if lbl not in POS and lbl not in NEG:
            continue
        want = 1 if lbl in POS else -1
        for tk, r in obs:
            v = r[20]
            if v is not None and float(v) != 0:
                pooled.append((tk, 1.0 if (float(v) > 0) == (want > 0) else 0.0))
    pr = mean([c for _t, c in pooled])
    pci = boot_ci(pooled, mean, "primary")
    n_tk = len({t for t, _ in pooled})
    pbadge = ("UNDERPOWERED" if len(pooled) < 30 or n_tk < 8 else
              "DESCRIPTIVE" if pci[0] <= 0.5 <= pci[1] else "PRELIMINARY")

    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "primary": {"consistency_k20": round(pr, 4), "ci": pci,
                           "n": len(pooled), "n_tickers": n_tk,
                           "badge": pbadge},
               "table": table}
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                   default=str).encode()).hexdigest()[:16]
    n_sec = sum(1 for lbl in table for k in KS if table[lbl].get(f"k{k}"))
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"forward ledger, {len(rows)} outcomes",
        n_primary_cells=1, n_secondary_cells=n_sec, result_hash=rh,
        note=(f"Calibration activation: pooled directional consistency@k20 "
              f"= {pr:.4f} CI {pci} [{pbadge}] over n={len(pooled)}.")))
    reg.verify_chain()
    print(f"[primary] directional consistency @k20 = {pr:.4f} CI{pci} "
          f"[{pbadge}] n={len(pooled)}/{n_tk} tickers")
    for lbl, row in table.items():
        c20 = row.get("k20") or {}
        print(f"  {lbl:>15} ({row['directional'][:3]}): n={row['n']} "
              f"k20 excess={c20.get('mean_excess')} "
              f"cons={c20.get('consistency')} [{c20.get('badge')}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
