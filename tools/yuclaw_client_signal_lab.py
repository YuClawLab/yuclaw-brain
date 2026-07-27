#!/usr/bin/env python3
"""
Client-signal validation suite (BYOS Part A) — bring a signal, receive an
honest answer about its validity.

Pipeline: validated client CSV (date,ticker,signal_value; see
yuclaw_client_intake) -> single-component Panel with forward
benchmark-relative returns from price_history -> the full DecompositionLab
suite runs on THE CLIENT'S signal:

  IC with moving-block bootstrap CIs (k=5 primary), quantile monotonicity,
  cohort churn, horizon decay (k=1/2/5/10/20), placebo falsification —
  the same registered machinery as the canonical Signal Decomposition Lab
  (method spec b3c57f89...), applied under a CLIENT-NAMESPACE protocol.

Point-in-time rule (pre-committed): a signal dated D enters at the close of
the first trading day STRICTLY AFTER D; the k-day forward return is
(P[t0+k]/P[t0] - 1) minus the same for SPY, in percent. No same-day entry —
conservative against intraday-availability assumptions.

Out-of-universe tickers (no usable price_history) are EXCLUDED and disclosed
with counts — no new data paths are invented for them.

Registry: client-namespace chain only (Registry(..., namespace='client'),
guarded in code). The canonical run_all() guard is deliberately not used —
this suite asserts registration against the CLIENT chain instead; the
canonical registry is never touched.

Library: run_suite(csv_path, out_dir) -> dict. CLI: prints the suite report.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_client_intake import IntakeError, validate
from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_signal_decomposition import DecompositionLab, Panel

from v3.lab.cohort_engine import load_prices

KS = (1, 2, 5, 10, 20)
K_PRIMARY = 5
SEED = 20260727
MIN_PRICE_ROWS = 60   # usable price history floor for coverage

CLIENT_SPEC = """CLIENT-SIGNAL decomposition v1 (user_defined=true,
non_canonical=true). Single-component DecompositionLab suite (IC + moving-
block bootstrap CIs, quantile monotonicity, churn, horizon decay, placebo)
on a user-supplied point-in-time signal; forward returns benchmark-relative
(SPY) from price_history; entry at the close of the first trading day
strictly after the signal date; k=5 IC is the single primary endpoint, all
other cells secondary/exploratory. Locked badges from the canonical Lab
spec. Client-namespace chain only; not part of the canonical public record."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_suite(csv_path: str | Path, out_dir: str | Path) -> dict:
    csv_path, out_dir = Path(csv_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, intake_report = validate(csv_path)          # raises IntakeError

    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}

    tickers = sorted({r["ticker"] for r in rows})
    covered = [t for t in tickers if len(prices.get(t, {})) >= MIN_PRICE_ROWS]
    excluded = sorted(set(tickers) - set(covered))
    excl_counts = {t: sum(1 for r in rows if r["ticker"] == t)
                   for t in excluded}

    # ---- client-namespace registry, registry-first -------------------------
    reg = Registry(str(out_dir / "registry_client.jsonl"), namespace="client")
    params = {"user_defined": True, "non_canonical": True,
              "csv_sha256": _sha(csv_path), "ks": list(KS),
              "k_primary": K_PRIMARY, "seed": SEED,
              "entry": "close of first trading day strictly after signal date"}
    pid = protocol_id(CLIENT_SPEC, params)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid,
            name="CLIENT-SIGNAL decomposition v1 [user_defined, non_canonical]",
            method_hash=hashlib.sha256(CLIENT_SPEC.encode()).hexdigest()[:16],
            spec_summary=CLIENT_SPEC.replace("\n", " "),
            primary_endpoint="client-signal IC at k=5 with moving-block bootstrap CI",
            secondary_endpoints=[
                "IC at k=1/2/10/20 (horizon decay)",
                "quantile monotonicity + top-minus-bottom spread",
                "cohort churn (rank autocorrelation)",
                "placebo falsification (within-date shuffle null)",
            ],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
    reg.verify_chain()
    reg.assert_registered(pid)   # registry-first, client chain

    # ---- Panel --------------------------------------------------------------
    dates = sorted({r["date"] for r in rows})
    sig = {(r["ticker"], r["date"]): r["signal_value"] for r in rows}

    def ret_k(tk, d, k):
        t0 = next((i for i in range(idx.get(d, -1) + 1 if d in idx else 0,
                                    len(trade_dates))
                   if trade_dates[i] > d), None)
        if t0 is None or t0 + k >= len(trade_dates):
            return None
        p0, pk = (prices.get(tk, {}).get(trade_dates[t0]),
                  prices.get(tk, {}).get(trade_dates[t0 + k]))
        b0, bk = (prices.get("SPY", {}).get(trade_dates[t0]),
                  prices.get("SPY", {}).get(trade_dates[t0 + k]))
        if None in (p0, pk, b0, bk) or 0 in (p0, b0):
            return None
        return ((pk / p0 - 1) - (bk / b0 - 1)) * 100.0

    scores = {"client_signal": [[sig.get((t, d)) for t in covered]
                                for d in dates]}
    fwd = {k: [[ret_k(t, d, k) for t in covered] for d in dates] for k in KS}
    panel = Panel(dates=[d.isoformat() for d in dates], names=covered,
                  scores=scores, fwd=fwd, weights={"client_signal": 1.0})

    lab = DecompositionLab(panel, k_primary=K_PRIMARY, B=2000, seed=SEED)
    comp = "client_signal"
    suite = {
        "data_status": lab.data_status(comp),
        "ic_primary_k5": lab.ic(comp),
        "quantiles": lab.quantile_table(comp),
        "churn": lab.churn(comp),
        "placebo": lab.placebo(comp),
        "horizon_decay": lab.horizon_decay(comp, ks=KS),
    }

    result = {
        "protocol_id": pid,
        "intake": intake_report,
        "coverage": {"covered_tickers": covered,
                     "excluded_out_of_universe": excl_counts,
                     "n_excluded_rows": sum(excl_counts.values())},
        "suite": suite,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    (out_dir / "signal_suite.json").write_text(
        json.dumps(result, indent=2, default=str))
    result_hash = hashlib.sha256(
        json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"{intake_report['date_range'][0]}.."
                     f"{intake_report['date_range'][1]}, "
                     f"{len(covered)} covered tickers"),
        n_primary_cells=1, n_secondary_cells=8, result_hash=result_hash,
        note="client-signal decomposition suite run"))
    reg.verify_chain()
    result["result_hash"] = result_hash
    return result


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: yuclaw_client_signal_lab.py <client.csv> <out_dir>")
        return 2
    try:
        r = run_suite(args[0], args[1])
    except IntakeError as e:
        print("INTAKE REJECTED — fix the following and resubmit:")
        for prob in e.problems:
            print(f"  · {prob}")
        return 2
    s = r["suite"]
    ic = s["ic_primary_k5"]
    print(f"[client-signal] protocol {r['protocol_id']} · "
          f"{r['intake']['n_rows']} rows · covered {len(r['coverage']['covered_tickers'])} "
          f"tickers · excluded {r['coverage']['n_excluded_rows']} rows "
          f"({len(r['coverage']['excluded_out_of_universe'])} tickers)")
    if ic:
        print(f"  IC(k=5)={ic['mean_ic']:+.4f} CI({ic['ci'][0]:+.4f},{ic['ci'][1]:+.4f}) "
              f"days={ic['days']} [{ic['badge']}]")
    q = s["quantiles"]
    print(f"  monotonicity={q['monotonicity_spearman']:+.3f} "
          f"T-B={q['top_minus_bottom_pct']}% adj={q['adjacent_ordering']}")
    print(f"  churn: {s['churn']}")
    print(f"  placebo: {s['placebo']}")
    for h in s["horizon_decay"]:
        if h:
            print(f"  decay k={h['k']}: IC={h['mean_ic']:+.4f} [{h['badge']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
