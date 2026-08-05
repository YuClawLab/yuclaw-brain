"""
Render the Signal Review product page (docs/signal_review.html).

Counsel-armed constraints, mechanical where possible:
  - NO <form>, NO upload element, NO payment integration anywhere —
    enforced by tools/check_no_forms.py across all of docs/
  - research classifications, never recommendations; full rails
  - EXPLORATORY (CLIENT) ceiling stated: higher standings are not for sale
  - contact = placeholder pattern (counsel decides the delivery channel);
    the working no-data path is a GitHub issue with no attachments
  - tier scope lines MUST match the fulfillment profiles in
    tools/yuclaw_client_deliverable.py TIER_PROFILES — a self-test diffs
    the page's promises against the memo sections (page may never promise
    what the pipeline doesn't produce)
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import site_header_html

OUT = _REPO / "docs" / "signal_review.html"

# The page's tier-scope promise lines. PART E's self-test asserts each of
# these maps to a produced deliverable section — single source of truth
# for what may be promised.
TIER_A_ITEMS = [
    "Locked protocol registered before computation (you receive the spec and its hash)",
    "Signal decomposition suite: rank association with later returns with confidence intervals, quantile ordering, churn, horizon decay, placebo",
    "Methodology note (how to read every number)",
    "Reproduction bundle (rerun our numbers without us)",
    "Research memo covering the suite results",
]
TIER_B_ITEMS = TIER_A_ITEMS + [
    "Basket event-study panel with cluster-robust intervals",
    "Falsification battery (date-shuffle, sign-flip, placebo)",
    "Coverage and exclusion anatomy (what was measurable and why)",
    "30 days of written questions + a findings session",
]


def render() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = site_header_html(subtitle="Signal Review",
                              stamp=f"built {stamp}",
                              active="signal_review.html")
    tier_a = "".join(f"<li>{x}</li>" for x in TIER_A_ITEMS)
    tier_b = "".join(f"<li>{x}</li>" for x in TIER_B_ITEMS[len(TIER_A_ITEMS):])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW Signal Review — bring your signal, we try to break it</title>
<meta name="description" content="A registered, reproducible research review of your signal. Research classifications, never recommendations. No uploads, no payment forms — engagement begins with a conversation.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.65}}
 .container{{max-width:980px;margin:0 auto;padding:24px}}
 h1{{font-size:28px;color:#FFF;letter-spacing:-0.5px;margin-bottom:6px}}
 h2{{font-size:18px;color:#FFF;margin:26px 0 10px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:16px}}
 .disc{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:12px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 ol.flow li{{margin:10px 0 10px 18px}}
 ul{{margin-left:18px}}
 li{{margin:6px 0}}
 table{{width:100%;border-collapse:collapse;margin:10px 0}}
 th,td{{padding:10px 12px;border-bottom:1px solid #1E232D;text-align:left;font-size:13px;vertical-align:top}}
 th{{color:#718096;font-size:11px;text-transform:uppercase;letter-spacing:0.5px}}
 code{{background:#1E232D;padding:2px 7px;border-radius:4px;font-size:12px;font-family:'JetBrains Mono',monospace;color:#00E676}}
 .muted{{color:#718096;font-size:12px}}
</style>
</head>
<body><div class="container">
{header}

<div class="card">
  <h1>Bring your signal. YUCLAW tries to break it before you trust it.</h1>
  <p style="color:#A0AEC0;margin-top:6px">A registered, reproducible research review of a signal you already have —
  statistics locked before computation, adverse results delivered as measured, and a bundle that lets you
  rerun every number without us.</p>
  <div class="disc"><strong>Research and education only — not investment advice.</strong>
  Signal Review produces research classifications, never recommendations. It will not tell you what to buy or
  sell, and it will not predict tomorrow's price. If you want tomorrow's stock price, we are deliberately the
  wrong vendor.</div>
</div>

<div class="card">
  <h2>How it works — five steps, no uploads</h2>
  <ol class="flow">
    <li><strong>Pre-check your file locally.</strong> <code>pip install yuclaw && yuclaw intake-check your.csv</code>
      — the exact intake rules, run on your machine. Your data stays yours until you engage; this page has no
      upload box by design.</li>
    <li><strong>Request a slot.</strong> Contact + a short scope call. Working path today: open a GitHub issue
      titled "Signal Review slot request" with <em>no data attached</em> — [CONTACT CHANNEL PLACEHOLDER —
      published after counsel sign-off on the delivery path].</li>
    <li><strong>Protocol locked before computation.</strong> Your engagement's statistical specification is
      registered in a client-namespace tamper-evident chain first; you receive the spec and its hash before any
      number is computed.</li>
    <li><strong>Analysis on sovereign hardware, custody-enforced.</strong> All inference runs on our own local
      hardware. Client data never enters the public repository or backups — enforced by an automated custody
      gate, not policy prose.</li>
    <li><strong>Memo + reproduction bundle + findings session.</strong> Every number in the memo cites its
      protocol; the bundle reruns the analysis end-to-end without us.</li>
  </ol>
</div>

<div class="card">
  <h2>Founding pilot tiers</h2>
  <table>
    <thead><tr><th>Tier</th><th>Fee (CAD, fixed, paid before work begins)</th><th>Scope</th></tr></thead>
    <tbody>
      <tr><td><strong>Founding Pilot A</strong><br><span class="muted">Signal validation core</span></td>
          <td class="mono">2,500</td>
          <td><ul>{tier_a}</ul></td></tr>
      <tr><td><strong>Founding Pilot B</strong><br><span class="muted">Full signal review</span></td>
          <td class="mono">5,000</td>
          <td>Everything in A, plus:<ul>{tier_b}</ul></td></tr>
    </tbody>
  </table>
  <p class="muted">Fixed fees only — no contingent, performance-linked, or asset-based fees of any kind.
  No payment is collected on this site; invoicing follows the scope call.</p>
</div>

<div class="card">
  <h2>The honest ceilings</h2>
  <ul>
    <li>Client engagements are capped at <strong>EXPLORATORY (CLIENT)</strong> standing.
      The public record's higher standings cannot be bought — at any price.</li>
    <li>Fewer than 15 names per date is disclosed as underpowered, up front.</li>
    <li>Adverse results are delivered exactly as measured. A defensible null — "your signal shows no measurable
      information at this sample size, and here is the power analysis that says so" — is a result we are proud
      to deliver. It may save you far more than the fee.</li>
    <li>Files containing columns we did not ask for are rejected automatically. We never carry client data we
      did not request.</li>
  </ul>
</div>

<div class="card">
  <h2>Who this is for — and not for</h2>
  <p><strong>For:</strong> anyone holding a signal, a screen, or a systematic idea who wants an independent,
  registered, reproducible read of what the evidence shows — and what it cannot show at the current sample
  size.</p>
  <p style="margin-top:8px"><strong>Not for:</strong> anyone seeking predictions, price targets, trade timing,
  portfolio construction, or advice. If you want tomorrow's stock price, we are deliberately the wrong vendor.
  No standing above EXPLORATORY (CLIENT) is available, and no recommendation will ever be part of a
  deliverable.</p>
</div>

<div class="disc"><strong>Research and education only — not investment advice.</strong> Signal labels and
review outputs are research classifications, not buy/sell recommendations. YUCLAW is not a registered
investment adviser. Past results — in-sample or forward-tracked — do not predict future performance.
Engagement terms are subject to counsel review before any engagement is accepted.</div>

<p class="muted" style="margin:16px 0">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a> ·
<a href="https://github.com/YuClawLab/yuclaw-brain" style="color:#A0AEC0">GitHub</a> ·
built {stamp}</p>
</div></body></html>"""


def main() -> int:
    OUT.write_text(render())
    print(f"[render_signal_review] wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
