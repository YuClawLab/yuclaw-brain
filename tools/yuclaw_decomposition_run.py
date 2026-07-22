#!/usr/bin/env python3
"""
Decomposition Lab — REAL-DATA staged run (owner-directed, 2026-07-22).

Builds the Panel from the point-in-time signal_snapshots path:
  * C1–C9 per-component scores + composite, forward-OOS window ONLY
    (signal_time >= 2026-05-20, is_backfill = false) — the in-sample regime
    never enters this panel.
  * forward benchmark-relative returns at k ∈ {1,2,5,10,20}: close-to-close
    ticker return minus SPY return over the same k trading days, from
    price_history — the same substrate the Forward Tracking Ledger uses.
  * instrument classes from v3/universe.json (the universe config's own
    groups: equities→EQUITY, sector_etfs→SECTOR_ETF, broad_etfs→BROAD_ETF,
    macro→MACRO). Nothing typed by hand.

C4 is frozen (2026-05-18) — it must arrive as its true constant values and
be flagged DATA-LIMITED by the module. That is correct output, not an error.

Renders docs/preview/decomposition_lab.html (PREVIEW banner, unlinked).
Lab page untouched.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from html import escape
from pathlib import Path

import psycopg2

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "tools"))

from yuclaw_signal_decomposition import (DecompositionLab, METHOD_HASH, Panel)
from v3.signal.base import COMPONENT_WEIGHTS

DSN = "dbname=yuclaw_events"
FORWARD_DAY0 = "2026-05-20"
KS = (1, 2, 5, 10, 20)
COMPS = tuple(sorted(COMPONENT_WEIGHTS))          # c1..c9
OUT = _REPO / "docs" / "preview" / "decomposition_lab.html"

BANNER = (
    '<div style="background:#3D2B00;border:2px solid #FBA94B;border-radius:10px;'
    'padding:14px 18px;margin-bottom:18px;font-size:13px;color:#FBA94B;font-weight:700">'
    'PREVIEW — real data, not yet part of the daily build. Unlinked page; '
    'forward-OOS window only (from 2026-05-20). Research classifications, '
    'not recommendations.</div>')


def _classes() -> dict[str, str]:
    u = json.loads((_REPO / "v3" / "universe.json").read_text())
    lab = {"equities": "EQUITY", "sector_etfs": "SECTOR_ETF",
           "broad_etfs": "BROAD_ETF", "macro": "MACRO"}
    out: dict[str, str] = {}
    for grp, cls in lab.items():
        entries = u.get(grp) or []
        for e in entries:
            tk = e if isinstance(e, str) else e.get("ticker")
            if tk:
                out[tk] = cls
    return out


def build_panel() -> Panel:
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT signal_time::date, ticker, total_score,
                          c1_price_momentum, c2_volume_confirm, c3_sector_velocity,
                          c4_macro_regime, c5_oil_rates_fx, c6_event_impact,
                          c7_peer_correlation, c8_cascade_effect, c9_model_trust
                   FROM signal_snapshots
                   WHERE is_backfill = false AND signal_time::date >= %s
                   ORDER BY 1, 2""", (FORWARD_DAY0,))
            snaps = cur.fetchall()
            cur.execute(
                """SELECT ticker, trade_date, close FROM price_history
                   WHERE close IS NOT NULL AND trade_date >= %s::date - 5
                   ORDER BY ticker, trade_date""", (FORWARD_DAY0,))
            px_rows = cur.fetchall()

    dates = sorted({r[0] for r in snaps})
    names = sorted({r[1] for r in snaps})
    d_ix = {d: i for i, d in enumerate(dates)}
    n_ix = {n: i for i, n in enumerate(names)}

    # prices: ticker -> ordered (trade_date, close)
    px: dict[str, list] = {}
    for tk, td, c in px_rows:
        px.setdefault(tk, []).append((td, float(c)))
    px_dates = {tk: [d for d, _ in v] for tk, v in px.items()}
    px_close = {tk: {d: c for d, c in v} for tk, v in px.items()}

    def fwd_rel(tk: str, d0: date, k: int):
        """(P[t0+k]/P[t0] - 1) - same for SPY, in %, k in trading days;
        t0 = first trade date >= signal date. None if window incomplete."""
        out = {}
        for sym in (tk, "SPY"):
            ds = px_dates.get(sym)
            if not ds:
                return None
            i0 = next((i for i, dd in enumerate(ds) if dd >= d0), None)
            if i0 is None or i0 + k >= len(ds):
                return None
            p0 = px_close[sym][ds[i0]]
            p1 = px_close[sym][ds[i0 + k]]
            if not p0:
                return None
            out[sym] = (p1 / p0 - 1.0) * 100.0
        return out[tk] - out["SPY"]

    scores = {c: [[None] * len(names) for _ in dates] for c in COMPS}
    scores["composite"] = [[None] * len(names) for _ in dates]
    fwd = {k: [[None] * len(names) for _ in dates] for k in KS}

    col = {c: 3 + i for i, c in enumerate(
        ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9"))}
    for r in snaps:
        d, tk, total = r[0], r[1], r[2]
        di, ni = d_ix[d], n_ix[tk]
        scores["composite"][di][ni] = float(total) if total is not None else None
        for c in COMPS:
            v = r[col[c]]
            scores[c][di][ni] = float(v) if v is not None else None
        for k in KS:
            fwd[k][di][ni] = fwd_rel(tk, d, k)

    classes = _classes()
    weights = dict(COMPONENT_WEIGHTS)
    return Panel(dates=[d.isoformat() for d in dates], names=names,
                 scores=scores, fwd=fwd, weights=weights,
                 classes={n: classes.get(n, "EQUITY") for n in names})


def main() -> int:
    build = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                           capture_output=True, text=True).stdout.strip()[:8]
    panel = build_panel()
    n_cells = sum(1 for c in COMPS for day in panel.scores[c] for v in day
                  if v is not None)
    print(f"[decomp] build {build} · method {METHOD_HASH} · "
          f"{len(panel.dates)} dates x {len(panel.names)} names · "
          f"{n_cells} component cells")

    lab = DecompositionLab(panel)
    res = lab.run_all()
    red = lab.redundancy_matrix()
    decay = {c: lab.horizon_decay(c) for c in COMPS
             if not res["components"][c]["data_status"]["data_limited"]}
    plac = {c: lab.placebo(c) for c in decay}
    classes_present = sorted(set(panel.classes.values()))
    seg = {c: {cls: lab.ic(c, subset=cls) for cls in classes_present}
           for c in decay}

    # ---------- text report ----------
    print(f"\nprotocol {res['protocol_id']} · {res['primary_endpoint']} · "
          f"{res['n_secondary_cells']} secondary cells")
    for c in sorted(res["components"]):
        row = res["components"][c]
        st = row["data_status"]
        if st["data_limited"]:
            print(f"  {c.upper()}: DATA-LIMITED {st}")
            continue
        ic = row["ic"]
        tb = row['quantiles']['top_minus_bottom_pct']
        print(f"  {c.upper()}: IC={ic['mean_ic']:+.3f} CI({ic['ci'][0]:+.4f},"
              f"{ic['ci'][1]:+.4f}) [{ic['badge']}] days={ic['days']}"
              f" · partial={row['partial']['mean_partial_ic']:+.3f}"
              f" · marginal={row['marginal']['marginal']:+.4f}"
              f" · mono={row['quantiles']['monotonicity_spearman']:+.2f}"
              f" · T-B={(f'{tb:+.3f}%' if tb is not None else 'n/a')}"
              f" · autocorr1d={row['churn']['rank_autocorr_1d']}"
              f" · placebo_pctile={plac[c]['percentile_in_null']}")
    print("\nREDUNDANCY (|rho|>0.6 pairs):")
    for (a, b), v in sorted(red.items()):
        if abs(v) > 0.6:
            print(f"  {a}~{b}: {v:+.2f}")
    print("\nHORIZON DECAY (IC at k=1/2/5/10/20):")
    for c, dd in decay.items():
        print(f"  {c.upper()}: " + " ".join(
            f"k{v['k']}:{v['mean_ic']:+.3f}" for v in dd if v))
    print("\nPER-CLASS (IC at k=5):")
    for c, m in seg.items():
        cells = " ".join(
            (f"{cls}:{v['mean_ic']:+.3f}(d={v['days']},xn={v['median_xsec_n']})"
             if v else f"{cls}:—") for cls, v in m.items())
        print(f"  {c.upper()}: {cells}")

    # ---------- preview HTML ----------
    def table_html():
        rows = []
        for c in sorted(res["components"]):
            row = res["components"][c]
            if row["data_status"]["data_limited"]:
                rows.append(f"<tr><td><b>{c.upper()}</b></td>"
                            f"<td colspan='7' style='color:#FBA94B'>DATA-LIMITED "
                            f"(frozen/constant input — flagged, not scored)</td></tr>")
                continue
            ic, q = row["ic"], row["quantiles"]
            rows.append(
                f"<tr><td><b>{c.upper()}</b></td>"
                f"<td>{ic['mean_ic']:+.3f} <span style='color:#718096'>({ic['ci'][0]:+.3f},"
                f"{ic['ci'][1]:+.3f})</span></td><td>{ic['badge']}</td>"
                f"<td>{row['partial']['mean_partial_ic']:+.3f}</td>"
                f"<td>{row['marginal']['marginal']:+.4f}</td>"
                f"<td>{q['monotonicity_spearman']:+.2f}</td>"
                f"<td>{row['churn']['rank_autocorr_1d']}</td>"
                f"<td>{plac[c]['percentile_in_null']}</td></tr>")
        return ("<table style='width:100%;border-collapse:collapse;font-size:12px'>"
                "<thead><tr><th>Comp</th><th>IC (95% CI)</th><th>Badge</th>"
                "<th>Partial</th><th>Marginal ΔIC</th><th>Mono</th><th>Churn</th>"
                "<th>Placebo pctile</th></tr></thead><tbody>"
                + "".join(rows) + "</tbody></table>")

    red_html = "".join(
        f"<tr><td>{a}~{b}</td><td>{v:+.2f}</td></tr>"
        for (a, b), v in sorted(red.items()) if abs(v) > 0.6)
    decay_html = "".join(
        f"<tr><td><b>{c.upper()}</b></td>" +
        "".join(f"<td>{v['mean_ic']:+.3f}</td>" if v else "<td>—</td>" for v in dd)
        + "</tr>" for c, dd in decay.items())
    def _seg_cell(v):
        return f"{v['mean_ic']:+.3f} (d={v['days']})" if v else "—"

    seg_html = "".join(
        f"<tr><td><b>{c.upper()}</b></td>"
        + "".join(f"<td>{_seg_cell(v)}</td>" for v in m.values()) + "</tr>"
        for c, m in seg.items())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>PREVIEW — Decomposition Lab</title>"
        "<body style='background:#0b0f14;color:#E2E8F0;font-family:Inter,sans-serif;"
        "padding:30px;max-width:960px;margin:0 auto'>" + BANNER +
        f"<h1 style='font-size:20px'>Signal Decomposition — forward-OOS panel</h1>"
        f"<p style='color:#A0AEC0;font-size:12.5px'>build {build} · method {METHOD_HASH} · "
        f"protocol {res['protocol_id']} · {len(panel.dates)} snapshot dates × "
        f"{len(panel.names)} names · window {panel.dates[0]} → {panel.dates[-1]} · "
        f"primary endpoint: {escape(res['primary_endpoint'])} · benchmark-relative "
        f"(vs SPY) forward returns · point-in-time scores</p>"
        "<h2 style='font-size:15px;margin-top:18px'>Per-component table</h2>" + table_html() +
        "<h2 style='font-size:15px;margin-top:18px'>Redundancy (|rho| &gt; 0.6)</h2>"
        "<table style='font-size:12px'><thead><tr><th>Pair</th><th>rho</th></tr></thead>"
        f"<tbody>{red_html or '<tr><td colspan=2>none above threshold</td></tr>'}</tbody></table>"
        "<h2 style='font-size:15px;margin-top:18px'>Horizon decay (IC at k=1/2/5/10/20)</h2>"
        "<table style='font-size:12px'><thead><tr><th>Comp</th><th>k=1</th><th>k=2</th>"
        f"<th>k=5</th><th>k=10</th><th>k=20</th></tr></thead><tbody>{decay_html}</tbody></table>"
        "<h2 style='font-size:15px;margin-top:18px'>Per-class IC (k=5)</h2>"
        "<table style='font-size:12px'><thead><tr><th>Comp</th>"
        + "".join(f"<th>{cls}</th>" for cls in classes_present)
        + f"</tr></thead><tbody>{seg_html}</tbody></table>"
        "<p style='color:#718096;font-size:11.5px;margin-top:20px'>Research and education "
        "only. Not investment advice. Component diagnostics are research classifications, "
        "not recommendations. No forward alpha is established.</p></body>")
    print(f"\n[decomp] preview -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
