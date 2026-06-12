"""Render the YUCLAW Signal Validation Lab (PRO) to docs/validation_lab.html.

Academic-grade research cohort analysis: full Fama-French-style decile spectrum,
per-rebalance information coefficient, decile-entry event studies, top-minus-
bottom spread with drawdown, and cohort turnover/stability — plus the original
cumulative-cohort panels, restyled.

Static, data-baked, self-contained (inline SVG via v3.web.chartkit, no JS, no
CDNs except the optional webfont). RESEARCH COHORT ANALYSIS framing throughout:
cohorts named by score decile or signal label, never by trade direction. ZERO
public SELL/SHORT/BUY/long-position language. Only derived statistics are shown;
raw prices never appear. Forward (out-of-sample) and in-sample panels are
computed and displayed separately and never blended. Honest-statistics
discipline: no t-statistics / significance claims on the short forward window;
in-sample carries the parametric look-ahead disclosure; nothing annualized.

Does NOT touch render_landing.py or docs/index.html.
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
from v3.lab.analytics import compute_all_analytics
from v3.web import chartkit as ck

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

COHORT_LABEL = {
    "top_decile": "Top-decile cohort (by composite score)",
    "bottom_decile": "Bottom-decile cohort (by composite score)",
    "bullish_labeled": "Bullish-labeled cohort (STRONG_BULLISH + BULLISH)",
    "cautious_labeled": "Cautious-labeled cohort (WEAKENING / NEGATIVE_EVENT / BEARISH_WATCH / RISK_ALERT)",
    "benchmark": "SPY benchmark (broad-market reference)",
}
COHORT_COLOR = {
    "top_decile": ck.GREEN, "bottom_decile": ck.RED,
    "bullish_labeled": ck.BLUE, "cautious_labeled": ck.AMBER, "benchmark": ck.GRAY,
}
SHORT = {"top_decile": "Top decile", "bottom_decile": "Bottom decile",
         "bullish_labeled": "Bullish-labeled", "cautious_labeled": "Cautious-labeled",
         "benchmark": "SPY"}
PRIMARY_ORDER = ["top_decile", "bottom_decile", "benchmark"]
LABEL_ORDER = ["bullish_labeled", "cautious_labeled", "benchmark"]

FWD_TAG, INS_TAG = "FORWARD / OOS", "IN-SAMPLE REPLAY"


def _pct(x):
    return f"{x*100:+.2f}%" if x is not None else "—"


def _fnum(x, dp=3):
    return "—" if x is None else f"{x:+.{dp}f}"


# ---- cumulative cohort curves (restyled via chartkit) ----------------------
def cum_chart(panel: dict, order: list[str], title: str, tag: str, n_label: str) -> str:
    series = []
    for c in order:
        ys = [0.0] + [p["cum"] - 1.0 for p in panel["series"][c]]  # baseline 0% return
        series.append({"name": SHORT[c], "color": COHORT_COLOR[c], "ys": ys})
    x_count = max((len(s["ys"]) for s in series), default=1)
    return ck.line_chart(series=series, x_count=x_count, title=title, tag=tag,
                         tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
                         n_label=n_label, y_axis_label="cumulative return",
                         x_axis_label="rebalance period", baseline=0.0)


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
            f"<td style='padding:8px 12px;color:{COHORT_COLOR[c]};font-family:{ck.MONO}'>{_pct(m['cumulative_return'])}</td>"
            f"<td style='padding:8px 12px;color:#FF3366;font-family:{ck.MONO}'>{_pct(m['max_drawdown'])}</td>"
            f"<td style='padding:8px 12px;color:#A0AEC0;font-family:{ck.MONO}'>{m['volatility_periodic']*100:.2f}%</td>"
            f"<td style='padding:8px 12px;color:#A0AEC0;font-family:{ck.MONO}'>{hit}</td>"
            f"<td style='padding:8px 12px;color:#718096;font-family:{ck.MONO}'>{nsize}</td></tr>")
    return "".join(rows)


# ---- (a) decile spectrum ----------------------------------------------------
def decile_chart(ds: dict, tag: str) -> str:
    if not ds.get("evaluable"):
        return '<p style="color:#718096;font-size:12px">Not evaluable — no forward price window.</p>'
    labels = [f"D{k+1}" for k in range(10)]
    colors = [ck.lerp_color(ck.GREEN, ck.RED, k / 9) for k in range(10)]
    vals = ds["decile_mean_return"]
    return ck.bar_chart(
        labels=labels, values=vals, colors=colors,
        title="Full decile spectrum — mean next-period return by score decile",
        tag=tag, tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
        n_label=f"pooled over {ds['n_rebalances']} rebalances · D1 = top score, D10 = bottom",
        y_axis_label="mean fwd return", x_axis_label="composite-score decile (D1 highest)")


def decile_verdict(ds: dict) -> str:
    if not ds.get("evaluable"):
        return "not evaluable"
    rho, tmb = ds["spearman_rho"], ds["top_minus_bottom"]
    mono = f"{ds['monotonic_steps']}/{ds['max_steps']} steps monotone-decreasing"
    return (f"Spearman ρ(score-decile, return) = <b>{_fnum(rho,2)}</b> · "
            f"D1−D10 = <b>{_pct(tmb)}</b> · {mono}")


# ---- (b) information coefficient --------------------------------------------
def ic_chart(ic: dict, tag: str) -> str:
    if not ic.get("evaluable"):
        return '<p style="color:#718096;font-size:12px">Not evaluable.</p>'
    s = ic["series"]
    labels = [d["date"][5:] for d in s]  # MM-DD
    vals = [d["ic"] for d in s]
    colors = [ck.GREEN if v > 0 else ck.RED for v in vals]
    return ck.bar_chart(
        labels=labels, values=vals, colors=colors,
        title="Information coefficient — per-rebalance Spearman rank correlation",
        tag=tag, tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
        n_label=f"n = {ic['n_points']} rebalances · mean IC {_fnum(ic['mean_ic'])} (descriptive)",
        y_axis_label="IC (rank corr)", x_axis_label="rebalance date",
        value_fmt=lambda v: f"{v:+.2f}", mean=ic["mean_ic"],
        mean_label=f"mean {_fnum(ic['mean_ic'],3)}", rotate_x=len(s) > 14)


# ---- (c) event study --------------------------------------------------------
def event_chart(ev_top: dict, ev_bot: dict, tag: str) -> str:
    series = []
    if ev_top.get("evaluable"):
        series.append({"name": f"Top-decile entry (n={ev_top['n_events']})",
                       "color": ck.GREEN, "ys": ev_top["mean_curve"],
                       "band": ev_top["stdev_band"]})
    if ev_bot.get("evaluable"):
        series.append({"name": f"Bottom-decile entry (n={ev_bot['n_events']})",
                       "color": ck.RED, "ys": ev_bot["mean_curve"],
                       "band": ev_bot["stdev_band"]})
    if not series:
        return '<p style="color:#718096;font-size:12px">Not evaluable — too few decile-entry events with a trackable forward window.</p>'
    x_count = max((len(s["ys"]) for s in series), default=1)
    return ck.line_chart(
        series=series, x_count=x_count,
        title="Event study — avg cumulative return vs SPY after a decile entry",
        tag=tag, tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
        n_label="event time · shaded band = ±1 stdev across events",
        y_axis_label="cum. excess vs SPY", x_axis_label="trading days after entry (event time)",
        x_ticks=[(i, str(i)) for i in range(0, x_count, max(1, x_count // 10))],
        baseline=0.0, day0_marker=True, legend_right=True)


# ---- (e) turnover / stability ----------------------------------------------
def turnover_chart(to: dict, tag: str) -> str:
    if not to.get("evaluable"):
        return '<p style="color:#718096;font-size:12px">Not evaluable.</p>'
    s = to["series"]
    labels = [d["date"][5:] for d in s]
    vals = [d["turnover"] for d in s]
    return ck.bar_chart(
        labels=labels, values=vals, colors=[ck.PURPLE] * len(vals),
        title="Top-decile cohort turnover — names replaced vs prior rebalance",
        tag=tag, tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
        n_label=f"n = {to['n_points']} transitions · mean turnover {to['mean_turnover']*100:.0f}% · "
                f"mean persistence {to['mean_persistence']:.1f} rebalances",
        y_axis_label="turnover %", x_axis_label="rebalance date",
        value_fmt=lambda v: f"{v*100:.0f}%", mean=to["mean_turnover"],
        mean_label=f"mean {to['mean_turnover']*100:.0f}%", rotate_x=len(s) > 14)


def render() -> str:
    data = compute_all()
    ana = compute_all_analytics()
    fwd, ins = data["forward"], data["in_sample"]
    af, ai = ana["forward"], ana["in_sample"]
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    fwd_n_td = fwd["span_trading_days"] if fwd["evaluable"] else 0
    ins_n = ins["evaluable_periods"]

    # ---------- headline findings (honest, unflattering shown) ----------
    fwd_ds, ins_ds = af["decile_spectrum"], ai["decile_spectrum"]
    fwd_ic, ins_ic = af["ic"], ai["ic"]
    headline = f"""
      <div style="background:#11161F;border:1px solid #1E232D;border-radius:10px;padding:16px 20px;margin-bottom:20px">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:10px">Headline findings — reported as-is, including weak results</div>
        <table style="margin-top:0">
          <thead><tr><th>Statistic</th><th>Forward (OOS)</th><th>In-sample (look-ahead)</th></tr></thead>
          <tbody>
            <tr><td style="padding:7px 12px;color:#E2E8F0">Decile monotonicity — Spearman ρ(score-decile, return)</td>
                <td style="padding:7px 12px;color:#E2E8F0;font-family:{ck.MONO}">{_fnum(fwd_ds.get('spearman_rho'),2)}</td>
                <td style="padding:7px 12px;color:#E2E8F0;font-family:{ck.MONO}">{_fnum(ins_ds.get('spearman_rho'),2)}</td></tr>
            <tr><td style="padding:7px 12px;color:#E2E8F0">Mean information coefficient (IC)</td>
                <td style="padding:7px 12px;color:#E2E8F0;font-family:{ck.MONO}">{_fnum(fwd_ic.get('mean_ic'))}</td>
                <td style="padding:7px 12px;color:#E2E8F0;font-family:{ck.MONO}">{_fnum(ins_ic.get('mean_ic'))}</td></tr>
            <tr><td style="padding:7px 12px;color:#E2E8F0">IC &gt; 0 hit-rate</td>
                <td style="padding:7px 12px;color:#A0AEC0;font-family:{ck.MONO}">{(fwd_ic.get('hit_rate_pos') or 0)*100:.0f}%</td>
                <td style="padding:7px 12px;color:#A0AEC0;font-family:{ck.MONO}">{(ins_ic.get('hit_rate_pos') or 0)*100:.0f}%</td></tr>
            <tr><td style="padding:7px 12px;color:#E2E8F0">Top-minus-bottom decile spread (cohort, pooled)</td>
                <td style="padding:7px 12px;color:#A0AEC0;font-family:{ck.MONO}">{_pct(fwd_ds.get('top_minus_bottom'))}</td>
                <td style="padding:7px 12px;color:#A0AEC0;font-family:{ck.MONO}">{_pct(ins_ds.get('top_minus_bottom'))}</td></tr>
          </tbody>
        </table>
        <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
          <strong style="color:#FBA94B">Plain reading:</strong> on the data so far the composite score shows
          <strong>weak and non-monotonic</strong> cross-sectional return separation — the decile spectrum is not
          cleanly ordered, and mean IC is near zero (slightly negative) on both panels. We report this directly
          rather than selecting a flattering cut. The forward window is far too short for statistical inference,
          and the in-sample panel is biased optimistic by parametric look-ahead — so neither panel should be read
          as evidence of skill. These are descriptive statistics on an accruing record.
        </p>
      </div>"""

    # ---------- forward caveat block ----------
    if fwd["evaluable"]:
        fwd_caveat = f"""
      <div style="background:#2A1A1A;border-radius:8px;padding:13px 18px;border-left:3px solid #FBA94B;margin-bottom:8px">
        <div style="color:#FBA94B;font-weight:700;font-size:12.5px">⚠ Early forward period — {fwd_n_td} trading days, {fwd_ic.get('n_points','—')} rebalances. Descriptive only; not statistically meaningful.</div>
        <p style="font-size:12px;color:#A0AEC0;margin-top:6px;line-height:1.55">
          Forward Day 0 = {escape(FORWARD_DAY0.isoformat())}; signals {escape(str(fwd['signal_date_range'][0]))} → {escape(str(fwd['signal_date_range'][1]))}.
          With this few observations no t-statistic or significance claim is reported — it would be meaningless at this N.
          Shown for transparency as the out-of-sample record accrues, not as evidence of skill.
        </p>
      </div>"""
    else:
        fwd_caveat = '<p style="color:#FBA94B;font-size:12.5px">Forward panel not yet evaluable — price window insufficient.</p>'

    # ---------- the six analytic sections ----------
    def section(num, title, sub, fwd_html, ins_html, note=""):
        note_html = f'<p style="font-size:11px;color:#718096;margin-top:8px">{note}</p>' if note else ""
        return f"""
    <div class="panel">
      <div class="panel-title">{num} · {escape(title)}</div>
      <div class="panel-sub">{escape(sub)}</div>
      {fwd_html}
      {ins_html}
      {note_html}
    </div>"""

    # (a) decile spectrum
    sec_decile = section(
        "A", "Full decile spectrum (D1→D10)",
        "the headline academic test — monotonic ordering of forward return across score deciles",
        decile_chart(fwd_ds, FWD_TAG) + f'<div class="verdict">Forward: {decile_verdict(fwd_ds)}</div>',
        decile_chart(ins_ds, INS_TAG) + f'<div class="verdict">In-sample: {decile_verdict(ins_ds)}</div>',
        "Bars are equal-weighted mean next-period returns of each ~8-name score decile, pooled across rebalances. "
        "A skilful score would show monotonically decreasing bars from D1 to D10; ρ near 0 (or non-monotone bars) "
        "indicates little cross-sectional separation.")

    # (b) information coefficient
    sec_ic = section(
        "B", "Information coefficient (IC)",
        "per-rebalance Spearman rank correlation of composite score vs next-period return",
        ic_chart(fwd_ic, FWD_TAG),
        ic_chart(ins_ic, INS_TAG),
        f"Descriptive statistics only. Forward: mean IC {_fnum(fwd_ic.get('mean_ic'))}, "
        f"IC&gt;0 hit-rate {(fwd_ic.get('hit_rate_pos') or 0)*100:.0f}%, ICIR {_fnum(fwd_ic.get('icir'),2)} "
        f"(n={fwd_ic.get('n_points','—')}). In-sample: mean IC {_fnum(ins_ic.get('mean_ic'))}, "
        f"hit-rate {(ins_ic.get('hit_rate_pos') or 0)*100:.0f}%, ICIR {_fnum(ins_ic.get('icir'),2)} "
        f"(n={ins_ic.get('n_points','—')}). ICIR = mean/stdev of the IC series — a descriptive consistency ratio, "
        "NOT an annualized or significance-tested quantity. No t-statistics are reported at these sample sizes.")

    # (c) event study
    sec_event = section(
        "C", "Event study — decile-entry dynamics",
        "average cumulative return relative to SPY in event time after a name ENTERS the top vs bottom decile",
        event_chart(af["event_top"], af["event_bottom"], FWD_TAG),
        event_chart(ai["event_top"], ai["event_bottom"], INS_TAG),
        "Event time is reset to 0 at each entry (a name newly appearing in the decile vs the prior rebalance), "
        "then averaged across all such events; the shaded band is ±1 cross-event standard deviation (dispersion, "
        "not a confidence interval). Excess return = cohort name minus SPY, cumulative from entry.")

    # (d) spread + drawdown
    def spread_block(panel, tag):
        if not panel.get("evaluable"):
            return '<p style="color:#718096;font-size:12px">Not evaluable.</p>'
        cum = [p["cum"] for p in panel["spread_series"]]
        sm = panel["spread_metrics"]
        chart = ck.drawdown_chart(
            cum=cum, title="Top-minus-bottom cohort spread — cumulative with drawdown",
            tag=tag, tag_color=(ck.GREEN if tag == FWD_TAG else ck.AMBER),
            n_label=f"cumulative {_pct(sm['cumulative_return'])} · max drawdown {_pct(sm['max_drawdown'])}",
            max_dd=sm["max_drawdown"])
        return chart + (
            f'<div style="font-size:12px;color:#7C4DFF;font-family:{ck.MONO};margin-top:2px">'
            f'research spread statistic (D1 minus D10 cohort) — not a position, not long/short, not tradeable</div>')
    sec_spread = section(
        "D", "Top-minus-bottom spread + drawdown",
        "the decile-spread research statistic with underwater (drawdown) shading and max-drawdown annotation",
        spread_block(fwd, FWD_TAG),
        spread_block(ins, INS_TAG),
        "The dashed line is the running peak; red shading is the drawdown beneath it. This is a derived spread "
        "between two research cohorts — a descriptive transparency statistic, explicitly not a tradeable position.")

    # (e) turnover / stability
    sec_turn = section(
        "E", "Cohort stability — turnover & persistence",
        "how much the top-decile cohort changes each rebalance, and how long names persist",
        turnover_chart(af["turnover"], FWD_TAG),
        turnover_chart(ai["turnover"], INS_TAG),
        "Turnover = fraction of the prior top-decile cohort no longer present at the next rebalance; persistence = "
        "average consecutive rebalances a name remains in the top decile. Presented purely as research transparency "
        "on cohort stability — relevant to understanding how reactive the score is, not a product or index claim.")

    # (f) cumulative cohort curves (restyled)
    fwd_cum = (cum_chart(fwd, PRIMARY_ORDER, "Cumulative cohort return vs SPY", FWD_TAG,
                         f"{fwd_n_td} trading days · ~8-name deciles") if fwd["evaluable"]
               else '<p style="color:#FBA94B;font-size:12px">Forward cumulative panel not yet evaluable.</p>')
    ins_cum = cum_chart(ins, PRIMARY_ORDER, "Cumulative cohort return vs SPY", INS_TAG,
                        f"{ins_n} rebalances · {ins['span_trading_days']} trading days")
    ins_label_cum = cum_chart(ins, LABEL_ORDER, "Cumulative label-cohort return vs SPY", INS_TAG,
                              "secondary — small, variable membership")
    sec_cum = f"""
    <div class="panel">
      <div class="panel-title">F · Cumulative cohort curves</div>
      <div class="panel-sub">equal-weighted cumulative return of the decile and label cohorts vs SPY (restyled)</div>
      {fwd_cum}
      {fwd_caveat if fwd['evaluable'] else ''}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(fwd, PRIMARY_ORDER) if fwd['evaluable'] else ''}</tbody>
      </table>
      <div style="height:10px"></div>
      {ins_cum}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, PRIMARY_ORDER)}</tbody>
      </table>
      {ins_label_cum}
      <table>
        <thead><tr><th>Cohort</th><th>Cumulative return</th><th>Max drawdown</th><th>Volatility (periodic)</th><th>Hit-rate vs SPY</th><th>n (min/med/max)</th></tr></thead>
        <tbody>{metric_rows(ins, LABEL_ORDER)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:10px">⚠ Label cohorts can be as small as a single name on some dates (see n column); small-n figures are statistically noisy and shown for illustration only. The decile cohorts are the robust comparison.</p>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · Signal Validation Lab</title>
  <meta name="description" content="Academic-grade research cohort analysis (Fama-French-style decile spectrum, information coefficient, event study) of YUCLAW composite signals. Hypothetical research illustration — not investment advice.">
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
    .panel-title{{font-size:14px;font-weight:700;color:#FFF;margin-bottom:4px}}
    .panel-sub{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}}
    .verdict{{font-size:12.5px;color:#A0AEC0;font-family:JetBrains Mono,monospace;margin:2px 0 14px;padding:8px 12px;background:#11161F;border-radius:6px}}
    .verdict b{{color:#E2E8F0}}
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

    <p style="font-size:14px;color:#A0AEC0;margin-bottom:18px;max-width:820px">
      An academic-grade <strong>decile-cohort study</strong> of YUCLAW's composite signal: a full Fama–French-style
      decile spectrum, per-rebalance <strong>information coefficient</strong>, decile-entry <strong>event studies</strong>,
      a top-minus-bottom spread, and cohort turnover/stability. Cohorts are grouped by composite-score decile or signal
      label and tracked as equal-weighted research cohorts. Derived statistics only — no raw prices. This is descriptive
      research analysis, not portfolio management and not trade advice.
    </p>

    {headline}

    <div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap">
      <div style="flex:1;min-width:240px;background:#11161F;border:1px solid #1E232D;border-left:3px solid #00E676;border-radius:8px;padding:12px 16px">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#00E676;font-weight:700">Panel 1 · Forward (Out-of-Sample) — LOOK-AHEAD-FREE</div>
        <div style="font-size:12px;color:#A0AEC0;margin-top:5px">is_backfill = false · Day 0 = {escape(FORWARD_DAY0.isoformat())} · the honest panel ({fwd_n_td} trading days so far)</div>
      </div>
      <div style="flex:1;min-width:240px;background:#11161F;border:1px solid #1E232D;border-left:3px solid #FBA94B;border-radius:8px;padding:12px 16px">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#FBA94B;font-weight:700">Panel 2 · In-Sample Replay — PARAMETRIC LOOK-AHEAD</div>
        <div style="font-size:12px;color:#A0AEC0;margin-top:5px">is_backfill = true · {ins_n} rebalances · the model's training cutoff overlaps this window → systematically optimistic</div>
      </div>
    </div>

    {sec_decile}
    {sec_ic}
    {sec_event}
    {sec_spread}
    {sec_turn}
    {sec_cum}

    <details class="acc">
      <summary>Methodology summary</summary>
      <div class="acc-body">
        <p>Equal-weighted cohorts, rebalanced at each signal date, ranked by composite <code>total_score</code>; deciles are ~10% (~8 names) of the 79-name universe. Returns are close-to-close from internal <code>price_history</code> (derived statistics only — raw prices never shown). Benchmark: SPY. The information coefficient is the per-rebalance Spearman rank correlation between score and next-period return; the event study resets event time to 0 at each decile entry and averages excess-vs-SPY cumulative return; turnover is the fraction of the top-decile cohort replaced each rebalance. Forward (out-of-sample) and in-sample (parametric look-ahead) panels are never blended. No t-statistics or significance claims are made on the short forward window, and no figure is annualized. Full formal definitions, data windows, and the in-sample look-ahead disclosure are in <a href="methodology/validation_lab.md" style="color:#00E676">methodology/validation_lab.md</a>.</p>
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
