"""
Render the Signal Review product page (docs/signal_review.html).

Visual redesign 2026-08-04 ("look like a product, not a policy") — copy
substantively as approved on 2026-08-04; presentation only. Counsel-armed
constraints unchanged and mechanical:
  - NO <form>, NO upload element, NO payment integration anywhere —
    enforced by tools/check_no_forms.py; <details> expanders are native
    HTML, no JS, no forms
  - research classifications, never recommendations; full rails
  - EXPLORATORY (CLIENT) ceiling stated: higher standings not for sale
  - contact = placeholder pattern (counsel decides the delivery channel)
  - tier scope lines MUST match tools/yuclaw_client_deliverable.py
    TIER_PROFILES — the packager's --selftest diffs page promises vs
    produced sections
  - the diagnostics chart renders from the synthetic dry-run's ACTUAL
    artifact (output/byos_dryrun/signal_suite.json) and is labeled
    SYNTHETIC DEMONSTRATION — a null signal, correctly diagnosed as null
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import site_header_html

OUT = _REPO / "docs" / "signal_review.html"
SUITE = _REPO / "output" / "byos_dryrun" / "signal_suite.json"

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

STEPS = [
    ("🔍", "Pre-check your file locally",
     "One command, on your machine. Sends nothing.",
     "<code>pip install yuclaw && yuclaw intake-check your.csv</code> — the "
     "exact intake rules, run on your machine. Your data stays yours until "
     "you engage; this page has no upload box by design."),
    ("📅", "Request a slot",
     "Contact + a short scope call.",
     "Working path today: open a GitHub issue titled \"Signal Review slot "
     "request\" with <em>no data attached</em> — [CONTACT CHANNEL "
     "PLACEHOLDER — published after counsel sign-off on the delivery "
     "path]."),
    ("🔒", "Protocol locked before computation",
     "You receive the spec and its hash.",
     "Your engagement's statistical specification is registered in a "
     "client-namespace tamper-evident chain first; you receive the spec "
     "and its hash before any number is computed."),
    ("🖥️", "Sovereign analysis, custody-enforced",
     "Local hardware. Your data never enters our repo.",
     "All inference runs on our own local hardware. Client data never "
     "enters the public repository or backups — enforced by an automated "
     "custody gate, not policy prose."),
    ("📦", "Memo + bundle + findings session",
     "Every number cites its protocol.",
     "Every number in the memo cites its protocol; the reproduction "
     "bundle reruns the analysis end-to-end without us."),
]


def _ic_chart() -> str:
    """Inline SVG: IC bars with CI whiskers from the REAL synthetic
    dry-run artifact. Omitted gracefully if the artifact is absent."""
    try:
        decay = json.loads(SUITE.read_text())["suite"]["horizon_decay"]
    except Exception:
        return ""
    W, H, PADL, ROWH = 560, 30 + 34 * len(decay), 70, 34
    scale = 2200          # x px per IC unit
    cx = PADL + (W - PADL - 20) / 2
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="IC by horizon with confidence intervals, all '
             f'straddling zero" style="width:100%;max-width:{W}px">',
             f'<line x1="{cx}" y1="8" x2="{cx}" y2="{H - 18}" '
             f'stroke="#3A4150" stroke-dasharray="3,3"/>',
             f'<text x="{cx}" y="{H - 4}" fill="#718096" font-size="10" '
             f'text-anchor="middle" font-family="monospace">0</text>']
    for i, c in enumerate(decay):
        y = 24 + i * ROWH
        x_lo, x_hi = cx + c["ci"][0] * scale, cx + c["ci"][1] * scale
        x_v = cx + c["mean_ic"] * scale
        parts += [
            f'<text x="{PADL - 10}" y="{y + 4}" fill="#A0AEC0" '
            f'font-size="11" text-anchor="end" font-family="monospace">'
            f'k={c["k"]}</text>',
            f'<line x1="{x_lo}" y1="{y}" x2="{x_hi}" y2="{y}" '
            f'stroke="#4A5568" stroke-width="2"/>',
            f'<line x1="{x_lo}" y1="{y - 5}" x2="{x_lo}" y2="{y + 5}" '
            f'stroke="#4A5568" stroke-width="2"/>',
            f'<line x1="{x_hi}" y1="{y - 5}" x2="{x_hi}" y2="{y + 5}" '
            f'stroke="#4A5568" stroke-width="2"/>',
            f'<circle cx="{x_v}" cy="{y}" r="4" fill="#00E676"/>',
            f'<text x="{x_hi + 10}" y="{y + 4}" fill="#718096" '
            f'font-size="10" font-family="monospace">'
            f'{c["mean_ic"]:+.3f}</text>']
    parts.append("</svg>")
    return "".join(parts)


def _flow_svg() -> str:
    boxes = ["your CSV", "local intake-check", "scope call",
             "protocol locked (hash to you)",
             "sovereign analysis (custody gate)", "memo + bundle to you"]
    W, BH, GAP = 960, 46, 26
    bw = (W - GAP * (len(boxes) - 1) - 8) / len(boxes)
    parts = [f'<svg viewBox="0 0 {W} 120" role="img" aria-label="Signal '
             f'Review flow: CSV to local intake-check to scope call to '
             f'locked protocol to sovereign analysis to memo and bundle; '
             f'a dashed arrow returns to the client: you rerun everything '
             f'without us" style="width:100%">']
    for i, label in enumerate(boxes):
        x = 4 + i * (bw + GAP)
        parts.append(
            f'<rect x="{x}" y="12" width="{bw}" height="{BH}" rx="8" '
            f'fill="#151A23" stroke="#1E232D"/>')
        words = label.split()
        mid = (len(words) + 1) // 2
        for j, seg in enumerate((" ".join(words[:mid]),
                                 " ".join(words[mid:]))):
            if seg:
                parts.append(
                    f'<text x="{x + bw / 2}" y="{30 + j * 13}" '
                    f'fill="#E2E8F0" font-size="10.5" '
                    f'text-anchor="middle">{seg}</text>')
        if i < len(boxes) - 1:
            ax = x + bw
            parts.append(
                f'<line x1="{ax + 3}" y1="{12 + BH / 2}" '
                f'x2="{ax + GAP - 5}" y2="{12 + BH / 2}" stroke="#00E676" '
                f'stroke-width="1.6" marker-end="url(#arr)"/>')
    x_last = 4 + (len(boxes) - 1) * (bw + GAP) + bw / 2
    parts += [
        f'<path d="M {x_last} {12 + BH} V 92 H {4 + bw / 2} V {12 + BH}" '
        f'fill="none" stroke="#00E676" stroke-width="1.4" '
        f'stroke-dasharray="6,5" marker-end="url(#arr)"/>',
        f'<text x="{W / 2}" y="108" fill="#00E676" font-size="11" '
        f'text-anchor="middle" font-family="monospace">you rerun '
        f'everything without us</text>',
        '<defs><marker id="arr" markerWidth="7" markerHeight="7" '
        'refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" '
        'fill="#00E676"/></marker></defs></svg>']
    return "".join(parts)


def render() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = site_header_html(subtitle="Signal Review",
                              stamp=f"built {stamp}",
                              active="signal_review.html")
    step_cards = "".join(f"""
      <div class="step">
        <div class="numrow"><span class="num">{i}</span><span class="ico">{ico}</span></div>
        <div class="steptitle">{title}</div>
        <div class="stepsub">{sub}</div>
        <details><summary>more</summary><p>{body}</p></details>
      </div>""" for i, (ico, title, sub, body) in enumerate(STEPS, 1))
    tier_a = "".join(f'<li><span class="tick">✓</span>{x}</li>'
                     for x in TIER_A_ITEMS)
    tier_b_extra = "".join(f'<li><span class="tick">✓</span>{x}</li>'
                           for x in TIER_B_ITEMS[len(TIER_A_ITEMS):])
    chart = _ic_chart()
    chart_block = f"""
      <div class="recv-card">
        <div class="recv-title">One honest chart</div>
        {chart}
        <div class="synth-label">SYNTHETIC DEMONSTRATION — a null signal, correctly diagnosed as null</div>
        <p class="muted" style="margin-top:6px">Rank-association (IC) by horizon with bootstrap confidence
        intervals, rendered from the synthetic dry-run's actual output. Every interval straddles zero —
        exactly what an information-free signal should show, and exactly what the suite reported.</p>
      </div>""" if chart else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW Signal Review — bring your signal, we try to break it</title>
<meta name="description" content="A registered, reproducible research review of your signal. Research classifications, never recommendations. No uploads, no payment forms — engagement begins with a conversation.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:1060px;margin:0 auto;padding:24px}}
 h2{{font-size:19px;color:#FFF;margin:0 0 14px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:24px;margin-bottom:18px}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 .muted{{color:#718096;font-size:12px}}
 code{{background:#1E232D;padding:2px 7px;border-radius:4px;font-size:12px;font-family:'JetBrains Mono',monospace;color:#00E676}}
 /* hero */
 .hero{{background:linear-gradient(135deg,#10141C,#141B2E);border:1px solid #1E232D;border-radius:14px;
        padding:52px 34px 40px;text-align:center;margin-bottom:14px}}
 .hero h1{{font-size:clamp(26px,4.4vw,44px);font-weight:800;color:#FFF;letter-spacing:-1.2px;line-height:1.15}}
 .hero .sub{{font-size:16px;color:#A0AEC0;margin:14px auto 26px;max-width:640px}}
 .cmdchip{{display:inline-block;background:#0B0E14;border:1px solid #00E67650;border-radius:10px;
           padding:14px 22px;font-family:'JetBrains Mono',monospace;font-size:clamp(11px,1.8vw,14px);
           color:#00E676;box-shadow:0 0 24px #00E67618}}
 .cmdcap{{font-size:12px;color:#718096;margin-top:10px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;
         font-size:12px;color:#A0AEC0;margin-bottom:20px}}
 .amber strong{{color:#FBA94B}}
 /* steps */
 .steps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px}}
 .step{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:16px}}
 .numrow{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
 .num{{width:26px;height:26px;border-radius:50%;background:#00E67620;color:#00E676;border:1px solid #00E67660;
       display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}}
 .ico{{font-size:18px}}
 .steptitle{{font-weight:700;color:#FFF;font-size:13.5px;line-height:1.35}}
 .stepsub{{font-size:12px;color:#A0AEC0;margin:5px 0 8px}}
 details summary{{cursor:pointer;color:#00E676;font-size:11.5px}}
 details p{{font-size:12px;color:#A0AEC0;margin-top:7px}}
 /* tiers */
 .tiers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
 .tier{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;position:relative}}
 .tier.full{{border:1px solid #00E67660;box-shadow:0 0 30px #00E67612}}
 .tag{{position:absolute;top:-10px;right:16px;background:#00E676;color:#0B0E14;font-size:10px;
       font-weight:800;padding:3px 10px;border-radius:5px;letter-spacing:0.5px}}
 .price{{font-family:'JetBrains Mono',monospace;font-size:34px;color:#FFF;font-weight:700;margin:6px 0 2px}}
 .price small{{font-size:13px;color:#718096;font-weight:400}}
 .tier ul{{list-style:none;margin-top:12px}}
 .tier li{{font-size:12.5px;color:#CBD5E1;margin:7px 0;padding-left:22px;position:relative}}
 .tick{{position:absolute;left:0;color:#00E676;font-weight:700}}
 .feestrip{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#718096;background:#10141C;
            border:1px solid #1E232D;border-radius:8px;padding:9px 14px;margin-top:12px;text-align:center}}
 /* receive */
 .recv{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}
 .recv-card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:18px}}
 .recv-title{{font-size:12px;color:#718096;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:10px}}
 .memomock{{background:#F7F8FA;border-radius:6px;padding:16px 18px;color:#1A202C;max-width:280px;
            box-shadow:0 6px 20px #00000060;font-size:9px}}
 .memomock .mt{{font-weight:800;font-size:11px;letter-spacing:0.2px}}
 .memomock .ms{{color:#718096;font-size:8px;margin-bottom:8px}}
 .memomock .sec{{border-top:1px solid #E2E8F0;padding:4px 0;font-weight:600;color:#2D3748}}
 .memomock .bar{{height:3px;background:#CBD5E1;border-radius:2px;margin:2px 0;width:90%}}
 .ftree{{font-family:'JetBrains Mono',monospace;font-size:12px;color:#A0AEC0;line-height:1.9;white-space:pre}}
 .synth-label{{display:inline-block;background:#FBA94B20;color:#FBA94B;border:1px solid #FBA94B60;
               font-size:10.5px;font-weight:800;letter-spacing:0.5px;padding:4px 10px;border-radius:5px;margin-top:8px}}
 /* ceilings */
 .ceil{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}}
 .ceil .c{{background:#0F1A14;border:1px solid #00E67630;border-radius:10px;padding:14px;font-size:12.5px;color:#CBD5E1}}
 .ceil .c b{{color:#FFF}}
 .pull{{border-left:3px solid #00E676;padding:12px 18px;margin:16px 0 0;font-size:15px;color:#E2E8F0;font-style:italic}}
 .pull span{{color:#00E676}}
 /* for / not for */
 .fornot{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
 .for{{background:#151A23;border:1px solid #1E232D;border-left:4px solid #00E676;border-radius:12px;padding:20px}}
 .notfor{{background:#151A23;border:1px solid #1E232D;border-left:4px solid #FF3366;border-radius:12px;padding:20px}}
 .for h3{{color:#00E676;font-size:14px;margin-bottom:8px}}
 .notfor h3{{color:#FF3366;font-size:14px;margin-bottom:8px}}
 .for p,.notfor p{{font-size:13px;color:#CBD5E1}}
</style>
</head>
<body><div class="container">
{header}

<div class="hero">
  <h1>Bring your signal.<br>YUCLAW tries to break it before you trust it.</h1>
  <p class="sub">A registered, reproducible research review — statistics locked before computation,
  adverse results delivered as measured, a bundle that reruns every number without us.</p>
  <div class="cmdchip">pip install yuclaw &amp;&amp; yuclaw intake-check your.csv</div>
  <div class="cmdcap">start here — runs on your machine, sends nothing</div>
</div>

<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal Review produces research classifications, never recommendations. It will not tell you what to buy or
sell, and it will not predict tomorrow's price.</div>

<h2>How it works — five steps, no uploads</h2>
<div class="steps">{step_cards}</div>
<div class="card">{_flow_svg()}</div>

<h2>Founding pilot tiers</h2>
<div class="tiers">
  <div class="tier">
    <div style="font-weight:800;color:#FFF">Founding Pilot A</div>
    <div class="muted">Signal validation core</div>
    <div class="price">CAD 2,500<small> fixed</small></div>
    <ul>{tier_a}</ul>
  </div>
  <div class="tier full">
    <span class="tag">FULL REVIEW</span>
    <div style="font-weight:800;color:#FFF">Founding Pilot B</div>
    <div class="muted">Full signal review</div>
    <div class="price">CAD 5,000<small> fixed</small></div>
    <ul><li style="padding-left:0;color:#718096">Everything in A, plus:</li>{tier_b_extra}</ul>
  </div>
</div>
<div class="feestrip">fixed fees only · no contingent, performance-linked, or asset-based fees ·
no payment is collected on this site — invoicing follows the scope call</div>

<h2 style="margin-top:26px">What you receive</h2>
<div class="recv">
  <div class="recv-card">
    <div class="recv-title">The memo — first page</div>
    <div class="memomock">
      <div class="mt">Signal Review — Research Memo</div>
      <div class="ms">protocol &lt;hash&gt; · registered before computation</div>
      <div class="sec">1 · Data Integrity</div><div class="bar"></div><div class="bar" style="width:70%"></div>
      <div class="sec">2 · IC with CIs</div><div class="bar"></div><div class="bar" style="width:80%"></div>
      <div class="sec">3 · Quantile Ordering</div><div class="bar" style="width:85%"></div>
      <div class="sec">4 · Falsification</div><div class="bar" style="width:75%"></div>
      <div class="sec">5 · Limitations</div><div class="bar" style="width:60%"></div>
      <div class="sec">6 · Reproduction</div><div class="bar" style="width:65%"></div>
    </div>
    <p class="muted" style="margin-top:8px">Layout illustration of the memo's section structure — every number
    in a delivered memo cites its registered protocol.</p>
  </div>
  <div class="recv-card">
    <div class="recv-title">The bundle — actual contents</div>
    <div class="ftree">client_deliverable.zip
├── CLIENT_MEMO.pdf
├── CLIENT_MEMO.md
├── METHODOLOGY.md
├── bundle/
│   ├── client_input.csv
│   ├── client_signals.csv
│   ├── manifest.json
│   ├── registry_client.jsonl
│   └── rerun.sh
├── SHA256SUMS
└── README_VERIFICATION.md</div>
    <p class="muted" style="margin-top:8px"><code>bash bundle/rerun.sh</code> recomputes the delivered numbers
    from the bundled inputs and prints REPRODUCTION OK on an exact match.</p>
  </div>
  {chart_block}
</div>

<h2 style="margin-top:26px">The honest ceilings</h2>
<div class="ceil">
  <div class="c">🚫 <b>Standings are not purchasable.</b> Client engagements cap at EXPLORATORY (CLIENT);
    the public record's higher standings cannot be bought — at any price.</div>
  <div class="c">📏 <b>Under 15 names per date = underpowered,</b> disclosed up front — honesty about sample
    size, not a defect in your signal.</div>
  <div class="c">⚖️ <b>Adverse results are delivered exactly as measured.</b> Nothing is softened, decorated,
    or withheld.</div>
  <div class="c">🧹 <b>Unrequested columns are rejected automatically.</b> We never carry client data we did
    not ask for.</div>
</div>
<div class="pull">A defensible null — <span>"your signal shows no measurable information at this sample size,
and here is the power analysis that says so"</span> — is a result we are proud to deliver.
It may save you far more than the fee.</div>

<h2 style="margin-top:26px">Who this is for</h2>
<div class="fornot">
  <div class="for">
    <h3>For</h3>
    <p>Anyone holding a signal, a screen, or a systematic idea who wants an independent, registered,
    reproducible read of what the evidence shows — and what it cannot show at the current sample size.</p>
  </div>
  <div class="notfor">
    <h3>"If you want tomorrow's stock price, we are deliberately the wrong vendor."</h3>
    <p>Not for anyone seeking predictions, price targets, trade timing, portfolio construction, or advice.
    No standing above EXPLORATORY (CLIENT) is available, and no recommendation will ever be part of a
    deliverable.</p>
  </div>
</div>

<div class="card" style="margin-top:26px">
  <h2>Request a slot</h2>
  <p style="font-size:13.5px;color:#CBD5E1">Contact + a short scope call. Working path today: open a GitHub
  issue titled "Signal Review slot request" with <em>no data attached</em> — [CONTACT CHANNEL PLACEHOLDER —
  published after counsel sign-off on the delivery path].</p>
</div>

<div class="amber"><strong>Research and education only — not investment advice.</strong> Signal labels and
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
