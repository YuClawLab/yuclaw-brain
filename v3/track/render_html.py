"""
Generate the static two-panel page at v3/web/validation.html.

NO JS hydration — data is rendered into the HTML at write time, so a
visitor sees consistent numbers regardless of whether any cron is running
(the v2.3.0 dashboard's silent-freeze incident on May 12 was the lesson
behind this rule).

Style matches the live dashboard (~/yuclaw/docs/index.html): dark bg,
card-style panels, JetBrains Mono numerics, locked compliance footer.
Every hit-rate cell renders its `n` (eligible-row count) inline so a
percentage cannot be quoted out of context.

CLI:
    python3 -m v3.track.render_html
    python3 -m v3.track.render_html --out path/to/file.html
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from v3.cli.validation import COMPLIANCE_FOOTER, POINT_IN_TIME_NOTE
from v3.track.panels import HORIZONS, build_panels

# Default output now lives under docs/ so GitHub Pages can serve it at
# /yuclaw-brain/validation.html. v3/web/validation.html (the development
# output directory) used to be the target but was outside the published
# folder — moving it here fixed the Day-14b launch-gate 404.
OUT_DEFAULT = Path(__file__).resolve().parents[2] / "docs" / "validation.html"

PANEL_HEADERS = {
    "in_sample": "IN-SAMPLE EVENT VALIDATION — Replay",
    "forward":   "FORWARD TRACKING LEDGER — Out-of-Sample",
}

# Threshold below which a panel cell is labelled "preliminary".
SMALL_SAMPLE_N = 20


def _fmt_pct(x: Any, decimals: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x*100:+.{decimals}f}%"


def _fmt_rate(x: Any) -> str:
    if x is None:
        return "—"
    return f"{x*100:.0f}%"




def _calibration_panel() -> str:
    """Label calibration panel (registered protocol; credibility battery,
    2026-08-01): what each classification has historically preceded —
    measured, not promised. Reads the recorded run artifact; renders
    nothing when absent."""
    import json as _json
    from pathlib import Path as _P
    src = _P(__file__).resolve().parents[2] / "output" / "oie" / "label_calibration.json"
    if not src.exists():
        return ""
    d = _json.loads(src.read_text())
    pr = d["primary"]
    rows = []
    for lbl, row in d["table"].items():
        c = row.get("k20") or {}
        cons = c.get("consistency")
        rows.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-size:12px'>{lbl}</td>"
            f"<td style='padding:6px 12px;color:#718096;font-size:11px'>{row['directional']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{row['n']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>"
            f"{(str(round(c['mean_excess']*100,2)) + '%') if c.get('mean_excess') is not None else '—'}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>"
            f"{(format(cons, '.2f')) if cons is not None else '—'}</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{c.get('badge', '—')}</td></tr>")
    seen = set(d["table"])
    absent = [l for l in ("STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
                          "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH",
                          "RISK_ALERT") if l not in seen]
    return f"""
    <div class="card">
      <div class="card-title">Label calibration — what each classification has historically preceded (measured, not promised)</div>
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:10px">
        protocol {d['protocol_id']} · forward ledger only · registered before computation · benchmark-relative outcomes at k=20</div>
      <table>
        <thead><tr><th>Label</th><th>Direction class</th><th>n outcomes</th><th>Mean excess k=20</th><th>Direction consistency</th><th>Badge</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Registered primary: pooled direction-consistency of the directional labels at k=20 =
        <strong style="color:#E2E8F0">{pr['consistency_k20']:.3f}</strong>
        CI ({pr['ci'][0]:.3f}, {pr['ci'][1]:.3f}) [{pr['badge']}] over n={pr['n']} outcomes /
        {pr['n_tickers']} clustered tickers — the interval includes 0.5, so directional meaning is not
        yet demonstrated at this sample; that is the finding, printed as measured. STRONG_BULLISH reads
        anti-consistent at k=20 at current n — also printed as measured; the record accrues daily.
        Labels with no forward outcomes yet: {', '.join(absent) or 'none'}. Non-directional labels carry
        no consistency claim by construction. The score-to-label mapping is fixed thresholds,
        published in <a href="methodology/backfill.md#thresholds" style="color:#00E676">the
        methodology (score-to-label thresholds)</a> — the thresholds carry no outcome promise;
        this panel measures the outcomes. Investment implication: none established — no buy, sell,
        or alpha conclusion is supported by this page.
      </p>
    </div>"""


def _label_color(label: str) -> str:
    if label in ("STRONG_BULLISH", "BULLISH"):
        return "#00E676"
    if label in ("WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH"):
        return "#FF3366"
    return "#A0AEC0"


def _render_panel_table(panel: dict[str, Any]) -> str:
    """One panel's HTML table — per-label rows + overall row."""
    rows_html: list[str] = []
    for lbl in sorted(panel["per_label"]):
        s = panel["per_label"][lbl]
        rows_html.append(_render_row(lbl, s, color=_label_color(lbl)))
    overall = panel["overall"]
    rows_html.append("<tr style='border-top:2px solid #2D3748'>")
    rows_html.append(_render_row("OVERALL", overall, color="#FFF", is_overall=True).removeprefix("<tr>").removesuffix("</tr>"))
    rows_html.append("</tr>")
    return f"""
    <table style='width:100%;border-collapse:collapse'>
      <thead><tr>
        <th>label</th><th>n</th><th>directional</th>
        <th>matured 1d/5d/20d</th>
        <th>hit 1d/5d/20d</th>
        <th>median return 5d</th>
        <th>median excess 5d</th>
      </tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    """


def _fmt_rate_with_n(s: dict[str, Any], n: int) -> str:
    """Hit rate with eligibility n; "preliminary" tag below SMALL_SAMPLE_N."""
    hr = s[f"hit_rate_{n}d"]
    n_elig = s[f"n_eligible_{n}d"]
    if hr is None:
        return "—"
    base = f"{hr*100:.0f}% (n={n_elig})"
    return base + (" prelim" if 0 < n_elig < SMALL_SAMPLE_N else "")


def _render_row(label: str, s: dict[str, Any], color: str, is_overall: bool = False) -> str:
    mat = f"{s['n_matured_1d']}/{s['n_matured_5d']}/{s['n_matured_20d']}"
    hit = " / ".join(_fmt_rate_with_n(s, n) for n in HORIZONS)
    return (
        f"<tr>"
        f"<td style='padding:8px 12px;font-weight:{'700' if is_overall else '600'};color:{color};font-size:13px'>{escape(label)}</td>"
        f"<td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{s['n_signals']}</td>"
        f"<td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{s['n_directional']}</td>"
        f"<td style='padding:8px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{mat}</td>"
        f"<td style='padding:8px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{hit}</td>"
        f"<td style='padding:8px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{_fmt_pct(s.get('median_return_5d'))}</td>"
        f"<td style='padding:8px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{_fmt_pct(s.get('median_excess_5d'))}</td>"
        f"</tr>"
    )


def _render_panel_section(panel_key: str, panel: dict[str, Any], note: str = "",
                          header_extra: str = "", lead_html: str = "") -> str:
    title = PANEL_HEADERS[panel_key]
    date_range = (f"{panel['date_min']} → {panel['date_max']}"
                  if panel["date_min"] else "(no data)")
    note_block = (
        f"<div style='font-size:12px;color:#FBA94B;margin:8px 0 12px 0;'>"
        f"⚠ {escape(note)}</div>") if note else ""
    extra = (f" <span style='font-weight:400;text-transform:none;letter-spacing:0;"
             f"color:#718096;font-family:JetBrains Mono,monospace'>· {escape(header_extra)}"
             f"</span>") if header_extra else ""
    return f"""
    {lead_html}
    <div class='card' style='margin-bottom:24px'>
      <div class='card-title'>{escape(title)}{extra}</div>
      <div style='font-size:12px;color:#A0AEC0;margin-bottom:14px;font-family:JetBrains Mono,monospace'>
        date range {date_range} &nbsp;·&nbsp; total signals {panel['n_total']}
        &nbsp;·&nbsp; directional {panel['overall']['n_directional']}
      </div>
      {note_block}
      <div style='overflow-x:auto'>
        {_render_panel_table(panel)}
      </div>
    </div>
    """


FROZEN_WINDOW_NOTE = (
    "Frozen historical window (2026-02-18 → 2026-05-13) — this regime closed "
    "when forward tracking began and is never updated, by design.")


def render(panels: dict[str, Any]) -> str:
    from v3.web.useful_blocks import site_header_html
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    matured_through = panels["forward"].get("matured_through")
    fwd_extra = f"data through {matured_through}" if matured_through else ""
    frozen_note = (
        f"<div style='font-size:12px;color:#718096;margin:0 0 10px 0;padding:10px 14px;"
        f"background:#10141C;border:1px solid #1E232D;border-radius:8px'>"
        f"{escape(FROZEN_WINDOW_NOTE)}</div>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW — Forward Tracking + In-Sample Validation</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;min-height:100vh}}
    .container{{max-width:1200px;margin:0 auto;padding:20px}}
    .header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding:14px 20px;background:#151A23;border:1px solid #1E232D;border-radius:12px}}
    .logo{{font-size:20px;font-weight:800;color:#FFF}}
    .logo span{{color:#00E676}}
    .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:20px}}
    .card-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#A0AEC0;margin-bottom:8px}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:14px 18px;margin-bottom:24px;font-size:12px;line-height:1.6;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    table th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:9px 12px;text-align:left;border-bottom:1px solid #2D3748}}
    table td{{font-size:13px}}
    table tr:hover td{{background:#1A202C}}
    .footer{{text-align:center;padding:16px;color:#718096;font-size:11px;margin-top:24px}}
    .footer a{{color:#00E676;text-decoration:none}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Forward Tracking + In-Sample Validation", active="validation.html",
                      stamp=f"generated {generated_at}")}

    <div style="font-size:12px;color:#A0AEC0;margin:0 0 16px 0">
      Cohort-level event study: <a href="validation_lab.html"
      style="color:#00E676;text-decoration:none">Validation Lab →</a>
    </div>

    {_calibration_panel()}

    <div class="disclaimer">
      <strong>DISCLAIMER —</strong> {escape(COMPLIANCE_FOOTER)}
    </div>

    {_render_panel_section("forward", panels["forward"], header_extra=fwd_extra)}
    {_render_panel_section("in_sample", panels["in_sample"], note=POINT_IN_TIME_NOTE,
                           lead_html=frozen_note)}

    <div class="card">
      <div class="card-title">METHODOLOGY</div>
      <div style="font-size:12px;color:#A0AEC0;line-height:1.7">
        Full methodology, data sources, limitations, and definitions are documented at
        <a href="https://github.com/YuClawLab/yuclaw-brain/blob/v3.0-evidence/docs/methodology/backfill.md"
           style="color:#00E676;text-decoration:none">docs/methodology/backfill.md</a>.
        Key points: data window is 2026-02-18 to 2026-05-17 (~90 days, all post-Llama 3.1 70B
        training cutoff); in-sample signals were reconstructed via point-in-time replay
        (leak-audited, zero future-event leakage); the Forward Tracking Ledger begins
        2026-05-20 and matures daily — 20-day outcomes mature in mid-June.
      </div>
    </div>

    <div class="disclaimer">
      <strong>DISCLAIMER —</strong> {escape(COMPLIANCE_FOOTER)}
    </div>

    <div class="footer">
      YUCLAW by <a href="https://github.com/YuClawLab">YuClawLab</a> ·
      <a href="index.html">Home</a> ·
      <a href="https://github.com/YuClawLab/yuclaw-brain/blob/v3.0-evidence/docs/methodology/backfill.md">Methodology</a> ·
      MIT
    </div>
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args(argv)

    panels = build_panels()
    html = render(panels)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"[render_html] wrote {out} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
