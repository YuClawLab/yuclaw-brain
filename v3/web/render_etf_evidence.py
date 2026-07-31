"""Render the SMH Covered-Constituent Evidence Lens page to docs/etf_evidence.html.

Static, data-baked, self-contained (inline SVG, no JS/CDNs). RESEARCH framing
throughout: evidence posture + event-study CARs on SMH-class semiconductor
constituents that are EDGAR filers in YUCLAW's universe. Locked vocabulary,
derived statistics only, no directive language. Regenerated daily by
cron/refresh_v3_pages.sh with the same freshness stamp as the Validation Lab.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.lab.etf_evidence import SMH_AS_OF, compute_all
from v3.web import oie_v51_blocks as _v51
from v3.web.useful_blocks import (site_header_html,
                                  packet_block_from_manifest as _packet_block,
                                  public_label as display_label,
                                  status_block_html as _shared_status_block,
                                  use_in_research_html as _use_in_research)

# Signal labels render VERBATIM from the locked public vocabulary
# (useful_blocks.PUBLIC_LABELS — the homepage legend). The previous
# display-layer remap ("POSITIVE_RESEARCH+", "RISK_FLAG (…)") invented
# labels outside the locked set and was removed per the 2026-07-26 label audit.

OUT = _REPO / "docs" / "etf_evidence.html"

DISCLAIMER_FULL = (
    "Hypothetical research illustration. Not investment advice, not performance "
    "advertising, not an offer of any product. Research classifications, not "
    "recommendations. Past results — in-sample or forward-tracked — do not "
    "predict future performance."
)
DISCLAIMER_LINE = (
    "Research event-study analysis — hypothetical illustration, not investment "
    "advice, not performance advertising. Classifications, not recommendations."
)


def _pct(x, digits=2):
    return f"{x*100:+.{digits}f}%" if x is not None else "—"


def car_chart(curve: dict, title: str, color: str = "#4DD0E1",
              spy_curve: dict | None = None, width=900, height=360) -> str:
    """Mean CAR path with 95% CI band; x-axis = event-time trading days.
    Optionally overlays the SPY-model mean as a dashed reference."""
    pts = curve["points"]
    if not pts:
        return "<p style='color:#718096;font-size:12px'>No evaluable events.</p>"
    pad_l, pad_r, pad_t, pad_b = 60, 210, 26, 46
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    ys = [p["mean_car"] for p in pts] + [0.0]
    ys += [p["ci_lo"] for p in pts if p["ci_lo"] is not None]
    ys += [p["ci_hi"] for p in pts if p["ci_hi"] is not None]
    if spy_curve and spy_curve["points"]:
        ys += [p["mean_car"] for p in spy_curve["points"]]
    ymin, ymax = min(ys), max(ys)
    if ymax == ymin:
        ymax += 0.01
    yr = ymax - ymin
    taus = [p["tau"] for p in pts]
    tmin, tmax = min(taus), max(taus)

    def X(tau): return pad_l + (tau - tmin) / (tmax - tmin or 1) * plot_w
    def Y(v): return pad_t + (ymax - v) / yr * plot_h

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="background:#0B0E14;border:1px solid #1E232D;border-radius:8px" '
             f'role="img" aria-label="{escape(title)}">']
    # zero line + event-day marker
    parts.append(f'<line x1="{pad_l}" y1="{Y(0):.1f}" x2="{pad_l+plot_w}" y2="{Y(0):.1f}" '
                 f'stroke="#2D3748" stroke-dasharray="3,3"/>')
    if Y(0) > pad_t + 60:  # skip the right-side 0% label when it would collide with the legend
        parts.append(f'<text x="{pad_l+plot_w+6}" y="{Y(0)+4:.1f}" fill="#718096" font-size="10" '
                     f'font-family="JetBrains Mono,monospace">0%</text>')
    parts.append(f'<line x1="{X(0):.1f}" y1="{pad_t}" x2="{X(0):.1f}" y2="{pad_t+plot_h}" '
                 f'stroke="#4A5568" stroke-dasharray="5,4"/>')
    parts.append(f'<text x="{X(0):.1f}" y="{pad_t-8}" fill="#A0AEC0" font-size="10" '
                 f'text-anchor="middle" font-family="JetBrains Mono,monospace">event day 0</text>')
    for cv in (ymin, ymax):
        parts.append(f'<text x="6" y="{Y(cv)+4:.1f}" fill="#718096" font-size="10" '
                     f'font-family="JetBrains Mono,monospace">{cv*100:+.1f}%</text>')
    # x ticks every 5 event days
    ax_y = pad_t + plot_h
    parts.append(f'<line x1="{pad_l}" y1="{ax_y}" x2="{pad_l+plot_w}" y2="{ax_y}" stroke="#2D3748"/>')
    for tau in range(tmin, tmax + 1, 5):
        parts.append(f'<line x1="{X(tau):.1f}" y1="{ax_y}" x2="{X(tau):.1f}" y2="{ax_y+5}" stroke="#2D3748"/>')
        parts.append(f'<text x="{X(tau):.1f}" y="{ax_y+18}" fill="#718096" font-size="10" '
                     f'text-anchor="middle" font-family="JetBrains Mono,monospace">{tau:+d}</text>')
    parts.append(f'<text x="{pad_l+plot_w/2:.0f}" y="{ax_y+34}" fill="#718096" font-size="10" '
                 f'text-anchor="middle" font-family="Inter,sans-serif">event-time trading days (τ)</text>')
    # CI band
    band = [p for p in pts if p["ci_lo"] is not None]
    if band:
        top_path = " ".join(f"{X(p['tau']):.1f},{Y(p['ci_hi']):.1f}" for p in band)
        bot_path = " ".join(f"{X(p['tau']):.1f},{Y(p['ci_lo']):.1f}" for p in reversed(band))
        parts.append(f'<polygon points="{top_path} {bot_path}" fill="{color}" opacity="0.16"/>')
    # SPY-model dashed reference
    ly = pad_t + 6
    if spy_curve and spy_curve["points"]:
        sp = " ".join(f"{X(p['tau']):.1f},{Y(p['mean_car']):.1f}" for p in spy_curve["points"])
        parts.append(f'<polyline points="{sp}" fill="none" stroke="#A0AEC0" stroke-width="2" '
                     f'stroke-dasharray="7,4"/>')
        last = spy_curve["points"][-1]
        parts.append(f'<line x1="{pad_l+plot_w+14}" y1="{ly+18}" x2="{pad_l+plot_w+30}" y2="{ly+18}" '
                     f'stroke="#A0AEC0" stroke-width="3" stroke-dasharray="7,4"/>')
        parts.append(f'<text x="{pad_l+plot_w+34}" y="{ly+22}" fill="#E2E8F0" font-size="10" '
                     f'font-family="JetBrains Mono,monospace">SPY model {last["mean_car"]*100:+.1f}%</text>')
    # mean line (peer model)
    mp = " ".join(f"{X(p['tau']):.1f},{Y(p['mean_car']):.1f}" for p in pts)
    parts.append(f'<polyline points="{mp}" fill="none" stroke="{color}" stroke-width="2.5"/>')
    last = pts[-1]
    parts.append(f'<line x1="{pad_l+plot_w+14}" y1="{ly}" x2="{pad_l+plot_w+30}" y2="{ly}" '
                 f'stroke="{color}" stroke-width="3"/>')
    parts.append(f'<text x="{pad_l+plot_w+34}" y="{ly+4}" fill="#E2E8F0" font-size="10" '
                 f'font-family="JetBrains Mono,monospace">peer model {last["mean_car"]*100:+.1f}%</text>')
    # n annotations
    n_by_tau = {p["tau"]: p["n"] for p in pts}
    ann = ", ".join(f"n(τ={t:+d})={n_by_tau[t]}" for t in (0, 10, 20) if t in n_by_tau)
    parts.append(f'<text x="{pad_l+plot_w+14}" y="{ly+40}" fill="#718096" font-size="9" '
                 f'font-family="JetBrains Mono,monospace">{escape(ann)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def render() -> str:
    data = compute_all()
    ru, es = data["rollup"], data["event_study"]
    ov = ru["overlap"]
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data_through = es["price_coverage"][1] if es["price_coverage"] else "—"

    member_rows = []
    for m in ru["members"]:
        ev_summary = ", ".join(f"{et}×{v['total']}" for et, v in
                               sorted(m["events"].items(), key=lambda kv: -kv[1]["total"])) or "—"
        member_rows.append(
            f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(m['ticker'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['weight_pct']:.2f}%</td>"
            f"<td style='padding:7px 12px;color:#4DD0E1;font-size:12px'>{escape(display_label(m['label']))}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['score']:+.3f}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['c6']:+.3f}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:12px'>{escape(m['grade'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-size:11px'>{escape(ev_summary)}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{m['events_30d']}</td></tr>")

    pooled = es["pooled_directional_backfill"]
    pooled_chart = car_chart(pooled["peer"],
                             "Direction-aligned CAR, backfill-era events (peer model, 95% CI)",
                             color="#7C4DFF", spy_curve=pooled["spy"])
    ins_chart = car_chart(es["by_type"]["INSIDER_SELL"]["peer"],
                          "INSIDER_SELL mean CAR (peer model, 95% CI)",
                          color="#FBA94B", spy_curve=es["by_type"]["INSIDER_SELL"]["spy"])
    mna = es["by_type"].get("M_AND_A_CLOSE")
    mna_chart = car_chart(mna["peer"], "M_AND_A_CLOSE mean CAR (peer model, 95% CI)",
                          color="#4DD0E1", spy_curve=mna["spy"]) if mna else ""

    def car_end(curve):
        return curve["points"][-1] if curve["points"] else None

    type_rows = []
    for et, c in es["by_type"].items():
        pe, se = car_end(c["peer"]), car_end(c["spy"])
        if pe is None:
            continue
        ci = (f"({_pct(pe['ci_lo'],1)}, {_pct(pe['ci_hi'],1)})"
              if pe["ci_lo"] is not None else "n too small for CI")
        type_rows.append(
            f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px;font-family:JetBrains Mono,monospace'>{escape(et)}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{c['peer']['n_events']}</td>"
            f"<td style='padding:7px 12px;color:#4DD0E1;font-family:JetBrains Mono,monospace'>{_pct(pe['mean_car'],1)}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace;font-size:11px'>{ci}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{_pct(se['mean_car'],1) if se else '—'}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{pe['n']}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-size:11px'>{escape(c['date_range'][0])} → {escape(c['date_range'][1])}</td></tr>")

    live = es["pooled_directional_live"]
    live_n = live["peer"]["n_events"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · SMH Covered-Constituent Evidence Lens</title>
  <meta name="description" content="Research event study: EDGAR evidence events on the YUCLAW-covered share of disclosed SMH weight. Hypothetical research illustration — not investment advice.">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1080px;margin:0 auto;padding:24px}}
    .header{{margin-bottom:16px;padding:18px 24px;background:#151A23;border:1px solid #1E232D;border-radius:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
    .logo{{font-size:20px;font-weight:800;color:#FFF;letter-spacing:-0.3px;text-decoration:none}}
    a.logo:hover{{color:#00E676}}
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
    .tile{{min-width:130px}}
    .tile .v{{font-size:24px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="SMH Covered-Constituent Evidence Lens", active="etf_evidence.html")}

    <h1 style="font-size:26px;font-weight:800;color:#FFF;letter-spacing:-0.5px;margin-bottom:4px">
      SMH Covered-Constituent Evidence Lens</h1>
    <p style="font-size:14px;color:#A0AEC0;margin-bottom:16px;max-width:820px">
      Evidence analysis of the YUCLAW-covered {ov['covered_weight_pct']}% of disclosed SMH weight.
      This is not a full-fund inference.</p>

    <div class="fresh">
      <strong>Data through {escape(data_through)}</strong> (last completed U.S. trading day) ·
      regenerated daily after market close · last build {escape(built)}
    </div>

    <div class="disclaimer-line">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}
    </div>

    <p style="font-size:14px;color:#A0AEC0;margin-bottom:18px;max-width:820px">
      Does SEC-filing evidence on semiconductor-theme constituents carry information that
      <em>precedes</em> full price adjustment? This module aggregates YUCLAW's evidence stream
      to the theme level and tests the question as a classic <strong>event study</strong> —
      cumulative abnormal returns (CAR) around evidence events, with the sector factor removed
      by a peer-benchmark model. The result below is reported exactly as measured, including
      where it is adverse to the hypothesis.
      <span style="color:#718096;font-size:12px;display:block;margin-top:6px">
      Scope note: this is research on the SEC-filing <em>constituents</em> of a published index
      fund's holdings list — an evidence study of companies, not analysis, promotion, or an
      offering of any fund or product.</span>
    </p>

    <div class="panel">
      <div class="panel-title">Theme coverage · SMH (VanEck Semiconductor ETF)</div>
      <div class="panel-sub">constituents as of {escape(SMH_AS_OF)} (issuer fund disclosure) · coverage = constituents ∩ YUCLAW 79-ticker universe</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v">{ov['n_covered']}/{ov['n_holdings_disclosed']}</div><div class="k">disclosed holdings covered</div></div>
        <div class="tile"><div class="v">{ov['covered_weight_pct']}%</div><div class="k">of fund weight covered</div></div>
        <div class="tile"><div class="v">{ru['rollup']['events_total']}</div><div class="k">accepted evidence events (filings)</div></div>
        <div class="tile"><div class="v">{ru['rollup']['events_30d']}</div><div class="k">events, trailing 30 days</div></div>
      </div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.6;max-width:820px">
        <strong style="color:#E2E8F0">Why not 100%?</strong> {len(ov['uncovered'])} disclosed constituents remain
        outside the covered sleeve — all of them US filers outside the 79-ticker scoring universe (a
        scoring-universe decision, not a filer-class gap). The foreign private issuers
        {', '.join(ov.get('covered_via_evidence_tier', []))} are covered as of 2026-07-31 through the
        evidence tier (6-K current reports + 20-F annual reports, exhibit-level prose extraction — the
        same path shipped for the
        <a href="canada_resources.html" style="color:#00E676">Canada Resources Evidence</a> vertical);
        they are evidence coverage only and are never scored.
        <strong style="color:#E2E8F0">Foreign-holdings ETFs (e.g. KORU-class country funds) remain
        methodologically out of scope</strong>: their constituents do not file with EDGAR at all, so there is
        no evidence stream to aggregate — a scope statement, not a caveat.
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">Current evidence posture · covered constituents</div>
      <div class="panel-sub">latest signal snapshots as of {escape(ru['rollup']['as_of'] or '—')} · weighted by SMH weight (renormalized over the covered {ov['covered_weight_pct']}%)</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v">{ru['rollup']['weighted_score']:+.3f}</div><div class="k">weighted composite score</div></div>
        <div class="tile"><div class="v">{ru['rollup']['weighted_c6']:+.3f}</div><div class="k">weighted C6 (evidence/risk channel)</div></div>
      </div>
      <table>
        <thead><tr><th>Ticker</th><th>SMH weight</th><th>Signal label</th><th>Composite score</th><th>C6</th><th>Evidence grade</th><th>Event history (type×count)</th><th>30d</th></tr></thead>
        <tbody>{''.join(member_rows)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">Research classifications, not recommendations. C6 is the evidence-impact component of the composite score; the earlier C6 finding is that insider-sale evidence may function more plausibly as a <em>risk-state input</em> than a near-term directional signal (see methodology).</p>
    </div>

    <div class="panel">
      <div class="panel-title">Event study · does evidence detection precede price adjustment?<span class="caveat-tag">ADVERSE RESULT SHOWN AS MEASURED</span></div>
      <div class="panel-sub">market-model CAR, window [−5, +20] event-time days · dedup: {es['n_raw_filings']} filings → {es['n_events_deduped']} distinct (ticker, type, day) events → {es['n_events_used']} with a ≥30-obs estimation window</div>

      <div style="background:#2A1A1A;border-radius:8px;padding:14px 18px;border-left:3px solid #FBA94B;margin-bottom:14px">
        <div style="color:#FBA94B;font-weight:700;font-size:13px">Headline finding (backfill era, Feb 18 – May 15): adverse under the event-level estimator; issuer- and date-clustered confirmation completed — the adverse point estimate persists under all four registered weightings but is statistically supported only under event weighting (issuer-, ETF-, and capped-weighted envelopes include zero). The event-date-shuffle null places the primary capped estimand at an unremarkable percentile: era-generic direction alignment, not event-timed information.</div>
        <p style="font-size:12px;color:#A0AEC0;margin-top:6px;line-height:1.55">
          Direction-aligned pooled CAR (peer model, n={pooled['peer']['n_events']} events) is
          <strong style="color:#FF3366">{_pct(car_end(pooled['peer'])['mean_car'],1)}</strong> at τ=+20
          (95% CI {_pct(car_end(pooled['peer'])['ci_lo'],1)} to {_pct(car_end(pooled['peer'])['ci_hi'],1)})
          — <em>negative</em> under this event-level estimator: prices moved against the evidence
          direction. The sample is dominated by INSIDER_SELL clusters during a sector melt-up (insiders
          sold the strongest names, which kept outperforming peers). This is consistent with the earlier
          C6 finding that insider-sale evidence may function more plausibly as a risk-state input than a
          near-term directional signal. Live-detected events since forward Day 0:
          n={live_n} directional — far too few for inference; this panel accrues with the live record.
        </p>
      </div>

      <div style="background:#151A23;border:1px solid #2D3748;border-radius:8px;padding:12px 16px;margin-bottom:14px">
        <div style="color:#A0AEC0;font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:5px">How to read direction alignment</div>
        <p style="font-size:12px;color:#A0AEC0;line-height:1.55">
          Each event's abnormal return is multiplied by its evidence direction (+1 for accumulation-type
          evidence, −1 for disposal-type evidence such as INSIDER_SELL). Because INSIDER_SELL events carry
          direction −1, a <em>positive</em> unsigned CAR after insider sales — visible in the INSIDER_SELL
          panel below — enters this pooled series with a <em>negative</em> sign. The adverse pooled result
          is therefore largely a restatement of the same unsigned fact: covered names continued to move up
          relative to peers after insider sales. It is evidence against the directional-sell hypothesis at
          this sample, not evidence of a price decline.
        </p>
      </div>

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:6px 0 8px">Direction-aligned pooled CAR · backfill era · n={pooled['peer']['n_events']}</div>
      {pooled_chart}

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:18px 0 8px">INSIDER_SELL mean CAR (unsigned) · n={es['by_type']['INSIDER_SELL']['peer']['n_events']}</div>
      {ins_chart}

      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:18px 0 8px">M_AND_A_CLOSE mean CAR (unsigned) · n={mna['peer']['n_events'] if mna else 0} <span style="color:#FBA94B">⚠ small n — illustrative</span></div>
      {mna_chart}

      <table>
        <thead><tr><th>Event type</th><th>n events</th><th>Peer-model CAR τ=+20</th><th>95% CI</th><th>SPY-model CAR τ=+20</th><th>n @ τ=+20</th><th>Event window</th></tr></thead>
        <tbody>{''.join(type_rows)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:10px">
        CIs assume independent events; distinct ticker-days can still share calendar days across tickers,
        so the intervals are optimistic — stated, not hidden. Types with n &lt; 10 are shown for completeness
        and are statistically uninformative. {escape(es['insider_stream_note'])}
      </p>
    </div>

    {_v51.smh_estimand_panel()}

    {_v51.falsification_panel("SMH-E4")}

    {_v51.taxonomy_panel("SMH")}

    {_v51.smh_funnel_panel()}

    {_v51.smh_holdings_panel()}

    {_v51.fields_review_panels()}

    <details class="acc">
      <summary>Methodology summary</summary>
      <div class="acc-body">
        <p style="margin-bottom:8px">
          <strong>Events:</strong> accepted L1 evidence events on covered constituents, deduplicated to one
          observation per (ticker, event type, direction, day). <strong>Day 0</strong> = first trading day on/after
          the event timestamp's date. <strong>Abnormal returns:</strong> two models, never averaged —
          <em>peer model</em> (market = equal-weight of the other covered constituents that day; removes the
          sector factor; the fair test) and <em>SPY market model</em> (classic; in a strong sector regime its
          "abnormal" return is dominated by the sector factor, which is what it shows). Estimation: up to 60
          trading days ending 6 days pre-event, minimum 30 observations ({es['skipped_insufficient_estimation']} events skipped for
          insufficient estimation history — early-window events; count disclosed). CAR window [−5, +20];
          mean CAR with a normal-approximation 95% CI across events; n disclosed at every horizon.
          <strong>Direction alignment:</strong> AR × direction for direction ≠ 0 events, so "evidence direction
          predicts abnormal return" is a positive number if true.
        </p>
        <p>
          Backfill-era events (before forward Day 0 = 2026-05-18) were extracted retrospectively and carry the
          same parametric look-ahead disclosure as the in-sample panel of the Validation Lab; live-era events
          are detected in real time. The two eras are never blended. Derived statistics only — no raw prices.
          Constituent weights are issuer fund disclosures as of {escape(SMH_AS_OF)}.
        </p>
      </div>
    </details>

    {_packet_block("open_index")}

    {_use_in_research("packets/yuclaw_open_index_evidence_packet.zip")}

    {_shared_status_block()}

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW SMH Covered-Constituent Evidence Lens · data through {escape(data_through)} · built {escape(built)} · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
</body>
</html>
"""


def main() -> int:
    html = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"[render_etf_evidence] wrote {OUT} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
