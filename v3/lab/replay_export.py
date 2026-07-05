"""Export the Validation Lab replay bundle to docs/replay/lab_replay_bundle.json.

The bundle is the reproducibility artifact for the Lab: everything needed to
recompute the page's core tables OFF this box, plus the expected outputs and
the ledger anchors to verify against.

COMPLIANT DATA PATH (stated here and on the page): the bundle contains ONLY
YUCLAW-derived data — composite scores, locked signal labels, snapshot content
hashes, per-period DERIVED returns (close[exit]/close[entry] - 1, computed
in-house), and derived 1/5/20-day track-record returns. NO raw vendor OHLCV
rows (Finnhub/Polygon/yfinance ToS) are exported. Users who want to extend the
analysis to raw prices supply their own licensed price feed; the bundled
derived returns are sufficient to reproduce every table on the page.

Regenerated daily by cron/refresh_v3_pages.sh alongside the page renders.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from v3.lab.cohort_engine import (DECILE_FRACTION, DSN, FORWARD_DAY0,
                                  MIN_UNIVERSE_FOR_DECILES, compute_panel)
from v3.lab.rigor import compute_rigor
from v3.lab.stats import BOOTSTRAP_SEED

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "replay" / "lab_replay_bundle.json"
TRUST_REPO = Path.home() / "yuclaw-trust"


def _git_head(path: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path,
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def _panel_inputs(panel: str) -> dict:
    """Per-rebalance derived inputs (full float precision, no rounding — the
    replay must reproduce bit-comparable statistics)."""
    is_backfill = panel == "in_sample"

    # per-ticker period returns aligned to the engine's rebalance schedule so
    # the replay can REBUILD the decile cohorts from scores and re-derive the
    # cohort aggregates itself (period return = derived statistic, not OHLCV)
    from v3.lab.cohort_engine import _entry_date, _period_return, load_prices, load_snapshots
    snaps = load_snapshots(panel)
    prices, trade_dates = load_prices()
    rebal_dates = sorted(snaps.keys())
    if panel == "in_sample":
        terminal_exit = _entry_date(trade_dates, FORWARD_DAY0)
    else:
        terminal_exit = trade_dates[-1] if trade_dates else None
    rebalances = []
    for i, rd in enumerate(rebal_dates):
        d0 = _entry_date(trade_dates, rd)
        nxt = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else None
        d1 = _entry_date(trade_dates, nxt) if nxt else terminal_exit
        if d0 is None or d1 is None or d1 <= d0:
            continue
        day = snaps[rd]
        rets = {tk: _period_return(prices.get(tk, {}), d0, d1) for tk in day}
        spy_ret = _period_return(prices.get("SPY", {}), d0, d1)
        if spy_ret is None:
            continue
        rebalances.append({
            "signal_date": rd.isoformat(),
            "entry": d0.isoformat(), "exit": d1.isoformat(),
            "scores": {tk: float(v["score"]) for tk, v in sorted(day.items())},
            "labels": {tk: v["label"] for tk, v in sorted(day.items())},
            "period_returns": {tk: r for tk, r in sorted(rets.items()) if r is not None},
            "spy_ret": spy_ret,
        })

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            # derived multi-horizon returns for the IC replication
            cur.execute(
                """SELECT signal_date, ticker, total_score,
                          return_1d, return_5d, return_20d
                   FROM track_record WHERE is_backfill = %s
                   ORDER BY signal_date, ticker""",
                (is_backfill,),
            )
            ic_rows = [
                {"date": d.isoformat(), "ticker": tk, "score": float(s),
                 "r1": float(r1) if r1 is not None else None,
                 "r5": float(r5) if r5 is not None else None,
                 "r20": float(r20) if r20 is not None else None}
                for d, tk, s, r1, r5, r20 in cur.fetchall()
            ]

    pres = compute_panel(panel)
    return {
        "rebalances": rebalances,
        "window": ([pres.get("first_entry_date"), pres.get("last_exit_date")]
                   if pres.get("evaluable") else None),
        "ic_rows": ic_rows,
    }


# component columns in ledger (v3/proof/ledger.py) convention
_COMPONENT_COLS = {
    "c1": "c1_price_momentum", "c2": "c2_volume_confirm", "c3": "c3_sector_velocity",
    "c4": "c4_macro_regime", "c5": "c5_oil_rates_fx", "c6": "c6_event_impact",
    "c7": "c7_peer_correlation", "c8": "c8_cascade_effect", "c9": "c9_model_trust",
}


def _ledger_leaves() -> dict[str, list[dict]]:
    """Per UTC date, the exact inputs the public ledger hashes: snapshot_id,
    total_score, component scores (None -> 0.0, the ledger convention). This
    lets the replay script recompute every leaf content_hash AND the daily
    root and match them against the public yuclaw-trust ledger."""
    cols = ", ".join(_COMPONENT_COLS.values())
    out: dict[str, list[dict]] = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                f"""SELECT (signal_time AT TIME ZONE 'UTC')::date, ticker,
                           snapshot_id, total_score, {cols}
                    FROM signal_snapshots WHERE is_backfill = false
                    ORDER BY 1, ticker""")
            for row in cur.fetchall():
                d, tk, sid, score = row[0], row[1], row[2], float(row[3])
                comps = {cid: (float(v) if v is not None else 0.0)
                         for cid, v in zip(_COMPONENT_COLS, row[4:])}
                out.setdefault(d.isoformat(), []).append(
                    {"ticker": tk, "snapshot_id": sid, "total_score": score,
                     "components": comps})
    return out


def _ledger_blocks() -> list[dict]:
    """Daily roots from the public yuclaw-trust ledger (date + root only)."""
    ledger_file = TRUST_REPO / "verified_research_ledger.jsonl"
    blocks = []
    if ledger_file.exists():
        for line in ledger_file.read_text().splitlines():
            try:
                b = json.loads(line)
                blocks.append({"date": b["date"], "daily_root": b["daily_root"],
                               "snapshot_count": b.get("snapshot_count"),
                               "entry_hashes": [e["content_hash"]
                                                for e in b.get("entries", [])]})
            except Exception:
                continue
    return blocks


def main() -> int:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bundle = {
        "artifact": "YUCLAW Validation Lab replay bundle",
        "disclaimer": ("Hypothetical research illustration. Not investment advice. "
                       "Research classifications, not recommendations. "
                       "Derived data only — no raw vendor market data."),
        "built_utc": built,
        "source_commit": _git_head(_REPO),
        "ledger_commit": _git_head(TRUST_REPO),
        "ledger_repo": "https://github.com/YuClawLab/yuclaw-trust",
        "methodology": {
            "decile_fraction": DECILE_FRACTION,
            "min_universe_for_deciles": MIN_UNIVERSE_FOR_DECILES,
            "forward_day0": FORWARD_DAY0.isoformat(),
            "bootstrap": {"iters": 10000, "seed": BOOTSTRAP_SEED, "scheme": "percentile, i.i.d. period resampling"},
            "in_sample_terminal_cap": "final in-sample holding period exits at forward_day0",
            "hash": "content_hash per snapshot (sha256, see v3/proof/_hash.py); daily_root = sha256('|'.join(sorted(hashes)))",
        },
        "panels": {p: _panel_inputs(p) for p in ("forward", "in_sample")},
        "ledger_leaves": _ledger_leaves(),
        "ledger_daily_roots": _ledger_blocks(),
        "expected": compute_rigor(),   # what tools/replay_lab.py must reproduce
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, indent=1, default=str))
    print(f"[replay_export] wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
