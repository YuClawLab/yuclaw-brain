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
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.lab.cohort_engine import (FORWARD_DAY0, MIN_UNIVERSE_FOR_DECILES,
                                  compute_all, current_top_decile)

OUT = _REPO / "docs" / "validation_lab.html"
UNIVERSE_PATH = _REPO / "v3" / "universe.json"

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
              baseline=1.0, title="") -> str:
    """series: [{name,short,color,pts:[(i,cum)],dash?}]; dates: ISO strings
    aligned to x indices 0..max_i. Inline SVG cumulative-return chart with
    real calendar dates on the x-axis."""
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
    SHORT = {"top_decile": "Top decile", "bottom_decile": "Bottom decile",
             "bullish_labeled": "Bullish-labeled", "cautious_labeled": "Cautious-labeled",
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
    </div>"""


def membership_html(mem: dict) -> str:
    rows = []
    for m in mem["members"]:
        rows.append(
            f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(m['ticker'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['score']:+.4f}</td>"
            f"<td style='padding:7px 12px;color:#4DD0E1;font-size:12px'>{escape(m['label'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:12px'>{escape(m['grade'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{m['ev_count']}</td></tr>")
    return f"""
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:20px 0 8px">
        Current top-decile cohort membership · as of {escape(mem['as_of'] or '—')} · {mem['k']} of {mem['universe_n']} tickers
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


def render() -> str:
    data = compute_all()
    fwd, ins = data["forward"], data["in_sample"]
    mem = current_top_decile()
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
    spread_svg = svg_chart([{"name": "spread", "short": "Top−Bottom spread",
                             "color": "#7C4DFF", "pts": spread_pts}], ins_dates,
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
    .fresh{{background:#0F1B14;border:1px solid #00E67640;border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:12px;color:#A0AEC0;font-family:JetBrains Mono,monospace}}
    .fresh strong{{color:#00E676}}
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

    <div class="fresh">
      <strong>Data through {escape(data_through)}</strong> (last completed U.S. trading day) ·
      regenerated daily after market close · last build {escape(built)}
    </div>

    <div class="disclaimer-line">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}
    </div>

    <p style="font-size:14px;color:#A0AEC0;margin-bottom:18px;max-width:780px">
      A Fama–French-style <strong>decile-cohort event study</strong>: does YUCLAW's composite
      signal <em>score</em> carry forward information about subsequent realized returns? Cohorts
      are grouped by score decile or signal label and tracked as equal-weighted research cohorts
      against two references: the <strong>equal-weight universe</strong> (all scored tickers,
      same rebalance dates) and <strong>SPY</strong>. Derived statistics only — no raw prices.
      This is an event study, not portfolio management.
    </p>

    <div class="disclaimer-line" style="border-left-color:#4DD0E1">
      <strong style="color:#4DD0E1">Infrastructure note (Jun 26 – Jul 3, 2026) —</strong>
      a network outage on the research host interrupted external data feeds. Daily signal
      snapshots continued to be written on-box, point-in-time, throughout the window — but from
      Jun 26 to Jul 2 their price-derived inputs were frozen at Jun 25 closes (the price feed was
      unreachable), and this page was not republished during the outage. Price history and SEC
      filing ingestion were restored and backfilled on Jul 3, and the filing window was
      re-checked against EDGAR on Jul 5 (no missing filings). No snapshot or ledger row was retroactively edited: the outage-window
      snapshots stand exactly as written, stale inputs and all.
    </div>

    {universe_panel_html(fwd)}

    <div class="panel">
      <div class="panel-title">Panel 1 · Forward (Out-of-Sample)<span class="lead-tag">LOOK-AHEAD-FREE</span></div>
      <div class="panel-sub">is_backfill = false · Day 0 = {escape(FORWARD_DAY0.isoformat())} · the honest panel</div>
      {fwd_body}
    </div>

    <div class="panel">
      <div class="panel-title">Panel 2 · In-Sample Replay<span class="caveat-tag">PARAMETRIC LOOK-AHEAD</span></div>
      <div class="panel-sub">is_backfill = true · {ins['evaluable_periods']} rebalances · {ins['span_trading_days']} trading days · return window {escape(ins['first_entry_date'])} → {escape(ins['last_exit_date'])}</div>
      <p style="font-size:12px;color:#FBA94B;margin-bottom:12px">⚠ The evidence-extraction model's training cutoff overlaps this window — in-sample results carry an unavoidable parametric look-ahead bias and are systematically optimistic. A <em>replay</em>, not a forecast. The replay's final holding period is capped at forward Day 0 ({escape(FORWARD_DAY0.isoformat())}) so this panel's return window never overlaps Panel 1's.</p>

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:6px 0 8px">Decile cohorts vs equal-weight universe and SPY (primary, 8-name cohorts)</div>
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
        <p>Equal-weighted cohorts, rebalanced at each signal date, ranked by composite <code>total_score</code>; top/bottom decile (~10%, currently 8 of 79). References: the equal-weight universe cohort (all scored tickers, identical rebalance schedule) and SPY. Returns are close-to-close from internal <code>price_history</code> (derived statistics only — raw prices never shown). Inclusion rule: a signal date enters the study only if it scored ≥{MIN_UNIVERSE_FOR_DECILES} tickers; a ticker contributes only when entry and exit closes both exist. The in-sample replay's final holding period is capped at forward Day 0 so the two panels' return windows never overlap. The two panels are never blended. Annualized figures are intentionally omitted — annualizing a weeks-long window is misleading; cumulative return over N trading days is shown instead. Full methodology, including the in-sample look-ahead disclosure, is in <a href="methodology/validation_lab.md" style="color:#00E676">methodology/validation_lab.md</a>.</p>
      </div>
    </details>

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW Signal Validation Lab · data through {escape(data_through)} · built {escape(built)} · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
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
