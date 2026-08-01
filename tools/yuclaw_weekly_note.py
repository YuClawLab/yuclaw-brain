#!/usr/bin/env python3
"""
Weekly evidence note generator (credibility battery Part F).

Auto-drafts a dated note from LIVE SOURCES ONLY — the evidence-changes
archive (docs/evidence_changes/*.json), registry protocols/runs in the
window, forward-ledger label distribution changes, and any completed
calendar reads. Zero free prose invention: every sentence is a template
filled from queried values. Full language rail + the forbidden-word set
run AT BUILD TIME — the build fails rather than shipping a violation.
Renders docs/weekly_note.html with the standing disclaimers; runs as a
Friday step in the daily chain.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from check_language import lint_text
from v3.web.useful_blocks import site_header_html

OUT = _REPO / "docs" / "weekly_note.html"
FORBIDDEN = re.compile(r"\bproof\b|certificate|mathematical verification|"
                       r"validated|conservation law", re.I)
IMPLICATION = ("Investment implication: none established — no buy, sell, or "
               "alpha conclusion is supported by this page.")
DISCLAIMER = ("Research and education only. Not investment advice. "
              "Classifications, not recommendations. Past results — "
              "in-sample or forward-tracked — do not predict future "
              "performance.")


def week_window(today: date) -> tuple[date, date]:
    end = today
    start = end - timedelta(days=6)
    return start, end


def gather(start: date, end: date) -> dict:
    # evidence-changes archive
    total_filings, total_events, days = 0, 0, 0
    arch = _REPO / "docs" / "evidence_changes"
    for f in sorted(arch.glob("*.json")):
        try:
            d = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        j = json.loads(f.read_text())
        c = j.get("counts", j)
        nf = c.get("new_filings")
        total_filings += (sum(nf.values()) if isinstance(nf, dict)
                          else int(nf or 0))
        ne = c.get("new_events_accepted", c.get("accepted", 0))
        total_events += (sum(ne.values()) if isinstance(ne, dict)
                         else int(ne or 0))
        days += 1

    from yuclaw_protocol_registry import Registry
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    protos, runs, sups = [], [], []
    for ln in reg._lines:
        pl = ln["payload"]
        if ln["kind"] == "protocol" and start.isoformat() <= pl["lock_date"] <= end.isoformat():
            protos.append(pl["name"])
        if ln["kind"] == "run" and start.isoformat() <= pl["run_date"] <= end.isoformat():
            runs.append(pl["protocol_id"])
        if ln["kind"] == "supersede_notice" and start.isoformat() <= pl["date"] <= end.isoformat():
            sups.append(f"{pl['protocol_id']} -> {pl['superseded_by']}")
    questions = {k: v["status"] for k, v in reg.questions().items()}
    return {"days": days, "filings": total_filings, "events": total_events,
            "protocols": protos, "n_runs": len(runs), "supersessions": sups,
            "questions": questions}


def main() -> int:
    today = datetime.now(timezone.utc).date()
    start, end = week_window(today)
    g = gather(start, end)

    proto_list = "".join(f"<li>{escape(n)}</li>" for n in g["protocols"]) or \
        "<li>none this week</li>"
    sup_list = "".join(f"<li><code>{escape(s)}</code></li>"
                       for s in g["supersessions"]) or "<li>none</li>"
    q_list = "".join(f"<li>{escape(k)}: <strong>{escape(v)}</strong></li>"
                     for k, v in g["questions"].items())

    body_text = (f"Week of {start} to {end}. Ingestion: {g['filings']} new "
                 f"filings across {g['days']} archived days; {g['events']} "
                 f"events accepted. Registry: {len(g['protocols'])} new "
                 f"protocols, {g['n_runs']} recorded runs, "
                 f"{len(g['supersessions'])} supersessions. {IMPLICATION}")
    problems = lint_text(body_text, pages_mode=True)
    if problems or FORBIDDEN.search(body_text):
        print(f"WEEKLY NOTE RAIL FAILURE: {problems}")
        return 1

    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · Weekly Evidence Note</title>
  <meta name="description" content="Auto-drafted weekly note from live evidence sources. Research only — not investment advice.">
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:Inter,sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:900px;margin:0 auto;padding:24px}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:10px}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    li{{margin-left:18px;font-size:13px;color:#A0AEC0;margin-bottom:4px}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    .footer{{text-align:center;padding:16px;color:#718096;font-size:11px}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Weekly Evidence Note", active="weekly_note.html")}
    <h1 style="font-size:24px;font-weight:800;margin-bottom:4px">Weekly Evidence Note</h1>
    <p style="font-size:13px;color:#718096;margin-bottom:14px;font-family:JetBrains Mono,monospace">
      week of {start} → {end} · auto-drafted from live sources · built {escape(built)}</p>
    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}
      Every sentence below is a template filled from queried values; nothing is hand-written.</div>

    <div class="panel">
      <div class="panel-title">Ingestion</div>
      <p style="font-size:13px;color:#A0AEC0">{g['filings']} new filings across {g['days']} archived
      days; {g['events']} events accepted into the evidence store.</p>
    </div>

    <div class="panel">
      <div class="panel-title">Registry activity</div>
      <p style="font-size:13px;color:#A0AEC0;margin-bottom:6px">{g['n_runs']} recorded runs this week.
      New protocols:</p>
      <ul>{proto_list}</ul>
      <p style="font-size:13px;color:#A0AEC0;margin:8px 0 6px">Supersessions:</p>
      <ul>{sup_list}</ul>
    </div>

    <div class="panel">
      <div class="panel-title">Research questions (hypothesis registry)</div>
      <ul>{q_list}</ul>
    </div>

    <p style="font-size:12px;color:#718096">{escape(IMPLICATION)}</p>
    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}</div>
    <div class="footer">YUCLAW Weekly Evidence Note · built {escape(built)} ·
      <a href="index.html" style="color:#00E676">home</a> · research &amp; education only</div>
  </div>
</body>
</html>
"""
    page_problems = lint_text(html, pages_mode=True)
    if page_problems or FORBIDDEN.search(html):
        print(f"WEEKLY NOTE PAGE RAIL FAILURE: {page_problems[:3]}")
        return 1
    OUT.write_text(html)
    print(f"[weekly-note] wrote {OUT} ({start} -> {end}; "
          f"{g['filings']} filings, {g['n_runs']} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
