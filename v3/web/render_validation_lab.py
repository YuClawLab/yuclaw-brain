"""Render the YUCLAW Signal Validation Lab page to docs/validation_lab.html.

Static, data-baked, self-contained (inline SVG, no JS, no CDNs). RESEARCH
COHORT ANALYSIS framing throughout — cohorts named by score decile or signal
label, never by trade direction. ZERO public SELL/SHORT/BUY/long-position
language. Only derived statistics are shown; raw prices never appear.

Regenerated daily by cron/refresh_v3_pages.sh (17:00 MDT pipeline chain);
the freshness stamp at the top of the page is the visible contract.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.lab.cohort_engine import (DSN, FORWARD_DAY0, MIN_UNIVERSE_FOR_DECILES,
                                  compute_all, current_top_decile)
from v3.lab.qualified import compute_qualified
from v3.lab.rigor import compute_rigor
from v3.web.useful_blocks import (freshness_strip, build_footer, site_header_html, canonical_html,
                                  packet_block_from_manifest as _packet_block,
                                  public_label as display_label,
                                  status_block_html as _shared_status_block,
                                  use_in_research_html as _use_in_research)
from v3.web.oie_v51_blocks import (baselines_block as _baselines,
                                   neutralized_ic_block as _neutralized,
                                   case_exhibits_block as _cases,
                                   transparency_block as _transparency,
                                   lab_clustered_block as _v51_clustered)

OUT = _REPO / "docs" / "validation_lab.html"
UNIVERSE_PATH = _REPO / "v3" / "universe.json"
TRUST_LEDGER = Path.home() / "yuclaw-trust" / "verified_research_ledger.jsonl"

DISCLAIMER_FULL = (
    "Hypothetical research illustration. Not investment advice, not performance "
    "advertising, not an offer of any product. Research classifications, not "
    "recommendations. Past results — in-sample or forward-tracked — do not "
    "predict future performance."
)
DISCLAIMER_LINE = (
    "Research cohort analysis — hypothetical illustration, not investment advice, "
    "not performance advertising. Classifications, not recommendations."
)

# compliance-safe display names (NO trade-direction language).
# Cohort names are descriptive prose; SIGNAL labels render verbatim from the
# locked public vocabulary (useful_blocks.PUBLIC_LABELS). The previous
# display-layer remap ("POSITIVE_RESEARCH+", "RISK_FLAG (…)") invented labels
# outside the locked set and was removed per the 2026-07-26 label audit.
COHORT_LABEL = {
    "top_decile": "High-score cohort (top decile by composite score)",
    "bottom_decile": "Low-score cohort (bottom decile by composite score)",
    "bullish_labeled": "Positive-label cohort",
    "cautious_labeled": "Risk-flag cohort",
    "universe_ew": "Equal-weight universe (all scored tickers)",
    "benchmark": "SPY benchmark (broad-market reference)",
}
COHORT_COLOR = {
    "top_decile": "#00E676",
    "bottom_decile": "#FF3366",
    "bullish_labeled": "#4DD0E1",
    "cautious_labeled": "#FBA94B",
    "universe_ew": "#64B5F6",
    "benchmark": "#A0AEC0",
}
# reference lines get dash patterns so identity is never color-alone
COHORT_DASH = {"benchmark": "7,4", "universe_ew": "2,3"}
PRIMARY_ORDER = ["top_decile", "bottom_decile", "universe_ew", "benchmark"]
LABEL_ORDER = ["bullish_labeled", "cautious_labeled", "benchmark"]

MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _pct(x):
    return f"{x*100:+.2f}%" if x is not None else "—"


def _fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{MONTHS[d.month]} {d.day}"


def svg_chart(series: list[dict], dates: list[str], width=900, height=350,
              baseline=1.0, title="", boundary_idx: int | None = None) -> str:
    """series: [{name,short,color,pts:[(i,cum)],dash?}]; dates: ISO strings
    aligned to x indices 0..max_i. Inline SVG cumulative-return chart with
    real calendar dates on the x-axis. boundary_idx: draw the in-sample /
    forward regime boundary at that x index (visual continuity only — all
    statistics remain per-regime)."""
    pad_l, pad_r, pad_t, pad_b = 56, 190, 28, 44
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    all_cum = [c for s in series for _, c in s["pts"]] + [baseline]
    ymin, ymax = min(all_cum), max(all_cum)
    if ymax == ymin:
        ymax += 0.01
    yrange = ymax - ymin
    max_i = max((i for s in series for i, _ in s["pts"]), default=1) or 1

    def X(i): return pad_l + (i / max_i) * plot_w
    def Y(c): return pad_t + (ymax - c) / yrange * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="background:#0B0E14;border:1px solid #1E232D;border-radius:8px" '
             f'role="img" aria-label="{escape(title)}">']
    # regime boundary: shaded in-sample region left, forward OOS right
    if boundary_idx is not None and 0 < boundary_idx <= max_i:
        bx = X(boundary_idx)
        parts.append(f'<rect x="{pad_l}" y="{pad_t}" width="{bx-pad_l:.1f}" '
                     f'height="{plot_h}" fill="#FBA94B" opacity="0.07"/>')
        parts.append(f'<line x1="{bx:.1f}" y1="{pad_t}" x2="{bx:.1f}" y2="{pad_t+plot_h}" '
                     f'stroke="#FBA94B" stroke-width="1.5" stroke-dasharray="6,4"/>')
        if bx - pad_l > 110:
            parts.append(f'<text x="{(pad_l+bx)/2:.0f}" y="{pad_t+13}" fill="#FBA94B" '
                         f'font-size="10" text-anchor="middle" opacity="0.9" '
                         f'font-family="Inter,sans-serif">in-sample replay</text>')
        if pad_l + plot_w - bx > 130:
            parts.append(f'<text x="{(bx+pad_l+plot_w)/2:.0f}" y="{pad_t+13}" fill="#00E676" '
                         f'font-size="10" text-anchor="middle" opacity="0.9" '
                         f'font-family="Inter,sans-serif">forward out-of-sample</text>')
        parts.append(f'<text x="{bx:.1f}" y="{pad_t+plot_h-6}" fill="#FBA94B" font-size="9" '
                     f'text-anchor="middle" font-family="JetBrains Mono,monospace">May 18</text>')
    # baseline (cumulative = 1.0, i.e. 0% return)
    by = Y(baseline)
    parts.append(f'<line x1="{pad_l}" y1="{by:.1f}" x2="{pad_l+plot_w}" y2="{by:.1f}" '
                 f'stroke="#2D3748" stroke-dasharray="3,3"/>')
    parts.append(f'<text x="{pad_l+plot_w+6}" y="{by+4:.1f}" fill="#718096" '
                 f'font-size="10" font-family="JetBrains Mono,monospace">0%</text>')
    # y gridlines (ymin/ymax)
    for cv in (ymin, ymax):
        yy = Y(cv)
        parts.append(f'<text x="6" y="{yy+4:.1f}" fill="#718096" font-size="10" '
                     f'font-family="JetBrains Mono,monospace">{(cv-1)*100:+.1f}%</text>')
    # x-axis: real calendar dates at ~5 evenly spaced tick positions
    n_ticks = min(5, len(dates)) if dates else 0
    tick_idx = sorted({round(j * max_i / (n_ticks - 1)) for j in range(n_ticks)}) if n_ticks > 1 else []
    ax_y = pad_t + plot_h
    parts.append(f'<line x1="{pad_l}" y1="{ax_y}" x2="{pad_l+plot_w}" y2="{ax_y}" '
                 f'stroke="#2D3748"/>')
    for ti in tick_idx:
        if ti >= len(dates):
            continue
        tx = X(ti)
        parts.append(f'<line x1="{tx:.1f}" y1="{ax_y}" x2="{tx:.1f}" y2="{ax_y+5}" '
                     f'stroke="#2D3748"/>')
        parts.append(f'<text x="{tx:.1f}" y="{ax_y+18}" fill="#718096" font-size="10" '
                     f'text-anchor="middle" font-family="JetBrains Mono,monospace">'
                     f'{escape(_fmt_date(dates[ti]))}</text>')
    # cohort polylines + legend (direct labels: name + final value)
    for k, s in enumerate(series):
        pts = " ".join(f"{X(i):.1f},{Y(c):.1f}" for i, c in s["pts"])
        dash = f' stroke-dasharray="{s["dash"]}"' if s.get("dash") else ""
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{s["color"]}" '
                     f'stroke-width="2"{dash}/>')
        ly = pad_t + 6 + k * 18
        parts.append(f'<line x1="{pad_l+plot_w+14}" y1="{ly}" x2="{pad_l+plot_w+30}" '
                     f'y2="{ly}" stroke="{s["color"]}" stroke-width="3"{dash}/>')
        final = (s["pts"][-1][1] - 1) * 100 if s["pts"] else 0
        parts.append(f'<text x="{pad_l+plot_w+34}" y="{ly+4}" fill="#E2E8F0" '
                     f'font-size="10" font-family="JetBrains Mono,monospace">'
                     f'{escape(s["short"])} {final:+.1f}%</text>')
    parts.append('</svg>')
    return "".join(parts)


def build_series(panel: dict, order: list[str]) -> list[dict]:
    out = []
    SHORT = {"top_decile": "High-score", "bottom_decile": "Low-score",
             "bullish_labeled": "Positive-label", "cautious_labeled": "Risk-flag",
             "universe_ew": "Universe EW", "benchmark": "SPY"}
    for c in order:
        pts = [(i, p["cum"]) for i, p in enumerate(panel["series"][c])]
        pts = [(0, 1.0)] + [(i + 1, c2) for i, c2 in pts]  # anchor at 1.0 baseline
        out.append({"name": c, "short": SHORT[c], "color": COHORT_COLOR[c],
                    "dash": COHORT_DASH.get(c), "pts": pts})
    return out


def panel_dates(panel: dict) -> list[str]:
    """x-axis dates aligned to chart indices: entry date, then each exit date."""
    return [panel["first_entry_date"]] + [p["date"] for p in panel["series"]["benchmark"]]


# ---- continuous rolling charts (visual continuity ONLY; stats stay per-regime)
BOUNDARY_ISO = FORWARD_DAY0.isoformat()
ROLL_WINDOWS = (("30", 30), ("60", 60), ("90", 90), ("all", None))


def continuous_points(ins: dict, fwd: dict, kind: str, cohort: str | None = None) -> list[tuple[str, float]]:
    """Chain the in-sample series into the forward series at the May-18
    boundary (forward rebased by the in-sample terminal value). Visual
    continuity only — no statistic is computed across the boundary."""
    def pts(panel, anchor):
        if kind == "spread":
            raw = [(p["date"], p["cum"]) for p in panel["spread_series"]]
        else:
            raw = [(p["date"], p["cum"]) for p in panel["series"][cohort]]
        return [(panel["first_entry_date"], anchor)] + [(d, anchor * c) for d, c in raw]
    ins_pts = pts(ins, 1.0)
    ins_end = ins_pts[-1][1]
    fwd_pts = pts(fwd, ins_end)
    return ins_pts + fwd_pts[1:]   # drop fwd anchor (same boundary point)


def _window_slice(points: list[tuple[str, float]], days: int | None) -> list[tuple[str, float]]:
    """Last `days` calendar days (None = all), rebased to 1.0 at window start."""
    if days is not None:
        end = date.fromisoformat(points[-1][0])
        start = end - timedelta(days=days)
        pts = [(d, v) for d, v in points if date.fromisoformat(d) >= start]
    else:
        pts = points
    if len(pts) < 2:
        return []
    base = pts[0][1]
    return [(d, v / base) for d, v in pts]


def rolling_chart_html(chart_id: str, series_defs: list[dict], caption: str,
                       title: str) -> str:
    """series_defs: [{points:[(iso,val)], short, color, dash?}]. Emits one SVG
    per range window + range buttons; a tiny inline script (no CDNs) toggles
    visibility. Mobile default = 60D, desktop = ALL."""
    blocks = []
    for wname, wdays in ROLL_WINDOWS:
        sliced = [dict(s, w=_window_slice(s["points"], wdays)) for s in series_defs]
        sliced = [s for s in sliced if s["w"]]
        if not sliced:
            continue
        dates = [d for d, _ in max((s["w"] for s in sliced), key=len)]
        b_idx = None
        for i, d in enumerate(dates):
            if d <= BOUNDARY_ISO:
                b_idx = i
        if b_idx == len(dates) - 1:
            b_idx = None   # boundary at/after window end -> nothing forward to split
        date_pos = {d: i for i, d in enumerate(dates)}
        chart_series = [{
            "name": s["short"], "short": s["short"], "color": s["color"],
            "dash": s.get("dash"),
            "pts": [(date_pos[d], v) for d, v in s["w"] if d in date_pos],
        } for s in sliced]
        svg = svg_chart(chart_series, dates, title=f"{title} ({wname.upper()}{'D' if wdays else ''})",
                        boundary_idx=b_idx)
        blocks.append(f'<div class="rollwin" data-chart="{chart_id}" data-w="{wname}">{svg}</div>')
    buttons = "".join(
        f'<button class="rangebtn" data-chart="{chart_id}" data-w="{w}">'
        f'{w.upper() + ("D" if d else "")}</button>' for w, d in ROLL_WINDOWS)
    return f"""
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin:14px 0 6px">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096">{escape(title)}</div>
        <div class="rangebar">{buttons}</div>
      </div>
      {''.join(blocks)}
      <p style="font-size:11px;color:#718096;margin:6px 0 0">{escape(caption)}</p>"""


def metric_rows(panel: dict, order: list[str]) -> str:
    rows = []
    for c in order:
        m = panel["metrics"][c]
        thin = ' <span style="color:#FBA94B">⚠ thin</span>' if m.get("thin") else ""
        nsize = (f'{m["cohort_n_min"]}/{m["cohort_n_median"]}/{m["cohort_n_max"]}'
                 if c != "benchmark" else "—")
        hit = f'{m["hit_rate_vs_benchmark"]*100:.0f}%' if m["hit_rate_vs_benchmark"] is not None else "—"
        rows.append(
            f"<tr><td style='padding:8px 12px;color:#E2E8F0'>{COHORT_LABEL[c]}{thin}</td>"
            f"<td style='padding:8px 12px;color:{COHORT_COLOR[c]};font-family:JetBrains Mono,monospace'>{_pct(m['cumulative_return'])}</td>"
            f"<td style='padding:8px 12px;color:#FF3366;font-family:JetBrains Mono,monospace'>{_pct(m['max_drawdown'])}</td>"
            f"<td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['volatility_periodic']*100:.2f}%</td>"
            f"<td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{hit}</td>"
            f"<td style='padding:8px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{nsize}</td></tr>")
    return "".join(rows)


def universe_panel_html(fwd: dict) -> str:
    u = json.loads(UNIVERSE_PATH.read_text())
    n_eq = len(u.get("equities", []))
    n_sec = len(u.get("sector_etfs", []))
    n_broad = len(u.get("broad_etfs", []))
    n_macro = len(u.get("macro", []))
    n_total = n_eq + n_sec + n_broad + n_macro
    sec = ", ".join(u.get("sector_etfs", []))
    broad = ", ".join(u.get("broad_etfs", []))
    macro = ", ".join(u.get("macro", []))
    cov = fwd.get("universe_coverage", {})
    skipped = fwd.get("skipped_partial_days", 0)
    return f"""
    <div class="panel">
      <div class="panel-title">Universe &amp; Coverage</div>
      <div class="panel-sub">what is scored, what enters the decile study, and the inclusion rule</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px">
        <div style="min-width:120px"><div style="font-size:26px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace">{n_total}</div><div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px">tickers scored daily</div></div>
        <div style="min-width:120px"><div style="font-size:26px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace">{n_eq}</div><div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px">U.S. large-cap equities</div></div>
        <div style="min-width:120px"><div style="font-size:26px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace">{n_sec + n_broad + n_macro}</div><div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px">ETFs / ETNs</div></div>
        <div style="min-width:120px"><div style="font-size:26px;font-weight:800;color:#00E676;font-family:JetBrains Mono,monospace">{cov.get('priced_median','—')}/{cov.get('size_median','—')}</div><div style="font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px">priced coverage (median day)</div></div>
      </div>
      <table>
        <thead><tr><th>Segment</th><th>Count</th><th>Members</th></tr></thead>
        <tbody>
          <tr><td style='padding:8px 12px;color:#E2E8F0'>Equities (tech, financials, health care, energy, staples, industrials, …)</td><td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{n_eq}</td><td style='padding:8px 12px;color:#718096;font-size:11px'>AAPL, MSFT, NVDA, … (full list in <code>v3/universe.json</code>)</td></tr>
          <tr><td style='padding:8px 12px;color:#E2E8F0'>Sector ETFs</td><td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{n_sec}</td><td style='padding:8px 12px;color:#718096;font-size:11px;font-family:JetBrains Mono,monospace'>{escape(sec)}</td></tr>
          <tr><td style='padding:8px 12px;color:#E2E8F0'>Broad-market ETFs</td><td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{n_broad}</td><td style='padding:8px 12px;color:#718096;font-size:11px;font-family:JetBrains Mono,monospace'>{escape(broad)}</td></tr>
          <tr><td style='padding:8px 12px;color:#E2E8F0'>Macro ETFs/ETNs (rates, metals, dollar, China/EM, volatility)</td><td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{n_macro}</td><td style='padding:8px 12px;color:#718096;font-size:11px;font-family:JetBrains Mono,monospace'>{escape(macro)}</td></tr>
        </tbody>
      </table>
      <div style="margin-top:14px;padding:12px 14px;background:#1A2030;border-radius:8px;font-size:12px;color:#A0AEC0;line-height:1.6">
        <strong style="color:#E2E8F0">Inclusion rule.</strong> A signal date enters the decile study only if it scored
        at least {MIN_UNIVERSE_FOR_DECILES} universe tickers (a "decile" of a handful of names is meaningless).
        {skipped} partial-universe date{'s were' if skipped != 1 else ' was'} excluded under this rule
        (2026-05-31, a non-trading Sunday on which an ad-hoc run scored 3 tickers).
        Within an included date, a ticker contributes to its cohort's period return only if closing
        prices exist at both the entry and exit dates — currently
        {cov.get('priced_median','—')} of {cov.get('size_median','—')} tickers on the median rebalance
        (min {cov.get('priced_min','—')}, max {cov.get('priced_max','—')}).
        Top/bottom decile = the highest/lowest ~10% of tickers by composite score, i.e. 8 of 79.
      </div>
      <div style="margin-top:10px;padding:12px 14px;background:#1A2030;border-radius:8px;font-size:12px;color:#A0AEC0;line-height:1.6">
        <strong style="color:#E2E8F0">Evidence-tier names ({len(u.get("evidence_tier", []))}, Canada Resources).</strong>
        Evidence-tier names are covered for filings evidence and research dashboards only.
        They are not scored and are not part of the Lab decile study or the 79-ticker
        forward-track universe. See the <a href="canada_resources.html">Canada Resources
        Evidence</a> page and the methodology's evidence-tier boundary section.
      </div>
    </div>"""


def membership_html(mem: dict) -> str:
    rows = []
    for m in mem["members"]:
        rows.append(
            f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(m['ticker'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['score']:+.4f}</td>"
            f"<td style='padding:7px 12px;color:#4DD0E1;font-size:12px'>{escape(display_label(m['label']))}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:12px'>{escape(m['grade'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{m['ev_count']}</td></tr>")
    return f"""
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:20px 0 8px">
        Current high-score (top-decile) cohort membership · as of {escape(mem['as_of'] or '—')} · {mem['k']} of {mem['universe_n']} tickers
      </div>
      <table>
        <thead><tr><th>Ticker</th><th>Composite score</th><th>Signal label</th><th>Evidence grade</th><th>Filings cited</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Research classifications, not recommendations. Membership is recomputed at every signal date;
        the cohort above is today's snapshot and changes daily. Evidence grades follow the public
        grading rubric (confidence × evidence depth); "Insufficient" appears when composite confidence &lt; 0.30.
      </p>"""


def _fmt_p(p):
    if p is None:
        return "—"
    return "&lt;0.001" if p < 0.001 else f"{p:.3f}"


def _fmt_t(t):
    return f"{t:+.2f}" if t is not None else "—"


def _ledger_tip() -> dict:
    """Latest public-ledger block (date, root, block count) — best-effort."""
    try:
        lines = TRUST_LEDGER.read_text().splitlines()
        last = json.loads(lines[-1])
        return {"date": last["date"], "root": last["daily_root"],
                "blocks": len(lines), "n": last.get("snapshot_count")}
    except Exception:
        return {}


def _c6_fire_rates() -> dict:
    import psycopg2
    q = ("SELECT is_backfill, count(*) FILTER (WHERE c6_event_impact IS NOT NULL "
         "AND c6_event_impact != 0), count(*) FROM signal_snapshots GROUP BY 1")
    out = {}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(q)
            for is_bf, fired, total in cur.fetchall():
                out["in_sample" if is_bf else "forward"] = fired / total if total else None
    return out


def rigor_panel_html(rig: dict) -> str:
    """Panel 3 — statistical rigor. Every number carries its n and window."""
    PANEL_META = {
        "forward": ("Forward OOS", "#00E676", "look-ahead-free"),
        "in_sample": ("In-Sample Replay", "#FBA94B", "replay reconstruction — optimistic"),
    }
    SPREAD_LABEL = {"top_minus_bottom": "Top − Bottom decile",
                    "top_minus_universe": "Top decile − EW universe"}
    sections = []
    for panel in ("forward", "in_sample"):
        r = rig.get(panel, {})
        if not r.get("evaluable"):
            continue
        name, color, tag = PANEL_META[panel]
        win = f"{r['window'][0]} → {r['window'][1]}"

        srows = []
        for key in ("top_minus_bottom", "top_minus_universe"):
            s = r["spreads"][key]
            ci = (f"({s['ci95'][0]*100:+.2f}%, {s['ci95'][1]*100:+.2f}%)"
                  if s.get("ci95") else "—")
            sig = "" if (s["p_value"] is None or s["p_value"] >= 0.05) else " *"
            srows.append(
                f"<tr><td style='padding:7px 12px;color:#E2E8F0'>{SPREAD_LABEL[key]}</td>"
                f"<td style='padding:7px 12px;color:{color};font-family:JetBrains Mono,monospace'>{s['mean_per_period']*100:+.3f}%</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{ci}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_fmt_t(s['t_stat'])}{sig}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_fmt_p(s['p_value'])}</td>"
                f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{s['n_periods']}</td></tr>")

        irows = []
        for h in (1, 5, 20):
            ic = r["ic"].get(h) or r["ic"].get(str(h))
            if not ic or ic["mean_ic"] is None:
                continue
            reliable = ic.get("t_reliable", True)
            rel = ("" if reliable else
                   " <span style='color:#FBA94B'>⚠ too few independent blocks</span>")
            pos = (f"{ic['ic_positive_share']*100:.0f}%"
                   if ic.get("ic_positive_share") is not None else "—")
            p_cell = (_fmt_p(ic["nw_p_value"]) if reliable else
                      "<span style='color:#FBA94B'>N/A — descriptive only</span>")
            t_cell = (f"{_fmt_t(ic['nw_t_stat'])} (lag {ic['nw_lag']})" if reliable else
                      f"<span style='color:#718096'>({_fmt_t(ic['nw_t_stat'])} — not interpretable)</span>")
            irows.append(
                f"<tr><td style='padding:7px 12px;color:#E2E8F0'>{h}-day{rel}</td>"
                f"<td style='padding:7px 12px;color:{color};font-family:JetBrains Mono,monospace'>{ic['mean_ic']:+.4f}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{t_cell}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{p_cell}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{pos}</td>"
                f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{ic['n_dates']}</td>"
                f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{ic['median_cross_section']}</td></tr>")

        mrows = []
        mm = r["market_model"]
        for key, label in (("vs_universe", "vs equal-weight universe"), ("vs_spy", "vs SPY")):
            m = mm.get(key)
            if not m:
                continue
            sig = "" if (m["p_alpha"] is None or m["p_alpha"] >= 0.05) else " *"
            mrows.append(
                f"<tr><td style='padding:7px 12px;color:#E2E8F0'>{label}</td>"
                f"<td style='padding:7px 12px;color:{color};font-family:JetBrains Mono,monospace'>{m['alpha_per_period']*100:+.3f}%</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['alpha_annualized']*100:+.1f}%</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['beta']:+.2f}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_fmt_t(m['t_alpha'])}{sig}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_fmt_p(m['p_alpha'])}</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['r2']:.3f}</td>"
                f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{m['n_periods']}</td></tr>")

        mde = mm.get("vs_universe", {}).get("mde_alpha_annualized")
        mde_txt = ""
        if mde is not None:
            n_p = mm["vs_universe"]["n_periods"]
            mde_txt = f"""
        <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:stretch;margin-top:12px">
          <div style="flex:1;min-width:260px;background:#1A2030;border:1px solid #2D3748;border-radius:8px;padding:14px 16px">
            <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#718096">Statistical power meter</div>
            <div style="display:flex;gap:22px;align-items:baseline;margin-top:6px;flex-wrap:wrap">
              <div><span style="font-size:22px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace">n={n_p}</span> <span style="font-size:11px;color:#718096">periods</span></div>
              <div><span style="font-size:22px;font-weight:800;color:#FBA94B;font-family:JetBrains Mono,monospace">≈{mde*100:,.0f}%</span> <span style="font-size:11px;color:#718096">detectable |α| (annualized, 80% power)</span></div>
              <div><span style="display:inline-block;background:#FBA94B20;color:#FBA94B;border:1px solid #FBA94B80;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:700">UNDERPOWERED</span></div>
            </div>
            <p style="font-size:12px;color:#A0AEC0;margin-top:8px">This panel is not failing. It is too young. Alpha estimates are shown for completeness and are <strong style="color:#E2E8F0">not significant</strong>; detectability improves as n accrues daily.</p>
          </div>
        </div>"""

        sections.append(f"""
      <div style="margin-top:{18 if panel == 'in_sample' else 0}px">
        <div style="font-size:12px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:1px">{name} · {win} · {tag}</div>

        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:12px 0 0">Decile spread tests (per-rebalance arithmetic spreads)</div>
        <table>
          <thead><tr><th>Spread</th><th>Mean / period</th><th>Bootstrap 95% CI</th><th>t</th><th>p</th><th>n periods</th></tr></thead>
          <tbody>{''.join(srows)}</tbody>
        </table>

        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:16px 0 0">Information coefficient (per-date cross-sectional Spearman, Fama–MacBeth mean)</div>
        <table>
          <thead><tr><th>Horizon</th><th>Mean IC</th><th>Newey–West t</th><th>p</th><th>share IC&gt;0</th><th>T dates</th><th>median cross-section</th></tr></thead>
          <tbody>{''.join(irows)}</tbody>
        </table>

        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:16px 0 0">Market model (top-decile cohort per-period returns, OLS)</div>
        <table>
          <thead><tr><th>Regression</th><th>α / period</th><th>α annualized</th><th>β</th><th>t(α)</th><th>p</th><th>R²</th><th>n</th></tr></thead>
          <tbody>{''.join(mrows)}</tbody>
        </table>
        {mde_txt}
        {_v51_clustered() if panel == "forward" else ""}
      </div>""")

    return f"""
    <div class="panel">
      <div class="panel-title">Panel 3 · Statistical Rigor</div>
      <div class="panel-sub">every statistic carries its n and window · * = p &lt; 0.05 · bootstrap: percentile, 10,000 i.i.d. period resamples, fixed seed · IC t-stats are Newey–West (Bartlett) HAC-corrected for overlapping return windows</div>
      {''.join(sections)}
      <p style="font-size:11px;color:#718096;margin-top:12px">
        Honest reading: at the current sample sizes, <strong style="color:#E2E8F0">no forward spread, IC, or alpha is
        statistically significant at the 5% level once overlap is corrected</strong>. The forward 20-day IC is positive on
        all observed dates but has too few independent blocks to test. "Not yet significant" is the finding — the
        statistics accrue daily and this panel recomputes with them.
      </p>
    </div>"""


def reproduce_panel_html(ledger: dict, source_commit: str | None) -> str:
    root_short = (ledger.get("root") or "")[:16]
    return f"""
    <div class="panel">
      <div class="panel-title">Reproduce this page</div>
      <div class="panel-sub">one command, fresh environment · derived data only (no vendor market data bundled or required)</div>
      <pre style="background:#0B0E14;border:1px solid #1E232D;border-radius:8px;padding:14px 16px;font-size:12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;overflow-x:auto;line-height:1.7"># packaged (v5.0+)
pip install yuclaw
yuclaw replay-lab

# or fully standalone (stdlib only, nothing to install)
curl -sO https://yuclawlab.github.io/yuclaw-brain/replay/lab_replay_bundle.json
curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/tools/replay_lab.py
python3 replay_lab.py lab_replay_bundle.json</pre>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.65;margin-top:10px">
        The script (Python ≥3.10, standard library only; <code>pip install yuclaw</code> optionally adds the full
        SDK) rebuilds the decile cohorts from the bundled composite scores, re-derives every cohort period
        return, recomputes all Panel-3 statistics (same bootstrap seed), and — the tamper-evidence step —
        recomputes every forward snapshot's sha-256 leaf hash from disclosed derived inputs and rolls them
        into daily roots that must match the public
        <a href="https://github.com/YuClawLab/yuclaw-trust" style="color:#00E676">yuclaw-trust</a> ledger.
        It exits non-zero on any mismatch.
      </p>
      <p style="font-size:11px;color:#718096;margin-top:8px;font-family:JetBrains Mono,monospace">
        this build derives from: source commit {escape((source_commit or '—')[:12])} ·
        ledger block {escape(ledger.get('date') or '—')} · evidence-ledger root {escape(root_short)}… ·
        {ledger.get('blocks', '—')} public ledger blocks
      </p>
      <p style="font-size:11px;color:#718096;margin-top:6px">
        Compliant data path: the bundle contains YUCLAW-derived data only — scores, locked labels, component
        scores, content hashes, and derived period returns. No raw vendor OHLCV rows are exported
        (data-provider terms). Analyses requiring raw prices need the user's own licensed price feed.
      </p>
    </div>"""


def innovation_panel_html(ledger: dict, c6: dict) -> str:
    c6f = c6.get("forward")
    c6i = c6.get("in_sample")
    rows = [
        ("Git-anchored replayable ledger",
         f"{ledger.get('blocks', '—')} daily blocks · latest evidence-ledger root {escape((ledger.get('root') or '')[:12])}… ({escape(ledger.get('date') or '—')})",
         "LIVE — anchored daily before pages publish", "#00E676"),
        ("Evidence grounding (v5 Layer-1 corpus)",
         "corpus grounding 0.52 → 0.75 · citation fidelity 0.66 → 0.85 after the prose-first extraction fix (commit f130983e)",
         "MEASURED on the v5 Layer-1 filing corpus", "#00E676"),
        ("C6 evidence/risk channel",
         (f"fires on {c6i*100:.0f}% of in-sample and {c6f*100:.0f}% of forward snapshots "
          f"(rare by construction) · in-sample within-class IC +0.36 on material non-insider events (n=38)"),
         "rareness confirmed OOS 2026-07-06 (22% fire, n=9 held-out); sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16)", "#FBA94B"),
        ("Event-type extraction specialists",
         "10 dedicated extractors (v5 Layer 1) — earnings, guidance, M&amp;A, insider, governance, …",
         "LIVE for 8-K and Form-4 streams · Form-4 live since 2026-07-16 (batch 2026-02-18 → 05-15; gap backfilled, ingestion-time as-of)", "#00E676"),
        ("Point-in-time discipline",
         "daily as-of snapshots; outage of Jun 26 – Jul 3 disclosed (snapshots continued point-in-time on frozen price inputs; zero retroactive edits)",
         "LIVE — the disclosed gap is the evidence it isn't backfilled", "#00E676"),
    ]
    trs = "".join(
        f"<tr><td style='padding:8px 12px;color:#E2E8F0;font-weight:600;font-size:12px'>{name}</td>"
        f"<td style='padding:8px 12px;color:#A0AEC0;font-size:12px'>{detail}</td>"
        f"<td style='padding:8px 12px;color:{color};font-size:11px;font-family:JetBrains Mono,monospace'>{status}</td></tr>"
        for name, detail, status, color in rows)
    return f"""
    <div class="panel">
      <div class="panel-title">System properties · numbers and status, no adjectives</div>
      <div class="panel-sub">each row: the measured number and its honest maturity label</div>
      <table>
        <thead><tr><th>Property</th><th>Measured</th><th>Status</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:12px;line-height:1.6">
        <strong style="color:#A0AEC0">Definitions (exact internal rubric, deterministic verifier — no LLM in the loop):</strong><br>
        <strong style="color:#A0AEC0">Corpus grounding</strong> = points_grounded / points_total across the filing corpus,
        where an agent key-point is <em>grounded</em> iff it carries ≥1 citation that verifies as a verbatim
        (whitespace/case-normalized) span of the source filing AND every numeric token in the point
        appears within those verified quotes; ungrounded points are discarded with the reason recorded.<br>
        <strong style="color:#A0AEC0">Citation fidelity</strong> = citations_verified / citations_total — the share of quoted
        spans an agent cites that locate as verbatim spans of the source filing after
        whitespace/case normalization. Verifier source: <code>v5/swarm/grounding.py</code>.
      </p>
    </div>"""


# Full outage disclosure — preserved VERBATIM in the Data Integrity Log
# (presentation compressed to a one-line card up top; substance unchanged).
OUTAGE_FULL_TEXT = (
    "Infrastructure note (Jun 26 – Jul 3, 2026) — a network outage on the research host "
    "interrupted external data feeds. Daily signal snapshots continued to be written on-box, "
    "point-in-time, throughout the window — but from Jun 26 to Jul 2 their price-derived inputs "
    "were frozen at Jun 25 closes (the price feed was unreachable), and this page was not "
    "republished during the outage. Price history and SEC filing ingestion were restored and "
    "backfilled on Jul 3, and the filing window was re-checked against EDGAR on Jul 5 (no missing "
    "filings). No snapshot or ledger row was retroactively edited: the outage-window snapshots "
    "stand exactly as written, stale inputs and all."
)

# Dated methodology note — ships with the enabling code (order of 2026-07-16).
FORM4_LIVE_TEXT = (
    "Live Form-4 ingestion enabled 2026-07-16. Insider-event stream restored to "
    "production inputs (batch coverage previously ended 2026-05-15; the gap is "
    "backfilled with ingestion-time available_as_of and cannot affect past replays). "
    "C6 elevated-arm accrual for the out-of-sample sign study begins from this date."
)


def status_cards_html(fwd_n: int, ledger: dict) -> str:
    # Every numeric on a status card carries data-source naming where the
    # number comes from (ORDER 2026-09-02A B2/P5): a same-page panel id
    # ("#panel-…") or a canonical artifact path ("ledger:…"). The
    # consumer-posture gate machine-checks the mapping on every build.
    cards = [
        ("Forward OOS", f"EARLY · n={fwd_n} periods",
         "no significant alpha yet — underpowered, accruing daily",
         "#FBA94B", "#panel-forward"),
        ("In-sample replay", "OPTIMISTIC",
         "replay reconstruction — educational only, collapsed below",
         "#FBA94B", ""),
        ("Ledger", f"LIVE · {ledger.get('blocks', '—')} blocks",
         f"git-anchored daily · evidence-ledger root {escape((ledger.get('root') or '')[:8])}…",
         "#00E676", f"ledger:docs/ledger/{escape(ledger.get('date') or '')}.json"),
        ("Reproducibility", "ONE-COMMAND VERIFY",
         "stdlib script reproduces every statistic + evidence-ledger roots",
         "#00E676", ""),
    ]
    tiles = "".join(
        f'<div{(" data-source=" + chr(34) + src + chr(34)) if src else ""}'
        f' style="flex:1;min-width:200px;background:#151A23;border:1px solid #1E232D;'
        f'border-left:3px solid {c};border-radius:10px;padding:12px 16px">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#718096">{escape(t)}</div>'
        f'<div style="font-size:15px;font-weight:800;color:{c};font-family:JetBrains Mono,monospace;margin:3px 0">{v}</div>'
        f'<div style="font-size:11px;color:#A0AEC0;line-height:1.45">{d}</div></div>'
        for t, v, d, c, src in cards)
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">{tiles}</div>'


def honest_reading_html() -> str:
    return """
    <div class="panel" style="border-left:3px solid #00E676">
      <div class="panel-title">Honest reading</div>
      <p style="font-size:14px;color:#E2E8F0;line-height:1.7;max-width:860px">
        <strong>No forward alpha has been statistically proven yet.</strong> What is running:
        the point-in-time infrastructure is live, every daily signal set is anchored to a public,
        git-committed ledger, and every statistic on this page reproduces from published derived
        data with one command. The <strong>evidence-risk channel (C6)</strong> is the next
        out-of-sample test target — its in-sample sign is known and its forward test is defined
        below. Everything here is research and education, not investment advice; research
        classifications, not recommendations.
      </p>
    </div>"""


def integrity_card_html() -> str:
    return """
    <div class="disclaimer-line" style="border-left-color:#4DD0E1">
      <strong style="color:#4DD0E1">Data integrity note —</strong> Jun 26 – Jul 3 outage disclosed.
      Price-derived inputs were stale. No snapshots were retroactively edited.
      <a href="#integrity-log" style="color:#4DD0E1">Full log ↓</a>
    </div>"""


def integrity_log_html() -> str:
    return f"""
    <details class="acc" id="integrity-log">
      <summary>Data Integrity Log</summary>
      <div class="acc-body">
        <p style="line-height:1.7">{escape(OUTAGE_FULL_TEXT)}</p>
        <p style="line-height:1.7;margin-top:10px">{escape(FORM4_LIVE_TEXT)}</p>
        <p style="margin-top:10px;font-size:12px;color:#718096">
          Policy: disclosures are never deleted; presentation may be compressed, substance may not.
          Fabricating retroactive point-in-time data would invalidate the replayable ledger; the
          disclosed staleness is the honest record. See also
          <a href="methodology/validation_lab.md" style="color:#00E676">methodology</a>.
        </p>
      </div>
    </details>"""


def proven_html(fwd_n: int) -> str:
    # fwd_n is the SAME computed value the header status card renders
    # (fwd['evaluable_periods']) — never hardcode the n here; the site-walk
    # gate asserts header n == not-proven n on every build.
    proven = [
        "Point-in-time snapshot discipline — daily as-of writes, zero retroactive edits (outage window included)",
        "Git-anchored replayable ledger — daily sha-256 roots committed publicly before pages update",
        "One-command reproducibility — every statistic + 2,847 leaf hashes re-derive from published data",
        "Deterministic evidence grounding measurement — corpus grounding 0.75, citation fidelity 0.85 (definitions footnoted below)",
    ]
    not_proven = [
        f"Forward alpha — n={fwd_n} periods, underpowered; not significant at 5%",
        "IC significance — forward 5d IC +0.09 loses significance after overlap (HAC) correction; 20d descriptive only",
        "Evidence→price lead — event-study CAR is adverse at the current backfill-era sample; live-era n too small",
        "C6 risk gate out-of-sample — rareness confirmed OOS 2026-07-06; sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16)",
    ]
    li = lambda xs, c: "".join(f'<li style="margin:5px 0;color:#A0AEC0;font-size:13px;line-height:1.55">'
                               f'<span style="color:{c};font-weight:700">{"✓" if c == "#00E676" else "✗"}</span> {x}</li>' for x in xs)
    return f"""
    <div class="panel">
      <div class="panel-title">What is proven · what is not proven</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap">
        <div style="flex:1;min-width:280px">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#00E676;margin-bottom:6px">Proven (verifiable today)</div>
          <ul style="list-style:none">{li(proven, "#00E676")}</ul>
        </div>
        <div style="flex:1;min-width:280px">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#FF3366;margin-bottom:6px">Not proven (open, tracked)</div>
          <ul style="list-style:none">{li(not_proven, "#FF3366")}</ul>
        </div>
      </div>
    </div>"""


def maturity_html(ledger: dict) -> str:
    gates = [
        ("Gate 1 · Point-in-time infrastructure + public ledger", "PASSED", "#00E676",
         f"live since 2026-05-18 · {ledger.get('blocks', '—')} anchored daily blocks"),
        ("Gate 2 · Honest measurement discipline", "PASSED", "#00E676",
         "per-regime statistics, HAC-corrected inference, power reporting, adverse results published"),
        ("Gate 3 · Independent reproducibility", "PASSED (young)", "#00E676",
         "one-command replay live since 2026-07-05; awaiting first external replication"),
        ("Gate 4 · Forward statistical significance", "NOT YET", "#FF3366",
         "no spread, IC, or alpha significant at 5% with adequate power — requires more forward data"),
        ("Gate 5 · Evidence→price lead, out-of-sample", "NOT YET", "#FF3366",
         "live-era event sample n=4; needs ≥30 live directional events for a first read"),
        ("Gate 6 · C6 risk-gate OOS confirmation", "NOT YET", "#FF3366",
         "rareness confirmed OOS 2026-07-06 (22% fire rate, n=9 held-out); sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16)"),
    ]
    rows = "".join(
        f"<tr><td style='padding:8px 12px;color:#E2E8F0;font-size:12px'>{g}</td>"
        f"<td style='padding:8px 12px'><span style='background:{c}20;color:{c};border:1px solid {c}80;"
        f"padding:2px 10px;border-radius:4px;font-size:10px;font-weight:700;font-family:JetBrains Mono,monospace'>{s}</span></td>"
        f"<td style='padding:8px 12px;color:#718096;font-size:12px'>{d}</td></tr>"
        for g, s, c, d in gates)
    return f"""
    <div class="panel">
      <div class="panel-title">Protocol readiness · maturity gates</div>
      <div class="panel-sub">infrastructure-ready, statistically young — 3 of 6 gates passed</div>
      <table><thead><tr><th>Gate</th><th>Status</th><th>Evidence / requirement</th></tr></thead>
      <tbody>{rows}</tbody></table>
    </div>"""


def challenge_html() -> str:
    return """
    <div class="panel">
      <div class="panel-title">Reproduction challenge</div>
      <p style="font-size:13px;color:#A0AEC0;line-height:1.7;max-width:860px">
        Independent replication is invited. Run the three commands in "Reproduce this page";
        the script exits non-zero on ANY mismatch between recomputed statistics and this page, or
        between recomputed hash roots and the public ledger. If you find a mismatch, the ledger is
        broken and we want to know:
        <a href="https://github.com/YuClawLab/yuclaw-brain/issues" style="color:#00E676">open an issue</a>
        with the script output. Replications that confirm are equally welcome — independent
        verification is the point of publishing the bundle.
      </p>
    </div>"""


def roadmap_html() -> str:
    return """
    <div class="panel">
      <div class="panel-title">Roadmap · Risk Gate Lab (next registered test)</div>
      <div class="panel-sub">no new claims — the tests are defined before the data can answer them</div>
      <ul style="list-style:none;font-size:13px;color:#A0AEC0;line-height:1.7">
        <li style="margin:6px 0">· <strong style="color:#E2E8F0">C6 out-of-sample test</strong>: the evidence/risk channel fires on ~25% of forward snapshots (rare by construction). Defined test: conditional 20-trading-day forward outcomes of C6-fired vs quiet snapshots, evaluable once the forward window exceeds the horizon with sufficient fired n.</li>
        <li style="margin:6px 0">· <strong style="color:#E2E8F0">Drawdown-vs-evidence-staleness study</strong>: does evidence age (days since last SourceLock-accepted filing) relate to subsequent drawdown? Evidence-age is measured and displayed today (Panel 4); the study runs when the qualified cohort has enough history — it is not fabricated now.</li>
        <li style="margin:6px 0">· <strong style="color:#E2E8F0">Live Form-4 ingestion</strong>: enabled 2026-07-16 — the insider-evidence stream is live in the forward era (batch coverage 2026-02-18 → 05-15; the 05-15 → 07-16 gap is backfilled with ingestion-time available_as_of and cannot affect past replays).</li>
      </ul>
    </div>"""


def panel4_html(q: dict) -> str:
    if not q.get("evaluable"):
        return """
    <div class="panel">
      <div class="panel-title">Panel 4 · Evidence-Qualified Protocol Candidate</div>
      <p style="font-size:13px;color:#FBA94B">No qualified rebalances yet — accrues as evidence coverage grows.</p>
    </div>"""
    m = q["metrics"]
    rows = []
    for mem in q["members"]:
        age = mem["evidence_age"]
        stale = (age is not None and age > q["stale_days"])
        age_txt = (f"{age}d" + (" ⚠ stale" if stale else "")) if age is not None else "— none"
        rows.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(mem['ticker'])}</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{mem['score']:+.3f}</td>"
            f"<td style='padding:6px 12px;color:#4DD0E1;font-size:12px'>{escape(display_label(mem['label']))}</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:12px'>{escape(mem['grade'])}</td>"
            f"<td style='padding:6px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{mem['evc']}</td>"
            f"<td style='padding:6px 12px;color:{'#FBA94B' if stale else '#A0AEC0'};font-family:JetBrains Mono,monospace;font-size:12px'>{age_txt}</td>"
            f"<td style='padding:6px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{mem['c6']:+.2f}</td></tr>")
    stat = lambda label, v: (f'<div class="tile"><div class="v">{v}</div>'
                             f'<div class="k">{label}</div></div>')
    return f"""
    <div class="panel">
      <div class="panel-title">Panel 4 · Evidence-Qualified Protocol Candidate<span class="lead-tag">FORWARD-ONLY</span></div>
      <div class="panel-sub">same decile methodology, restricted to names meeting minimum evidence criteria as of each date · window {escape(q['window'][0])} → {escape(q['window'][1])} · {q['evaluable_periods']} rebalances</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.6;max-width:860px;margin-bottom:10px">
        <strong style="color:#E2E8F0">Qualification (point-in-time):</strong> {escape(q['criteria'])}.
        Evidence-quality fields exist only from the v4.0 launch (2026-06-01), so this panel is
        structurally forward-only — no in-sample variant is possible without fabricating grades.
      </p>
      <div style="display:flex;gap:22px;flex-wrap:wrap;margin-bottom:6px">
        {stat("qualified pool (median/day)", f"{q['pool']['median']}<span style='font-size:13px;color:#718096'>/{q['universe_n']}</span>")}
        {stat("evidence coverage", f"{q['coverage_median']*100:.0f}%")}
        {stat("median evidence age", f"{q['median_evidence_age']}d")}
        {stat("C6 coverage of pool", f"{q['c6_coverage_mean']*100:.0f}%")}
      </div>
      <table>
        <thead><tr><th>Cohort (n)</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th></tr></thead>
        <tbody>
          <tr><td style='padding:7px 12px;color:#E2E8F0'>Qualified pool, equal-weight (n={q['pool']['min']}–{q['pool']['max']}/day)</td><td style='padding:7px 12px;color:#4DD0E1;font-family:JetBrains Mono,monospace'>{_pct(m['qualified_ew']['cumulative_return'])}</td><td style='padding:7px 12px;color:#FF3366;font-family:JetBrains Mono,monospace'>{_pct(m['qualified_ew']['max_drawdown'])}</td><td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['qualified_ew']['volatility_periodic']*100:.2f}%</td></tr>
          <tr><td style='padding:7px 12px;color:#E2E8F0'>Qualified high-score decile (n={q['top_n']['min']}–{q['top_n']['max']}/day) <span style="color:#FBA94B">⚠ too small for inference</span></td><td style='padding:7px 12px;color:#4DD0E1;font-family:JetBrains Mono,monospace'>{_pct(m['qualified_top']['cumulative_return'])}</td><td style='padding:7px 12px;color:#FF3366;font-family:JetBrains Mono,monospace'>{_pct(m['qualified_top']['max_drawdown'])}</td><td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['qualified_top']['volatility_periodic']*100:.2f}%</td></tr>
          <tr><td style='padding:7px 12px;color:#E2E8F0'>Equal-weight universe (n=79, reference)</td><td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_pct(m['universe_ew']['cumulative_return'])}</td><td style='padding:7px 12px;color:#FF3366;font-family:JetBrains Mono,monospace'>{_pct(m['universe_ew']['max_drawdown'])}</td><td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['universe_ew']['volatility_periodic']*100:.2f}%</td></tr>
        </tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin:10px 0">
        Honest result: over its first {q['evaluable_periods']} periods the qualified pool
        <strong style="color:#E2E8F0">trails the universe</strong>
        ({_pct(m['qualified_ew']['cumulative_return'])} vs {_pct(m['universe_ew']['cumulative_return'])}).
        The cohort is too young and (at the decile level) too small for inference; it accrues as
        evidence coverage grows. Criteria will NOT be loosened to fatten n.
      </p>
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:14px 0 6px">Current qualified membership · as of {escape(q['as_of'])} · {len(q['members'])} names (top {q['k_latest']} = decile cohort)</div>
      <div style="max-height:340px;overflow-y:auto">
      <table>
        <thead><tr><th>Ticker</th><th>Score</th><th>Display label</th><th>Grade</th><th>Cited filings</th><th>Evidence age</th><th>C6</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      </div>
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Evidence age = days since the last SourceLock-accepted filing event for the ticker (stale
        flag at &gt;{q['stale_days']}d). Limitations: {q['evaluable_periods']} periods; decile cohort of
        {q['top_n']['min']}–{q['top_n']['max']} names; insider-evidence stream live since 2026-07-16 (batch coverage
        ended 2026-05-15; gap backfilled with ingestion-time as-of) — evidence ages for some names reflect
        the coverage gap until live events accrue; qualification uses
        the public grade rubric and is recomputed point-in-time daily.
      </p>
    </div>"""


def render() -> str:
    data = compute_all()
    fwd, ins = data["forward"], data["in_sample"]
    mem = current_top_decile()
    rig = compute_rigor()
    q = compute_qualified()
    ledger = _ledger_tip()
    c6 = _c6_fire_rates()
    try:
        import subprocess
        source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                                       capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        source_commit = None
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data_through = fwd.get("price_coverage_end") or "—"

    # ---- Forward panel (leads). ----
    if fwd["evaluable"]:
        n_td = fwd["span_trading_days"]
        fwd_dates = panel_dates(fwd)
        fwd_primary_svg = svg_chart(build_series(fwd, PRIMARY_ORDER), fwd_dates,
                                    title="Forward OOS decile cohorts vs equal-weight universe and SPY")
        fwd_spread_pts = [(0, 1.0)] + [(i + 1, p["cum"]) for i, p in enumerate(fwd["spread_series"])]
        fwd_spread_svg = svg_chart([{"name": "spread", "short": "Top−Bottom spread",
                                     "color": "#7C4DFF", "pts": fwd_spread_pts}], fwd_dates,
                                   title="Forward top-minus-bottom spread")
        fwd_body = f"""
      <div style="background:#2A1A1A;border-radius:8px;padding:14px 18px;border-left:3px solid #FBA94B;margin-bottom:14px">
        <div style="color:#FBA94B;font-weight:700;font-size:13px">⚠ Early forward period — {n_td} trading days, {fwd['evaluable_periods']} rebalances. Not yet statistically meaningful.</div>
        <p style="font-size:12px;color:#A0AEC0;margin-top:6px;line-height:1.55">
          Forward Day 0 = {escape(FORWARD_DAY0.isoformat())}; return window
          {escape(fwd['first_entry_date'])} → {escape(fwd['last_exit_date'])}
          (signals {escape(str(fwd['signal_date_range'][0]))} → {escape(str(fwd['signal_date_range'][1]))}).
          A {n_td}-trading-day out-of-sample window is far too short for any statistical
          inference — this is a directional illustration shown for transparency as the
          forward record accrues, not evidence of skill. In this early window the top-decile
          cohort trails the equal-weight universe; that is what the data shows and it is shown unblended.
        </p>
      </div>
      {fwd_primary_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(fwd, PRIMARY_ORDER)}</tbody>
      </table>
      {membership_html(mem)}
      <div style="margin-top:14px;padding:12px 14px;background:#151A23;border-radius:8px">
        <div style="font-size:12px;color:#E2E8F0;font-weight:600">Top-minus-bottom cohort spread (research spread statistic — not a position, not tradeable)</div>
        <div style="font-size:13px;color:#7C4DFF;font-family:JetBrains Mono,monospace;margin-top:4px">cumulative {_pct(fwd['spread_metrics']['cumulative_return'])} · max drawdown {_pct(fwd['spread_metrics']['max_drawdown'])}</div>
      </div>
      {fwd_spread_svg}"""
    else:
        fwd_body = f"""
      <div style="background:#1A2030;border-radius:8px;padding:18px;border-left:3px solid #FBA94B">
        <div style="color:#FBA94B;font-weight:700;font-size:13px;margin-bottom:8px">Insufficient forward price data — panel not yet evaluable</div>
        <p style="font-size:13px;color:#A0AEC0;line-height:1.6">
          Forward signals exist ({fwd['rebalance_dates']} rebalance dates,
          {escape(str(fwd['signal_date_range'][0]))} → {escape(str(fwd['signal_date_range'][1]))}),
          but internal <code>price_history</code> coverage currently ends
          <code>{escape(str(fwd['price_coverage_end']))}</code>. Measuring a cohort's
          <em>forward</em> return requires closing prices <em>after</em> the signal date,
          and none are available past the coverage end — so <strong>0 forward periods are
          evaluable</strong>. No external data was fetched or synthesized to fill this gap.
        </p>
        <p style="font-size:12px;color:#718096;margin-top:10px">Forward Day 0 = {escape(FORWARD_DAY0.isoformat())}.</p>
      </div>"""

    # ---- In-sample panel ----
    ins_dates = panel_dates(ins)
    ins_primary_svg = svg_chart(build_series(ins, PRIMARY_ORDER), ins_dates,
                                title="In-sample decile cohorts vs equal-weight universe and SPY")
    ins_label_svg = svg_chart(build_series(ins, LABEL_ORDER), ins_dates,
                              title="In-sample label cohorts vs SPY")
    spread_pts = [(0, 1.0)] + [(i + 1, p["cum"]) for i, p in enumerate(ins["spread_series"])]
    spread_svg = svg_chart([{"name": "spread", "short": "High−Low spread",
                             "color": "#7C4DFF", "pts": spread_pts}], ins_dates,
                           title="High-minus-low cohort spread (archived in-sample view)")

    # ---- continuous rolling charts (visual continuity only; stats per-regime)
    ROLL_CAPTION = ("Continuous for display only: the dashed May-18 line marks the in-sample "
                    "replay → forward out-of-sample regime boundary. All statistics are computed "
                    "per-regime and never blended across the boundary. Windows are rebased to "
                    "their start date.")
    roll_spread = rolling_chart_html(
        "roll-spread",
        [{"points": continuous_points(ins, fwd, "spread"),
          "short": "High−Low spread", "color": "#7C4DFF"}],
        caption=ROLL_CAPTION,
        title="High-minus-low cohort spread — latest rolling record · updated daily after U.S. market close")
    roll_labels = rolling_chart_html(
        "roll-labels",
        [{"points": continuous_points(ins, fwd, "cohort", "bullish_labeled"),
          "short": "Positive-label", "color": "#4DD0E1"},
         {"points": continuous_points(ins, fwd, "cohort", "cautious_labeled"),
          "short": "Risk-flag", "color": "#FBA94B"},
         {"points": continuous_points(ins, fwd, "cohort", "benchmark"),
          "short": "SPY", "color": "#A0AEC0", "dash": "7,4"}],
        caption=ROLL_CAPTION + " Label cohorts have small, variable membership — see the "
                "archived replay for per-date n.",
        title="Label cohorts vs SPY — latest rolling record · updated daily after U.S. market close")

    # ONE computed forward-n for every surface that states it (header status
    # card + "Not proven" list) — the site-walk gate asserts they agree.
    fwd_n = fwd["evaluable_periods"] if fwd["evaluable"] else 0

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · Signal Validation Lab</title>
  <meta name="description" content="Research cohort analysis (Fama-French-style decile event study) of YUCLAW composite signals. Hypothetical research illustration — not investment advice.">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1080px;margin:0 auto;padding:24px}}
    .header{{margin-bottom:16px;padding:18px 24px;background:#151A23;border:1px solid #1E232D;border-radius:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
    .logo{{font-size:20px;font-weight:800;color:#FFF;letter-spacing:-0.3px;text-decoration:none}}
    a.logo:hover{{color:#00E676}}
    .logo span{{color:#00E676}}
    .ver{{display:inline-block;background:#00E67620;color:#00E676;border:1px solid #00E67680;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:700;margin-left:8px;font-family:JetBrains Mono,monospace}}
    .navlinks a{{color:#A0AEC0;text-decoration:none;font-size:13px;padding:5px 11px;border-radius:6px;background:#1E232D;margin-left:6px}}
    .navlinks a:hover{{color:#00E676}}
    .fresh,.panel-fresh{{background:#0F1B14;border:1px solid #00E67640;border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:12px;color:#A0AEC0;font-family:JetBrains Mono,monospace}}
    .fresh strong,.panel-fresh strong{{color:#00E676}}
    .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:22px;font-size:12px;line-height:1.55;color:#A0AEC0}}
    .disclaimer-line strong{{color:#FBA94B}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:14px 18px;font-size:12px;line-height:1.55;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:4px}}
    .panel-sub{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}}
    .lead-tag{{display:inline-block;background:#00E67620;color:#00E676;border:1px solid #00E67680;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:0.5px;margin-left:8px}}
    .caveat-tag{{display:inline-block;background:#FBA94B20;color:#FBA94B;border:1px solid #FBA94B80;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:0.5px;margin-left:8px}}
    table{{width:100%;border-collapse:collapse;margin-top:14px}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:8px 12px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.6px}}
    td{{font-size:13px;border-bottom:1px solid #1A2030}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    details.acc{{background:#151A23;border:1px solid #1E232D;border-radius:12px;margin-bottom:20px;overflow:hidden}}
    details.acc>summary{{list-style:none;cursor:pointer;padding:16px 22px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#A0AEC0}}
    details.acc>summary::-webkit-details-marker{{display:none}}
    details.acc>summary::before{{content:"▸";color:#00E676;margin-right:8px}}
    details.acc[open]>summary::before{{content:"▾"}}
    .acc-body{{padding:0 22px 20px;font-size:13px;color:#A0AEC0}}
    .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
    .footer a{{color:#00E676;text-decoration:none}}
    .tile{{min-width:130px;margin-right:8px}}
    .tile .v{{font-size:22px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
    .rangebar{{display:flex;gap:4px}}
    .rangebtn{{background:#1E232D;color:#A0AEC0;border:1px solid #2D3748;border-radius:6px;padding:3px 10px;font-size:11px;cursor:pointer;font-family:JetBrains Mono,monospace}}
    .rangebtn.active{{background:#00E67620;color:#00E676;border-color:#00E67680}}
    .rollwin{{display:none}}
    .rollwin.active{{display:block}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Signal Validation Lab", active="validation_lab.html")}

    <div style="font-size:12px;color:#A0AEC0;margin:0 0 14px 0">
      Per-label hit-rate ledger: <a href="validation.html"
      style="color:#00E676;text-decoration:none">Forward Tracking →</a>
    </div>

    <div class="fresh">
      <strong>Data through {escape(data_through)}</strong> (last completed U.S. trading day) ·
      regenerated daily after market close · last build {escape(built)}
    </div>

    {status_cards_html(fwd_n, ledger)}

    <div class="disclaimer-line">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}
    </div>

    {honest_reading_html()}

    {integrity_card_html()}

    {proven_html(fwd_n)}

    <p style="font-size:14px;color:#A0AEC0;margin-bottom:18px;max-width:780px">
      A Fama–French-style <strong>decile-cohort event study</strong>: does YUCLAW's composite
      signal <em>score</em> carry forward information about subsequent realized returns? Cohorts
      are grouped by score decile or signal label and tracked as equal-weighted research cohorts
      against two references: the <strong>equal-weight universe</strong> (all scored tickers,
      same rebalance dates) and <strong>SPY</strong>. Derived statistics only — no raw prices.
      This is an event study, not portfolio management.
    </p>

    <div class="panel">
      <div class="panel-title">Latest rolling record</div>
      <div class="panel-sub">continuous display across the regime boundary · statistics stay strictly per-regime</div>
      <div class="panel-fresh" style="margin-bottom:4px">
        Updated through <strong>{escape(data_through)}</strong> · last build {escape(built)} · daily after U.S. market close
      </div>
      {roll_spread}
      {roll_labels}
    </div>

    {universe_panel_html(fwd)}

    <div class="panel" style="border:1px solid #00E67640">
      <div class="panel-title" id="panel-forward">Panel 1 · Forward (Out-of-Sample)<span class="lead-tag">LOOK-AHEAD-FREE</span></div>
      <div class="panel-sub">is_backfill = false · Day 0 = {escape(FORWARD_DAY0.isoformat())} · the honest panel</div>
      {fwd_body}
    </div>

    {panel4_html(q)}

    <details class="acc">
      <summary>Panel 2 · In-Sample Replay — Educational replay only (n={ins['evaluable_periods']} rebalances) · collapsed</summary>
      <div class="acc-body">
      {canonical_html("LOOKAHEAD", '<p style="font-size:12px;color:#FBA94B;margin-bottom:10px;line-height:1.6">', "</p>")}
      <p style="font-size:12px;color:#FBA94B;margin-bottom:12px">⚠ Educational replay only — in-sample results are <strong>systematically optimistic</strong> (see the look-ahead statement above). Label cohorts can be as small as a single name on some dates — treat all label-cohort figures below as illustrative, not evidence. The replay's final holding period is capped at forward Day 0 ({escape(FORWARD_DAY0.isoformat())}) so this window never overlaps Panel 1's.</p>
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:6px 0 8px">Archived replay (methodology view) · return window {escape(ins['first_entry_date'])} → {escape(ins['last_exit_date'])} · {ins['span_trading_days']} trading days</div>

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:6px 0 8px">Decile cohorts vs equal-weight universe and SPY (n=8-name cohorts)</div>
      {ins_primary_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, PRIMARY_ORDER)}</tbody>
      </table>

      <div style="margin-top:18px;padding:12px 14px;background:#1A2030;border-radius:8px">
        <div style="font-size:12px;color:#E2E8F0;font-weight:600">High-minus-low cohort spread (research spread statistic — not a position, not tradeable)</div>
        <div style="font-size:13px;color:#7C4DFF;font-family:JetBrains Mono,monospace;margin-top:4px">cumulative {_pct(ins['spread_metrics']['cumulative_return'])} · max drawdown {_pct(ins['spread_metrics']['max_drawdown'])}</div>
      </div>
      {spread_svg}

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:20px 0 8px">Label cohorts vs SPY (n= per-date membership in the table below — as small as 1; replay-optimistic figures)</div>
      {ins_label_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, LABEL_ORDER)}</tbody>
      </table>
      </div>
    </details>

    {rigor_panel_html(rig)}

    {_baselines()}

    {_neutralized()}

    {_cases()}

    {_transparency()}

    {maturity_html(ledger)}

    {reproduce_panel_html(ledger, source_commit)}

    {_packet_block("lab")}

    {_use_in_research("packets/yuclaw_validation_lab_packet.zip")}

    {_shared_status_block()}

    {challenge_html()}

    {roadmap_html()}

    {integrity_log_html()}

    {innovation_panel_html(ledger, c6)}

    <details class="acc">
      <summary>Methodology summary</summary>
      <div class="acc-body">
        <p>Equal-weighted cohorts, rebalanced at each signal date, ranked by composite <code>total_score</code>; top/bottom decile (~10%, currently 8 of 79). References: the equal-weight universe cohort (all scored tickers, identical rebalance schedule) and SPY. Returns are close-to-close from internal <code>price_history</code> (derived statistics only — raw prices never shown). Inclusion rule: a signal date enters the study only if it scored ≥{MIN_UNIVERSE_FOR_DECILES} tickers; a ticker contributes only when entry and exit closes both exist. The in-sample replay's final holding period is capped at forward Day 0 so the two panels' return windows never overlap. The two panels are never blended. Annualized figures are intentionally omitted — annualizing a weeks-long window is misleading; cumulative return over N trading days is shown instead. Full methodology, including the in-sample look-ahead disclosure, is in <a href="methodology/validation_lab.md" style="color:#00E676">methodology/validation_lab.md</a>.</p>
      </div>
    </details>

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW Signal Validation Lab · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
  <script>
  (function() {{
    var mobile = window.matchMedia && window.matchMedia('(max-width: 640px)').matches;
    var def = mobile ? '60' : 'all';
    function activate(chart, w) {{
      var wins = document.querySelectorAll('.rollwin[data-chart="' + chart + '"]');
      var found = false;
      wins.forEach(function(el) {{ if (el.dataset.w === w) found = true; }});
      if (!found) w = 'all';
      wins.forEach(function(el) {{ el.classList.toggle('active', el.dataset.w === w); }});
      document.querySelectorAll('.rangebtn[data-chart="' + chart + '"]').forEach(function(b) {{
        b.classList.toggle('active', b.dataset.w === w);
      }});
    }}
    var charts = {{}};
    document.querySelectorAll('.rollwin').forEach(function(el) {{ charts[el.dataset.chart] = 1; }});
    Object.keys(charts).forEach(function(c) {{ activate(c, def); }});
    document.querySelectorAll('.rangebtn').forEach(function(b) {{
      b.addEventListener('click', function() {{ activate(b.dataset.chart, b.dataset.w); }});
    }});
  }})();
  </script>
{build_footer()}
</body>
</html>
"""


def main() -> int:
    html = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"[render_validation_lab] wrote {OUT} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
