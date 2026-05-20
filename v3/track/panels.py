"""
Two-panel aggregation:
  - BACKTEST panel       (is_backfill=true)   — in-sample replay
  - FORWARD TRACKING     (is_backfill=false)  — live emissions, OOS

Per panel:
  - Per signal_label and overall:
      n_signals             total snapshots
      n_directional         signals with non-NULL hit (excl. HOLD/WATCH)
      n_matured_{1,5,20}d   how many have a non-NULL return_Nd
      hit_rate_{1,5,20}d    over matured + directional only
      median_return_{N}d / mean_return_{N}d
      median_excess_{N}d / mean_excess_{N}d

We never compute a hit_rate over unmatured rows, and we never assume non-
directional labels are "hits" or "misses". Every output explicitly carries
the denominator so a reader can't confuse coverage with signal.

CLI:
    python3 -m v3.track.panels
    python3 -m v3.track.panels --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.sources.edgar_poll import DB_DSN

HORIZONS = (1, 5, 20)
DIRECTIONAL_LABELS = {"STRONG_BUY", "BUY", "WEAKENING", "NEGATIVE_EVENT", "DOWNSIDE_WATCH"}


def _safe_median(xs: list[float]) -> Optional[float]:
    return statistics.median(xs) if xs else None


def _safe_mean(xs: list[float]) -> Optional[float]:
    return statistics.mean(xs) if xs else None


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one bucket (typically all rows for one label, or 'overall')."""
    out: dict[str, Any] = {"n_signals": len(rows)}
    out["n_directional"] = sum(1 for r in rows if r["signal_label"] in DIRECTIONAL_LABELS)

    for n in HORIZONS:
        ret_col = f"return_{n}d"
        exc_col = f"excess_return_{n}d"
        hit_col = f"hit_{n}d"

        matured = [r for r in rows if r[ret_col] is not None]
        out[f"n_matured_{n}d"] = len(matured)

        # hits over matured AND directional rows
        eligible = [r for r in matured if r[hit_col] is not None]
        hits = sum(1 for r in eligible if r[hit_col])
        out[f"n_eligible_{n}d"] = len(eligible)
        out[f"hit_rate_{n}d"] = (hits / len(eligible)) if eligible else None

        returns = [float(r[ret_col]) for r in matured if r[ret_col] is not None]
        excess = [float(r[exc_col]) for r in matured if r[exc_col] is not None]
        out[f"median_return_{n}d"] = _safe_median(returns)
        out[f"mean_return_{n}d"] = _safe_mean(returns)
        out[f"median_excess_{n}d"] = _safe_median(excess)
        out[f"mean_excess_{n}d"] = _safe_mean(excess)

    return out


def build_panels() -> dict[str, Any]:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM track_record ORDER BY signal_date")
            all_rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    panels: dict[str, Any] = {}
    for is_backfill, panel_name in [(True, "backtest"), (False, "forward")]:
        rows = [r for r in all_rows if r["is_backfill"] is is_backfill]
        labels_present = sorted({r["signal_label"] for r in rows})
        per_label = {}
        for lbl in labels_present:
            per_label[lbl] = _summarize([r for r in rows if r["signal_label"] == lbl])
        overall = _summarize(rows)
        date_range = ([r["signal_date"] for r in rows] or [None])
        panels[panel_name] = {
            "is_backfill": is_backfill,
            "n_total": len(rows),
            "date_min": min(date_range) if rows else None,
            "date_max": max(date_range) if rows else None,
            "overall": overall,
            "per_label": per_label,
        }
    return panels


def format_text(panels: dict[str, Any]) -> str:
    lines: list[str] = []
    for panel_name, header in [
        ("backtest", "BACKTEST RESULTS — In-Sample Replay"),
        ("forward",  "FORWARD TRACKING LEDGER — Out-of-Sample"),
    ]:
        p = panels[panel_name]
        lines.append("=" * 90)
        lines.append(header)
        lines.append(f"  date range: {p['date_min']} → {p['date_max']}   "
                     f"signals: {p['n_total']}   directional: {p['overall']['n_directional']}")
        lines.append("=" * 90)
        lines.append(f"  {'label':<16s} {'n':>5s} {'dir':>5s}  "
                     f"{'matured 1d/5d/20d':>20s}  "
                     f"{'hit 1d/5d/20d':>20s}  "
                     f"{'median ret 5d':>14s}")
        lines.append("  " + "-" * 86)
        # Per-label rows
        for lbl in sorted(p["per_label"]):
            s = p["per_label"][lbl]
            mat = f"{s['n_matured_1d']}/{s['n_matured_5d']}/{s['n_matured_20d']}"
            hit_strs = []
            for n in HORIZONS:
                hr = s[f"hit_rate_{n}d"]
                hit_strs.append(f"{hr*100:.0f}%" if hr is not None else "  -")
            hit = "/".join(hit_strs)
            med5 = s["median_return_5d"]
            med5_str = f"{med5*100:+.2f}%" if med5 is not None else "    -"
            lines.append(f"  {lbl:<16s} {s['n_signals']:>5d} {s['n_directional']:>5d}  "
                         f"{mat:>20s}  {hit:>20s}  {med5_str:>14s}")
        # Overall row
        s = p["overall"]
        mat = f"{s['n_matured_1d']}/{s['n_matured_5d']}/{s['n_matured_20d']}"
        hit_strs = []
        for n in HORIZONS:
            hr = s[f"hit_rate_{n}d"]
            hit_strs.append(f"{hr*100:.0f}%" if hr is not None else "  -")
        hit = "/".join(hit_strs)
        med5 = s["median_return_5d"]
        med5_str = f"{med5*100:+.2f}%" if med5 is not None else "    -"
        lines.append("  " + "-" * 86)
        lines.append(f"  {'OVERALL':<16s} {s['n_signals']:>5d} {s['n_directional']:>5d}  "
                     f"{mat:>20s}  {hit:>20s}  {med5_str:>14s}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    panels = build_panels()
    if args.json:
        print(json.dumps(panels, indent=2, default=str))
    else:
        print(format_text(panels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
