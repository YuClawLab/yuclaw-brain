"""Render the XLK Covered-Constituent Evidence Lens to docs/xlk_evidence.html.

Second sector lens, activated 2026-07-31 because XLK passed the published
admission standard (EXPLORATORY) — admission-standard-driven expansion.
Every statistic on the page comes from the registered run artifact
(output/oie/xlk_lens_run.json, protocol e5f9e680f402); this renderer
computes nothing. Locked vocabulary; frozen implication line; regenerated
daily by cron/refresh_v3_pages.sh.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import site_header_html, status_block_html

OUT = _REPO / "docs" / "xlk_evidence.html"
SRC = _REPO / "output" / "oie" / "xlk_lens_run.json"

DISCLAIMER = (
    "Hypothetical research illustration. Not investment advice, not "
    "performance advertising, not an offer of any product. Research "
    "classifications, not recommendations. Past results — in-sample or "
    "forward-tracked — do not predict future performance.")
IMPLICATION = ("Investment implication: none established — no buy, sell, or "
               "alpha conclusion is supported by this page.")


def _xlk_robustness() -> str:
    rp = _REPO / "output" / "oie" / "robustness_profile.json"
    if not rp.exists():
        return ""
    d = json.loads(rp.read_text())
    tgt = d.get("xlk")
    if not tgt:
        return ""
    s = tgt["summary"]
    rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{escape(k)}</td>"
        + (f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{v['estimate']:+.2f}%</td>"
           f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({v['ci'][0]:+.2f}, {v['ci'][1]:+.2f})</td>"
           f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(v['badge'])}</td>"
           if v else "<td colspan='3' style='padding:6px 12px;color:#718096;font-size:11px'>empty — SPY history begins 2026-02-02 (own-data rule)</td>")
        + "</tr>"
        for k, v in tgt["cells"].items())
    return f"""
    <div class="panel">
      <div class="panel-title">Context robustness</div>
      <div class="panel-sub">secondary cells under the registered robustness protocol · pre-declared grid</div>
      <table><thead><tr><th>Context cell</th><th>E4 estimate</th><th>Cluster CI</th><th>Badge</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:8px">Sign held {s['sign_held']}/{s['n_computed']}
      (coherence {s['coherence_fraction']}) · breaks: {escape(', '.join(s['breaks']) or 'none')}.
      {escape(IMPLICATION)}</p>
    </div>"""


def render() -> str:
    d = json.loads(SRC.read_text())
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    f, v, a = d["facts"], d["verdict"], d["anatomy"]
    e = d["estimands"]
    order = [("event", "E1 event-weighted"), ("issuer", "E2 issuer-weighted"),
             ("etf", "E3 ETF-weighted"),
             ("capped", "E4 capped-ETF-weighted — PRIMARY")]
    est_rows = []
    for k, desc in order:
        r = e[k]
        tw = r["two_way"]
        hl = " style='background:#1A2334'" if k == "capped" else ""
        est_rows.append(
            f"<tr{hl}><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{desc}</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366;font-weight:700'>{r['mean_pct']:+.2f}%</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B;font-size:11px'>({r['envelope'][0]:+.2f}, {r['envelope'][1]:+.2f})</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-size:11px'>({tw['ci'][0]:+.2f}, {tw['ci'][1]:+.2f})</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")
    fal = d["falsification"]
    geo = d["geometry"]
    top5 = "".join(
        f"<tr><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{s['size']}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{s['mass_pct']}%</td>"
        f"<td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{escape(s['dominant_issuer'])}</td>"
        f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(s['dominant_type'])}</td></tr>"
        for s in geo["top5_stories"])
    lc_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-size:12px'>{escape(et)}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{r['n']}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{r['peak_tau']}</td>"
        f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(r['half_life'])}</td></tr>"
        for et, r in d["lifecycle"].items())
    thin = ", ".join(f"{escape(et)} (n={r['n']})"
                     for et, r in d["lifecycle_thin"].items()) or "none"
    unc_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#A0AEC0;font-size:12px'>{escape(u['reason'])}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{u['weight_pct']:.2f}%</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{u['names']}</td></tr>"
        for u in a["uncovered_by_reason"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · XLK Covered-Constituent Evidence Lens</title>
  <meta name="description" content="Research event study on the YUCLAW-covered share of disclosed XLK weight. Hypothetical research illustration — not investment advice.">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1080px;margin:0 auto;padding:24px}}
    .fresh{{background:#0F1B14;border:1px solid #00E67640;border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:12px;color:#A0AEC0;font-family:JetBrains Mono,monospace}}
    .fresh strong{{color:#00E676}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:12px 16px;margin-bottom:20px;font-size:12px;line-height:1.55;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:4px}}
    .panel-sub{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}}
    table{{width:100%;border-collapse:collapse;margin-top:12px}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:8px 12px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.6px}}
    td{{font-size:13px;border-bottom:1px solid #1A2030}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    .tile{{min-width:120px}}
    .tile .v{{font-size:24px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
    .footer{{text-align:center;padding:18px;color:#718096;font-size:11px}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="XLK Covered-Constituent Evidence Lens", active="xlk_evidence.html")}

    <h1 style="font-size:26px;font-weight:800;color:#FFF;letter-spacing:-0.5px;margin-bottom:4px">
      XLK Covered-Constituent Evidence Lens</h1>
    <p style="font-size:14px;color:#A0AEC0;margin-bottom:16px;max-width:840px">
      Evidence analysis of the YUCLAW-covered {f['covered_weight_pct']}% of disclosed XLK weight.
      This is not a full-fund inference. XLK is the second sector lens: it was activated because it
      passed the published admission standard — not because of popularity.</p>

    <div class="fresh"><strong>Registered run</strong> · protocol <code>{escape(d['protocol_id'])}</code> ·
      holdings as of {escape(d['holdings']['as_of'])} · last build {escape(built)}</div>

    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}</div>

    <div class="panel">
      <div class="panel-title">Admission and coverage</div>
      <div class="panel-sub">issuer holdings snapshot ∩ 79-ticker scoring universe · admission per the published standard</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v" style="font-size:16px;color:#4DD0E1">{escape(v['label'])}</div><div class="k">admission verdict</div></div>
        <div class="tile"><div class="v">{v['effective_issuers']}</div><div class="k">effective issuers</div></div>
        <div class="tile"><div class="v">{f['covered_issuers']}/{d['holdings']['n_holdings']}</div><div class="k">holdings covered</div></div>
        <div class="tile"><div class="v">{f['covered_weight_pct']}%</div><div class="k">of fund weight covered</div></div>
      </div>
      <p style="font-size:12px;color:#A0AEC0">Top-1 covered {a['top1_covered_pct']}% · top-3 {a['top3_covered_pct']}% · top-5 {a['top5_covered_pct']}% of full-fund weight (largest: {escape(a['largest_covered'][0])}).</p>
      <table><thead><tr><th>Uncovered — reason</th><th>Weight</th><th>Names</th></tr></thead><tbody>{unc_rows}</tbody></table>
    </div>

    <div class="panel">
      <div class="panel-title">Multi-estimand direction-aligned CAR at τ=+20 · backfill era</div>
      <div class="panel-sub">n={d['n_events_backfill']} events · conservative envelope AND formal two-way, side by side · all-era n={d['n_events_all']} disclosed</div>
      <table>
        <thead><tr><th>Estimand</th><th>Mean CAR</th><th>Conservative envelope</th><th>Formal two-way CI (CGM)</th><th>Badge</th></tr></thead>
        <tbody>{''.join(est_rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Falsification (registered secondaries): event-date-shuffle percentile
        {fal['date_shuffle']['percentile_in_null']:.3f}; direction sign-flip percentile
        {fal['sign_flip']['percentile_in_null']:.3f}; pre-event placebo {fal['placebo_minus20d']['value_pct']:+.2f}%.
        Extremity is read two-sided. The sign-flip result is extreme while the date-shuffle result is not —
        the adverse alignment survives direction randomization, but an era-generic component cannot be
        excluded at this sample. Reported as measured. {escape(IMPLICATION)}
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">Evidence structure</div>
      <div class="panel-sub">story clustering (pre-committed linkage) · effective evidence count</div>
      <p style="font-size:12px;color:#A0AEC0">{geo['n_events']} events → {geo['n_stories']} stories →
        <strong style="color:#E2E8F0">{geo['n_eff_story']} effective</strong> (design effect {geo['deff_story']};
        issuer-level {geo['n_eff_issuer']}). Top story {geo['top_story_share_pct']}% of event mass.
        Many events, fewer stories — statistics on this page use cluster-aware inference accordingly.</p>
      <table><thead><tr><th>Story size</th><th>Mass</th><th>Dominant issuer</th><th>Dominant type</th></tr></thead><tbody>{top5}</tbody></table>
    </div>

    <div class="panel">
      <div class="panel-title">Evidence lifecycle</div>
      <div class="panel-sub">per-type |CAR| paths day 0→20 · backfill era · n≥15 floor</div>
      <table><thead><tr><th>Event type</th><th>n</th><th>Peak day</th><th>Half-life</th></tr></thead><tbody>{lc_rows}</tbody></table>
      <p style="font-size:11px;color:#718096;margin-top:8px">An absolute cumulative path rises mechanically
        with horizon — a window-edge peak with no half-life is what no-decay looks like under this estimator.
        Below the floor, listed not plotted: {thin}. {escape(IMPLICATION)}</p>
    </div>

    {_xlk_robustness()}

    {status_block_html()}

    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}</div>
    <div class="footer">YUCLAW XLK Covered-Constituent Evidence Lens · built {escape(built)} ·
      <a href="https://github.com/YuClawLab/yuclaw-brain" style="color:#00E676">YuClawLab</a> · research &amp; education only</div>
  </div>
</body>
</html>
"""


def main() -> int:
    html = render()
    OUT.write_text(html)
    print(f"[render_xlk_evidence] wrote {OUT} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
