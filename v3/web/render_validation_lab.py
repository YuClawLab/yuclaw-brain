"""Render the YUCLAW Signal Validation Lab page to docs/validation_lab.html.

Static, data-baked, self-contained (inline SVG, no JS, no CDNs). RESEARCH
COHORT ANALYSIS framing throughout — cohorts named by score decile or signal
label, never by trade direction. ZERO public SELL/SHORT/BUY/long-position
language. Only derived statistics are shown; raw prices never appear.

New page; does NOT touch render_landing.py or docs/index.html.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.lab.cohort_engine import FORWARD_DAY0, compute_all

OUT = _REPO / "docs" / "validation_lab.html"

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

# compliance-safe display names (NO trade-direction language)
COHORT_LABEL = {
    "top_decile": "Top-decile cohort (by composite score)",
    "bottom_decile": "Bottom-decile cohort (by composite score)",
    "bullish_labeled": "Bullish-labeled cohort (STRONG_BULLISH + BULLISH)",
    "cautious_labeled": "Cautious-labeled cohort (WEAKENING / NEGATIVE_EVENT / BEARISH_WATCH / RISK_ALERT)",
    "benchmark": "SPY benchmark (broad-market reference)",
}
COHORT_COLOR = {
    "top_decile": "#00E676",
    "bottom_decile": "#FF3366",
    "bullish_labeled": "#4DD0E1",
    "cautious_labeled": "#FBA94B",
    "benchmark": "#A0AEC0",
}
PRIMARY_ORDER = ["top_decile", "bottom_decile", "benchmark"]
LABEL_ORDER = ["bullish_labeled", "cautious_labeled", "benchmark"]


def _pct(x):
    return f"{x*100:+.2f}%" if x is not None else "—"


def svg_chart(series: list[dict], width=900, height=340, baseline=1.0, title="") -> str:
    """series: [{name,color,pts:[(i,cum)]}]. Inline SVG cumulative-return chart."""
    pad_l, pad_r, pad_t, pad_b = 56, 180, 28, 34
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
    # cohort polylines + legend
    for k, s in enumerate(series):
        pts = " ".join(f"{X(i):.1f},{Y(c):.1f}" for i, c in s["pts"])
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{s["color"]}" '
                     f'stroke-width="2"/>')
        ly = pad_t + 6 + k * 18
        parts.append(f'<line x1="{pad_l+plot_w+14}" y1="{ly}" x2="{pad_l+plot_w+30}" '
                     f'y2="{ly}" stroke="{s["color"]}" stroke-width="3"/>')
        final = (s["pts"][-1][1] - 1) * 100 if s["pts"] else 0
        parts.append(f'<text x="{pad_l+plot_w+34}" y="{ly+4}" fill="#E2E8F0" '
                     f'font-size="10" font-family="JetBrains Mono,monospace">'
                     f'{escape(s["short"])} {final:+.1f}%</text>')
    parts.append('</svg>')
    return "".join(parts)


def build_series(panel: dict, order: list[str]) -> list[dict]:
    out = []
    SHORT = {"top_decile": "Top decile", "bottom_decile": "Bottom decile",
             "bullish_labeled": "Bullish-labeled", "cautious_labeled": "Cautious-labeled",
             "benchmark": "SPY"}
    for c in order:
        pts = [(i, p["cum"]) for i, p in enumerate(panel["series"][c])]
        pts = [(0, 1.0)] + [(i + 1, c2) for i, c2 in pts]  # anchor at 1.0 baseline
        out.append({"name": c, "short": SHORT[c], "color": COHORT_COLOR[c], "pts": pts})
    return out


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


def render() -> str:
    data = compute_all()
    fwd, ins = data["forward"], data["in_sample"]
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ---- Forward panel (leads). Now evaluable (price feed restored). ----
    if fwd["evaluable"]:
        n_td = fwd["span_trading_days"]
        fwd_primary_svg = svg_chart(build_series(fwd, PRIMARY_ORDER),
                                    title="Forward OOS decile cohorts vs SPY")
        fwd_spread_pts = [(0, 1.0)] + [(i + 1, p["cum"]) for i, p in enumerate(fwd["spread_series"])]
        fwd_spread_svg = svg_chart([{"name": "spread", "short": "Top−Bottom spread",
                                     "color": "#7C4DFF", "pts": fwd_spread_pts}],
                                   title="Forward top-minus-bottom spread")
        fwd_body = f"""
      <div style="background:#2A1A1A;border-radius:8px;padding:14px 18px;border-left:3px solid #FBA94B;margin-bottom:14px">
        <div style="color:#FBA94B;font-weight:700;font-size:13px">⚠ Early forward period — {n_td} trading days. Not yet statistically meaningful.</div>
        <p style="font-size:12px;color:#A0AEC0;margin-top:6px;line-height:1.55">
          Forward Day 0 = {escape(FORWARD_DAY0.isoformat())}; signals
          {escape(str(fwd['signal_date_range'][0]))} → {escape(str(fwd['signal_date_range'][1]))}.
          A {n_td}-trading-day out-of-sample window is far too short for any statistical
          inference — this is a directional illustration shown for transparency as the
          forward record accrues, not evidence of skill.
        </p>
      </div>
      {fwd_primary_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(fwd, PRIMARY_ORDER)}</tbody>
      </table>
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
          This panel will populate once the price feed resumes (a separate, tracked
          data-freshness item).
        </p>
        <p style="font-size:12px;color:#718096;margin-top:10px">Forward Day 0 = {escape(FORWARD_DAY0.isoformat())}.</p>
      </div>"""

    # ---- In-sample panel ----
    ins_primary_svg = svg_chart(build_series(ins, PRIMARY_ORDER), title="In-sample decile cohorts vs SPY")
    ins_label_svg = svg_chart(build_series(ins, LABEL_ORDER), title="In-sample label cohorts vs SPY")
    spread_pts = [(0, 1.0)] + [(i + 1, p["cum"]) for i, p in enumerate(ins["spread_series"])]
    spread_svg = svg_chart([{"name": "spread", "short": "Top−Bottom spread",
                             "color": "#7C4DFF", "pts": spread_pts}],
                           title="Top-minus-bottom cohort spread")

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
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div><a href="index.html" class="logo">YUCLAW</a> <span style="color:#A0AEC0;font-size:14px">· Signal Validation Lab</span> <span class="ver">v4.2.0</span></div>
      <div class="navlinks">
        <a href="index.html">← Dashboard</a>
        <a href="methodology/validation_lab.md">Methodology</a>
        <a href="https://github.com/YuClawLab/yuclaw-trust">Ledger</a>
      </div>
    </div>

    <div class="disclaimer-line">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}
    </div>

    <p style="font-size:14px;color:#A0AEC0;margin-bottom:18px;max-width:780px">
      A Fama–French-style <strong>decile-cohort event study</strong>: does YUCLAW's composite
      signal <em>score</em> carry forward information about subsequent realized returns? Cohorts
      are grouped by score decile or signal label and tracked as equal-weighted research cohorts.
      Derived statistics only — no raw prices. This is an event study, not portfolio management.
    </p>

    <div class="panel">
      <div class="panel-title">Panel 1 · Forward (Out-of-Sample)<span class="lead-tag">LOOK-AHEAD-FREE</span></div>
      <div class="panel-sub">is_backfill = false · Day 0 = {escape(FORWARD_DAY0.isoformat())} · the honest panel</div>
      {fwd_body}
    </div>

    <div class="panel">
      <div class="panel-title">Panel 2 · In-Sample Replay<span class="caveat-tag">PARAMETRIC LOOK-AHEAD</span></div>
      <div class="panel-sub">is_backfill = true · {ins['evaluable_periods']} rebalances · {ins['span_trading_days']} trading days · signals {escape(ins['signal_date_range'][0])} → {escape(ins['signal_date_range'][1])}</div>
      <p style="font-size:12px;color:#FBA94B;margin-bottom:12px">⚠ The evidence-extraction model's training cutoff overlaps this window — in-sample results carry an unavoidable parametric look-ahead bias and are systematically optimistic. A <em>replay</em>, not a forecast.</p>

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:6px 0 8px">Decile cohorts vs SPY (primary, robust ~8-name cohorts)</div>
      {ins_primary_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, PRIMARY_ORDER)}</tbody>
      </table>

      <div style="margin-top:18px;padding:12px 14px;background:#1A2030;border-radius:8px">
        <div style="font-size:12px;color:#E2E8F0;font-weight:600">Top-minus-bottom cohort spread (research spread statistic — not a position, not tradeable)</div>
        <div style="font-size:13px;color:#7C4DFF;font-family:JetBrains Mono,monospace;margin-top:4px">cumulative {_pct(ins['spread_metrics']['cumulative_return'])} · max drawdown {_pct(ins['spread_metrics']['max_drawdown'])}</div>
      </div>
      {spread_svg}

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:20px 0 8px">Label cohorts vs SPY (secondary — small, variable membership; illustrative only)</div>
      {ins_label_svg}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, LABEL_ORDER)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:10px">⚠ Label cohorts can be as small as a single name on some dates (see n column); small-n figures are statistically noisy and shown for illustration only. The decile cohorts above are the robust comparison.</p>
    </div>

    <details class="acc">
      <summary>Methodology summary</summary>
      <div class="acc-body">
        <p>Equal-weighted cohorts, rebalanced at each signal date, ranked by composite <code>total_score</code>; top/bottom decile (~10%). Returns are close-to-close from internal <code>price_history</code> (derived statistics only — raw prices never shown). Benchmark: SPY. Two panels (forward OOS, in-sample replay) are never blended. Annualized figures are intentionally omitted — annualizing a ~3-month window is misleading; cumulative return over N trading days is shown instead. Full methodology, including the in-sample look-ahead disclosure and the forward-window data limitation, is in <a href="methodology/validation_lab.md" style="color:#00E676">methodology/validation_lab.md</a>.</p>
      </div>
    </details>

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW Signal Validation Lab · built {escape(built)} · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
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
