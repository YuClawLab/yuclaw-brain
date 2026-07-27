"""
Render the YUCLAW v5.0.0 public landing page to docs/index.html.

Static, data-baked, NO JS hydration — the v2.3.0 silent-freeze lesson.

The landing page is the FACE of the project at https://yuclawlab.github.io/yuclaw-brain/.
v4.1 layout (friends' feedback: lead with the data, collapse the prose):
  - Minimal header: logo + version badge + nav
  - Minimal hero: one-line tagline + install line (no dense paragraph up top)
  - One-line disclaimer, ALWAYS visible (no click required)
  - "Current signals" table — the HERO, directly under the header
  - Public signal vocabulary legend (label compliance, kept visible)
  - "How it works" — four bullets, in a collapsed <details> accordion
  - "Full disclaimer & methodology" — the full DISCLAIMER (verbatim) plus the
    descriptive methodology paragraph, in a collapsed <details> accordion
  - Install card + footer
  - Links to validation page, GitHub, PyPI, ledger, REST API

All compliance text is preserved verbatim — only relocated, never deleted.
Accordions use native <details>/<summary> (no JS, GitHub-Pages-safe, accessible).
No performance numbers anywhere on the homepage. None.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "index.html"

DB_DSN = "dbname=yuclaw_events"

# Locked sentiment vocabulary — anything outside this set on the homepage is a
# bug. Single source: useful_blocks.PUBLIC_LABELS (shared by every renderer).
from v3.web.useful_blocks import PUBLIC_LABELS  # noqa: E402

# Canonical compliance notice — MUST stay byte-identical to
# v4/api/schema.py::COMPLIANCE_NOTICE (single source of truth, v4 Day 9/Q5).
COMPLIANCE_NOTICE = (
    "YUCLAW research output. Not investment advice. "
    "Past performance does not guarantee future results. "
    "Signal labels are research classifications, not buy/sell recommendations."
)

# The rendered disclaimer is the canonical notice PLUS the dashboard's extra
# protective sentences (registered-adviser + forward-tracked caveats). It must
# never be weaker than the canonical notice — only additive.
DISCLAIMER = (
    COMPLIANCE_NOTICE + " "
    "YUCLAW is not a registered investment adviser. "
    "Past results — in-sample or forward-tracked — do not predict future performance."
)


def _label_color(label: str) -> str:
    if label in ("STRONG_BULLISH", "BULLISH"):
        return "#00E676"
    if label in ("WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH"):
        return "#FF3366"
    if label == "RISK_ALERT":
        return "#FBA94B"
    return "#A0AEC0"


def _fetch_current_signals() -> tuple[list[dict[str, Any]], datetime | None]:
    """Latest OOS snapshot per ticker, sorted by absolute score desc."""
    with psycopg2.connect(DB_DSN) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (ticker)
                ticker, signal_label, total_score, signal_time
            FROM signal_snapshots
            WHERE is_backfill = false
            ORDER BY ticker, signal_time DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        return [], None
    rows.sort(key=lambda r: abs(float(r["total_score"])), reverse=True)
    as_of = max(r["signal_time"] for r in rows)
    return rows, as_of


def _row_html(r: dict[str, Any]) -> str:
    label = r["signal_label"]
    if label not in PUBLIC_LABELS:
        # Defensive — never serve a non-public label.
        label = "(?)"
    color = _label_color(label)
    score = float(r["total_score"])
    score_color = "#00E676" if score > 0 else ("#FF3366" if score < 0 else "#A0AEC0")
    return (
        f"<tr>"
        f"<td style='padding:9px 14px;font-weight:600;color:#FFF;font-size:13px'>{escape(r['ticker'])}</td>"
        f"<td style='padding:9px 14px'>"
        f"<span style='background:{color}26;color:{color};border:1px solid {color}80;"
        f"padding:3px 10px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:0.5px'>"
        f"{escape(label)}</span></td>"
        f"<td style='padding:9px 14px;color:{score_color};font-weight:600;"
        f"font-family:JetBrains Mono,monospace;font-size:13px'>{score:+.3f}</td>"
        f"</tr>"
    )


def render(rows: list[dict[str, Any]], as_of: datetime | None) -> str:
    from v3.web.useful_blocks import (site_header_html, status_block_html,
                                      use_in_research_html)
    rebuilt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    as_of_str = as_of.strftime("%Y-%m-%d %H:%M UTC") if as_of else "no signals yet"
    table_body = "".join(_row_html(r) for r in rows) or (
        "<tr><td colspan='3' style='padding:14px;color:#718096;font-style:italic'>"
        "Forward Tracking Ledger Day 0 — first signals materialize at 17:00 MDT cron."
        "</td></tr>")
    use_research_block = use_in_research_html(None, guide_link=True)
    status_block = status_block_html()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <title>YUCLAW v5.0.0 — Evidence-First Financial AI</title>
  <meta name="description" content="Open-source evidence-first financial research platform. Composite signals tied to SEC filings, time-machine replay, hash-anchored Verified Research Ledger. Agent Research API · MCP · LangChain/LlamaIndex. Research only — not investment advice.">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1100px;margin:0 auto;padding:24px}}
    .header{{margin-bottom:18px;padding:18px 24px;background:#151A23;border:1px solid #1E232D;border-radius:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
    .logo{{font-size:22px;font-weight:800;color:#FFF;letter-spacing:-0.3px}}
    .logo span{{color:#00E676}}
    .ver{{display:inline-block;background:#00E67620;color:#00E676;border:1px solid #00E67680;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:700;margin-left:8px;letter-spacing:0.5px;font-family:JetBrains Mono,monospace}}
    .features{{margin-top:12px;font-family:JetBrains Mono,monospace;font-size:12px;color:#00E676;letter-spacing:0.3px}}
    .features span{{color:#718096}}
    .navlinks a{{color:#A0AEC0;text-decoration:none;font-size:13px;padding:5px 11px;border-radius:6px;background:#1E232D;margin-left:6px}}
    .navlinks a:hover{{color:#00E676}}
    .hero-min{{padding:26px 24px;background:linear-gradient(135deg,#151A23,#1A2334);border:1px solid #1E232D;border-radius:12px;margin-bottom:16px}}
    .hero-min h1{{font-size:30px;font-weight:800;color:#FFF;margin-bottom:6px;letter-spacing:-1px}}
    .tagline{{font-size:15px;color:#A0AEC0}}
    .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:22px;font-size:12px;line-height:1.55;color:#A0AEC0}}
    .disclaimer-line strong{{color:#FBA94B}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:14px 18px;font-size:12px;line-height:1.55;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .card-title{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:#A0AEC0;margin-bottom:14px}}
    .acc{{background:#151A23;border:1px solid #1E232D;border-radius:12px;margin-bottom:20px;overflow:hidden}}
    .acc>summary{{list-style:none;cursor:pointer;padding:18px 22px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:#A0AEC0;display:flex;align-items:center;gap:10px;user-select:none}}
    .acc>summary::-webkit-details-marker{{display:none}}
    .acc>summary::before{{content:"▸";color:#00E676;font-size:12px}}
    .acc[open]>summary::before{{content:"▾"}}
    .acc>summary:hover{{color:#00E676}}
    .acc-body{{padding:0 22px 22px}}
    .bullets{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}
    .bullet{{background:#1A2030;border-radius:8px;padding:14px 16px}}
    .bullet h3{{font-size:13px;font-weight:700;color:#00E676;margin-bottom:5px;font-family:JetBrains Mono,monospace}}
    .bullet p{{font-size:13px;color:#A0AEC0;line-height:1.55}}
    .method-para{{font-size:14px;color:#A0AEC0;max-width:760px;margin-bottom:16px}}
    table{{width:100%;border-collapse:collapse}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:9px 14px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.8px}}
    td{{font-size:13px}}
    tr:hover td{{background:#1A202C}}
    .as-of{{font-size:11px;color:#718096;font-family:JetBrains Mono,monospace;margin-top:10px;text-align:right}}
    .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:24px}}
    .footer a{{color:#00E676;text-decoration:none}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    @media(max-width:640px){{.bullets{{grid-template-columns:1fr}}.hero-min h1{{font-size:24px}}}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(active="index.html")}

    <div class="hero-min">
      <h1>Evidence-First Financial AI</h1>
      <p class="tagline">Every signal traces to a real SEC filing.</p>
      <div class="features">Agent Research API <span>·</span> MCP <span>·</span> LangChain/LlamaIndex <span>·</span> pip install yuclaw</div>
    </div>

    <div class="disclaimer-line">
      <strong>Disclaimer —</strong> Research &amp; education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations.
    </div>

    <div class="card">
      <div class="card-title">Current signals — Forward Tracking Ledger</div>
      <table>
        <caption style="caption-side:top;text-align:left;font-size:12px;color:#A0AEC0;padding:0 0 10px">
          Current research classifications — not recommendations</caption>
        <thead>
          <tr><th>Ticker</th><th>Signal label</th>
          <th title="Composite research score — not an expected return, a probability, a price target, or a recommendation.">Score
          <span aria-hidden="true" style="cursor:help;color:#718096">ⓘ</span></th></tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Score = composite research score. It is not an expected return, a probability,
        a price target, or a recommendation.</p>
      <div class="as-of">data as of {escape(as_of_str)} · landing page rebuilt {escape(rebuilt)}</div>
    </div>

    <div class="card">
      <div class="card-title">Public signal vocabulary</div>
      <p style="font-size:13px;color:#A0AEC0;margin-bottom:8px">
        Labels are research classifications, not buy/sell recommendations:
      </p>
      <p style="font-family:JetBrains Mono,monospace;font-size:12px;color:#E2E8F0;line-height:1.9">
        <span style="color:#00E676">STRONG_BULLISH</span> ·
        <span style="color:#00E676">BULLISH</span> ·
        <span style="color:#A0AEC0">NEUTRAL</span> ·
        <span style="color:#A0AEC0">WATCH</span> ·
        <span style="color:#FF3366">WEAKENING</span> ·
        <span style="color:#FF3366">NEGATIVE_EVENT</span> ·
        <span style="color:#FF3366">BEARISH_WATCH</span> ·
        <span style="color:#FBA94B">RISK_ALERT</span>
      </p>
      <p style="font-size:12px;color:#718096;margin-top:10px">
        There is no <code>SELL</code> or <code>SHORT</code> label.
        The SDK's <code>_validate_label()</code> is invoked on every signal-bearing return.
      </p>
    </div>

    <details class="acc">
      <summary>How it works</summary>
      <div class="acc-body">
        <div class="bullets">
          <div class="bullet">
            <h3>1 · Evidence layer</h3>
            <p>SEC EDGAR filings (Form 4, 8-K, 10-Q, 10-K, 6-K, 40-F) are extracted with a local Llama 3.1 70B model. A deterministic SourceLock Guard validates every extraction against the source text before any signal sees it.</p>
          </div>
          <div class="bullet">
            <h3>2 · Composite scoring</h3>
            <p>Nine components combine into a confidence-weighted composite. C6 event impact carries the highest weight (0.18) — by design, the evidence layer leads.</p>
          </div>
          <div class="bullet">
            <h3>3 · Time-machine replay</h3>
            <p>Any signal can be recomputed as of a past date. Point-in-time filtering (<code>available_as_of &lt;= as_of</code>) is leak-audited; reproducible via the <code>yuclaw replay</code> CLI or REST API.</p>
          </div>
          <div class="bullet">
            <h3>4 · Verified Research Ledger</h3>
            <p>Each day's published signals have their content hashes committed to a public git repo (<a href="https://github.com/YuClawLab/yuclaw-trust" style="color:#00E676">yuclaw-trust</a>). Anyone can call <code>yuclaw verify</code> to confirm a signal hasn't been edited since publication.</p>
          </div>
        </div>
      </div>
    </details>

    <details class="acc">
      <summary>Full disclaimer &amp; methodology</summary>
      <div class="acc-body">
        <p class="method-para">Open-source equity research where every composite signal traces back to a verifiable SEC filing or deterministic supply-chain cascade. Replayable point-in-time. Tamper-evidenced via a public git-anchored Verified Research Ledger. Research and education only.</p>
        <div class="disclaimer">
          <strong>Disclaimer —</strong> {escape(DISCLAIMER)}
        </div>
      </div>
    </details>

    {use_research_block}

    {status_block}

    <div class="card">
      <div class="card-title">Install + try it</div>
      <pre style="background:#0B0E14;padding:14px;border-radius:8px;border:1px solid #1E232D;
                  font-family:JetBrains Mono,monospace;font-size:13px;color:#E2E8F0;overflow-x:auto">
pip install yuclaw
yuclaw demo                         # 3-minute guided "Why AMD?" journey
yuclaw why AMD --as-of 2026-05-20   # bundled offline signal
yuclaw verify AMD --date 2026-05-20 # check the ledger record
# all tickers/dates: connect the local backend — see README</pre>
      <p style="font-size:12px;color:#718096;margin-top:10px">
        SDK + REST API + MCP server documented at
        <a href="https://github.com/YuClawLab/yuclaw-brain" style="color:#00E676">github.com/YuClawLab/yuclaw-brain</a>.
        REST API terms at <a href="API_TERMS.md" style="color:#00E676">/API_TERMS.md</a>.
      </p>
    </div>

    <div class="footer">
      YUCLAW v5.0.0 · <a href="https://github.com/YuClawLab">YuClawLab</a> ·
      <a href="https://github.com/YuClawLab/yuclaw-brain/blob/main/DISCLAIMER.md">Full Disclaimer</a> ·
      <a href="YUCLAW_User_Guide.pdf">📖 User Guide (PDF)</a> ·
      <a href="methodology/backfill.md">Methodology</a> ·
      <a href="replication.html">Replication</a> ·
      <a href="todays_evidence.html">Today's Evidence Changes</a> ·
      <a href="lane.html">YUCLAW's Lane</a> ·
      MIT Licensed
    </div>
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render the YUCLAW v4.0 public landing page")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args(argv)
    rows, as_of = _fetch_current_signals()
    html = render(rows, as_of)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"[render_landing] wrote {out} ({len(html)} bytes, {len(rows)} signals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
