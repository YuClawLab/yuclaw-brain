"""
"For AI builders" page (docs/for_ai_builders.html) — the agent surface,
factually pitched: agents citing YUCLAW inherit accession-verified,
point-in-time, hash-anchored evidence. Renders a REAL passport (NVDA,
generated at build) with the five statuses explained. No oversight/
regulation claim appears anywhere — nothing renders until counsel
approves wording (MICRO 2026-08-31A removed the former [COUNSEL]
placeholder; placeholder markers are now banned in public HTML by
check_site_walk).
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

OUT = _REPO / "docs" / "for_ai_builders.html"

STATUS_EXPLAIN = [
    ("SOURCE_MATCHED", "every structured element of the claim matched at "
     "least one EvidenceObject — the excerpts and hashes are in the "
     "passport"),
    ("PARTIAL_MATCH", "at least one EvidenceObject matched some elements "
     "of the claim; the matched objects and the misses are both listed "
     "explicitly — a passport with zero matched objects is never "
     "PARTIAL_MATCH"),
    ("UNSUPPORTED", "no EvidenceObject matched — not found in YUCLAW's "
     "corpus, never a truth verdict; a cited accession that is not in "
     "the corpus lands here"),
    ("NOT_IN_COVERAGE", "the ticker is outside the 79-name scoring "
     "universe; the corpus cannot speak to it"),
    ("NOT_PARSEABLE", "the conservative text parser could not "
     "confidently structure the claim — the false-denial guard: an "
     "unparsed claim is never called unsupported"),
]


def _live_passport() -> dict:
    from v3.cli.check_claim import passport
    from v3.evidence import evidence_objects
    objs = [o for o in evidence_objects("NVDA")
            if o["evidence_type"] == "INSIDER_SELL"]
    acc = objs[0]["accession_number"] if objs else None
    claim = {"ticker": "NVDA", "type": "INSIDER_SELL",
             "accession": acc, "date_range": None}
    return passport(json.dumps({k: v for k, v in claim.items() if v}),
                    claim, True)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = site_header_html(subtitle="For AI builders")
    pp = _live_passport()
    pp_json = escape(json.dumps(pp, indent=1)[:2600])
    statuses = "".join(
        f"<tr><td class='mono st'>{s}</td><td>{d}</td></tr>"
        for s, d in STATUS_EXPLAIN)
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW for AI builders — the open evidence layer for financial AI</title>
<meta name="description" content="Ground Truth JSON API, Evidence Passport claim-checker, MCP tools, EvidenceBench. Agents citing YUCLAW inherit accession-verified, point-in-time, hash-anchored evidence. Research only — not investment advice.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:960px;margin:0 auto;padding:24px}}
 h1{{font-size:26px;color:#FFF;letter-spacing:-0.5px}}
 h2{{font-size:17px;color:#FFF;margin:24px 0 10px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:16px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .amber strong{{color:#FBA94B}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 pre{{background:#10141C;border:1px solid #1E232D;border-radius:8px;padding:12px;overflow-x:auto;
      font-family:'JetBrains Mono',monospace;font-size:11px;color:#A0AEC0;white-space:pre-wrap}}
 table{{width:100%;border-collapse:collapse;margin:10px 0}}
 td,th{{padding:8px 12px;border-bottom:1px solid #1E232D;font-size:13px;text-align:left;vertical-align:top}}
 .st{{color:#00E676;font-size:12px;white-space:nowrap}}
 code{{background:#1E232D;padding:2px 6px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#00E676}}
 .muted{{color:#718096;font-size:12px}}
</style>
</head>
<body><div class="container">
{header}
<div class="card">
  <h1>The open evidence layer for financial AI.</h1>
  <p style="margin-top:8px;color:#A0AEC0">Agents citing YUCLAW inherit <strong style="color:#E2E8F0">accession-verified,
  point-in-time, hash-anchored evidence</strong>: every EvidenceObject carries a verified excerpt, its SEC
  accession number, a SHA-256 anchored in a public daily ledger, and the <code>available_as_of</code> bound
  that makes look-ahead impossible to hide. Start at
  <a href="capabilities.json" style="color:#00E676">capabilities.json</a> — one URL discovers everything.</p>
</div>
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations. Investment implication: none
established — no buy, sell, or alpha conclusion is supported by this page.</div>

<div class="card"><h2>The Evidence Passport — a deterministic claim-checker</h2>
<p style="font-size:13.5px"><code>yuclaw check-claim --ticker NVDA --type INSIDER_SELL --accession …</code>
returns a passport: the claim as parsed, the matched EvidenceObjects with excerpts and hashes, and one of
five mechanical statuses. Below is a real passport generated at this page's build:</p>
<pre>{pp_json}</pre>
<table><thead><tr><th>Status</th><th>Meaning</th></tr></thead><tbody>{statuses}</tbody></table>
</div>

<div class="card"><h2>The as-of recipe (point-in-time reconstruction)</h2>
<p style="font-size:13.5px">To reconstruct name X as of date D from <code>why/X.json</code>: evidence =
objects with <code>available_as_of ≤ D</code>; the classification at D = the <code>label_history</code>
entry for the last date ≤ D. Older dates beyond the ribbon: <code>yuclaw replay X --date D</code>.
Worked example in <a href="llms.txt" style="color:#00E676">llms.txt</a>.</p>
</div>

<div class="card" id="evidence-changes"><h2>Daily evidence changes + the C6 posture set (schema effective 2026-08-29)</h2>
<p style="font-size:13.5px"><code>/evidence_changes/{{YYYY-MM-DD}}.json</code> — one file per UTC day, rolling 30 days,
key order <code>date, counts, c6_posture, grades, ledger, maturity, replay</code>. The cumulative C6 posture
accession set is <em>not</em> inlined; it lives at <code>/c6_posture_current.json</code>
(<code>{{as_of, files, set_sha256, accessions}}</code>) and each daily file carries only a one-day delta:</p>
<pre>"c6_posture": {{ "files": N, "set_sha256": "…", "added_today": [...], "removed_today": [...],
                "delta_since": "YYYY-MM-DD", "delta_span_days": N, "delta_status": "OK",
                "current_url": "/c6_posture_current.json" }}</pre>
<ul style="margin-left:18px;font-size:13.5px">
<li><strong>set_sha256 definition:</strong> sorted UNIQUE accession strings, byte-lexicographic order
(locale-independent), UTF-8, joined with <code>"\\n"</code>, NO trailing newline; sha256 of those bytes.
Recompute it from <code>accessions</code> to verify the endpoint offline.</li>
<li><strong>Pin semantics:</strong> <code>current_url</code> is mutable (always latest); the <code>set_sha256</code>
inside each dated daily file is the historical pin for that day.</li>
<li><strong>Delta base (dated previous-set state):</strong> the delta is always computed against the last
<em>completed</em> prior build day's set — <code>delta_since</code> is that day and <code>delta_span_days</code> the
calendar days covered (1 on consecutive build days; honestly 3 after a weekend — the chain runs weekdays). A
same-UTC-day rebuild leaves the base unchanged and recomputes the block idempotently (the build gate proves
twice-run identity). Only a true cold start (no previous-day set at all) publishes <code>added_today</code>/
<code>removed_today</code>/<code>delta_since</code>/<code>delta_span_days</code> = <code>null</code> with
<code>delta_status</code> = <code>UNAVAILABLE (cold start: no previous-day set state)</code>.</li>
<li>Files dated before 2026-08-29 carry the legacy inline <code>c6_posture_accessions</code> /
<code>c6_posture_files</code> keys and are never rewritten.</li>
</ul>
</div>

<div class="card"><h2>Surfaces</h2>
<ul style="margin-left:18px;font-size:13.5px">
<li><code>/why/{{TICKER}}.json</code> — full anatomy + EvidenceObjects + label history (79 names)</li>
<li><code>/capabilities.json</code> · <code>/evidence/verify.json</code> · <code>/ledger/{{DATE}}.json</code> — discovery + offline integrity verification</li>
<li><code>/schemas/*.v1.json</code> — eight frozen object schemas</li>
<li><code>/c6_posture_current.json</code> · <code>/evidence_changes/{{YYYY-MM-DD}}.json</code> — C6 posture set (pinned hash) + daily deltas</li>
<li>MCP v2 tools: <code>get_evidence · get_signal_anatomy · check_claim · verify_snapshot · get_protocol</code></li>
<li><a href="evidencebench.html" style="color:#00E676">EvidenceBench</a> — the contamination-resistant groundedness benchmark</li>
</ul>
</div>

<div class="amber"><strong>Research and education only — not investment advice.</strong>
Past results — in-sample or forward-tracked — do not predict future performance.</div>
<p class="muted">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a></p>
{footer_stamp_html(freshness_strip())}
{build_footer()}
</div></body></html>""")
    print(f"[render_ai_builders] live NVDA passport status: {pp['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
