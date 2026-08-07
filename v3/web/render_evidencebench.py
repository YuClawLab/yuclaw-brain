"""
EvidenceBench page (docs/evidencebench.html) — groundedness, not
prediction. How to run, the scoring rule (abstention outscores
fabrication by construction), the honest leaderboard with our
self-evaluation row loudly labeled, and the dataset pointer (derived
events + excerpts + keys; no OHLCV — the export rule).
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

from v3.web.useful_blocks import (footer_stamp_html, build_footer, freshness_strip, site_header_html)

OUT = _REPO / "docs" / "evidencebench.html"


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = json.loads((_REPO / "docs" / "evidencebench" /
                       "meta.json").read_text())
    lb = json.loads((_REPO / "docs" / "evidencebench" /
                     "leaderboard.json").read_text())
    header = site_header_html(subtitle="EvidenceBench")
    rows = "".join(
        f"<tr><td>{escape(r['label'])}</td>"
        f"<td class='mono'>{r['aggregate']}</td>"
        f"<td class='mono'>{escape(json.dumps(r['per_type']))}</td>"
        f"<td class='mono'>{r['abstentions']}</td></tr>"
        for r in lb["rows"])
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EvidenceBench — financial groundedness, contamination-resistant</title>
<meta name="description" content="A weekly-regenerated groundedness benchmark from post-cutoff SEC evidence. Abstention outscores fabrication by construction. Groundedness, not prediction. Research only.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:960px;margin:0 auto;padding:24px}}
 h1{{font-size:24px;color:#FFF}} h2{{font-size:17px;color:#FFF;margin:22px 0 10px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:16px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .amber strong{{color:#FBA94B}}
 .mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
 table{{width:100%;border-collapse:collapse;margin:10px 0}}
 td,th{{padding:9px 12px;border-bottom:1px solid #1E232D;font-size:13px;text-align:left}}
 th{{color:#718096;font-size:11px;text-transform:uppercase}}
 code{{background:#1E232D;padding:2px 6px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#00E676}}
 .muted{{color:#718096;font-size:12px}}
 .wait{{border:1px dashed #00E67650;border-radius:10px;padding:16px;text-align:center;color:#00E676;font-size:14px;margin-top:8px}}
</style>
</head>
<body><div class="container">
{header}
<div class="card">
  <h1>EvidenceBench v{meta['version']} — groundedness, not prediction</h1>
  <p style="margin-top:8px;color:#A0AEC0">Can your model answer questions about real SEC disclosures with
  verifiable grounding — and abstain when it cannot? Items regenerate <strong style="color:#E2E8F0">weekly
  from the newest post-cutoff evidence</strong>, so no static answer key can have been memorized from a
  training corpus: the answers did not exist at training time. That property is mechanical, not aspirational
  — keys ship openly.</p>
  <p class="muted" style="margin-top:8px">Current release: {meta['n_items']} items ·
  item-set hash <span class="mono">{meta['item_set_hash'][:16]}…</span> ·
  generation spec registered as protocol <span class="mono">{meta['protocol_id']}</span> ·
  window: {escape(meta['window'])}</p>
</div>
<div class="amber"><strong>Research and education only — not investment advice.</strong>
EvidenceBench measures groundedness against disclosed evidence; nothing here measures or implies future
returns. Signal labels are research classifications, not buy/sell recommendations.</div>

<div class="card"><h2>How to run</h2>
<pre class="mono" style="background:#10141C;border:1px solid #1E232D;border-radius:8px;padding:12px;white-space:pre-wrap">curl -sO https://yuclaw.ca/evidencebench/items.jsonl
# answer each item_id with your model → predictions.json {{"item_id": "answer", ...}}
pip install yuclaw
python3 -m tools.yuclaw_evidencebench score predictions.json "your-model-name"</pre>
<p style="font-size:13px;margin-top:8px"><strong>Scoring rule (exact, from the registered spec):</strong>
grounded/exact correct = 1.0 · an answer of <code>cannot verify</code> = 0.25 · anything else, including
confident fabrication, = 0.0. <em>An honest abstention always outscores a wrong answer — by
construction.</em></p></div>

<div class="card"><h2>Leaderboard</h2>
<table><thead><tr><th>System</th><th>Aggregate</th><th>Per-type</th><th>Abstentions</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="wait">this row is waiting for your model</div>
<p class="muted" style="margin-top:8px">The only current row is our own extraction stack scored against its
own corpus — a format demonstration, loudly labeled self-evaluation; nothing is claimed by it.</p></div>

<div class="card"><h2>Dataset</h2>
<p style="font-size:13px">Items + keys: <a href="evidencebench/items.jsonl" style="color:#00E676">items.jsonl</a> (JSONL — one item per line: <code>{{item_id, template, question, key}}</code>)
· <a href="evidencebench/meta.json" style="color:#00E676">meta.json</a>. Under the export rule: derived
events, verified excerpts, and keys only — no raw vendor OHLCV is published. Weekly snapshots are tagged in
the repository (dataset citability: see CITATION.cff at the repo root and the
<a href="replication.html" style="color:#00E676">replication page</a>).</p></div>

<div class="amber"><strong>Research and education only — not investment advice.</strong>
Past results — in-sample or forward-tracked — do not predict future performance.</div>
<p class="muted">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a> ·
<a href="for_ai_builders.html" style="color:#A0AEC0">For AI builders</a></p>
{footer_stamp_html(freshness_strip())}
{build_footer()}
</div></body></html>""")
    print(f"[render_evidencebench] {meta['n_items']} items · "
          f"{len(lb['rows'])} leaderboard row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
