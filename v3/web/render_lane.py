"""
Render the positioning page "YUCLAW's lane" (docs/lane.html) — Part I of the
usefulness build (2026-07-16).

The page states the difference between an AI research assistant and an
evidence protocol — factually, respectfully, with NO competitor names and
the locked research vocabulary. Both kinds of tools are described by what
they do, never ranked.

CLI: python3 -m v3.web.render_lane
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from v3.web.useful_blocks import freshness_strip, VERSION, site_header_html, status_block_html

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "lane.html"

DISCLAIMER_LINE = ("Research & education only. Not investment advice. Everything on this page "
                   "describes methodology, not performance.")

ASSISTANT_DOES = [
    ("Search", "find filings, transcripts, and news relevant to a question"),
    ("Summarize", "condense a document or a quarter into readable prose"),
    ("Monitor", "watch tickers or topics and surface new items"),
    ("Converse", "answer follow-up questions in context"),
]

PROTOCOL_DOES = [
    ("Point-in-time extraction",
     "every event carries available_as_of — what was knowable, when; replays filter on it, so "
     "nothing ingested later can leak into an earlier date"),
    ("Event classification",
     "filings become typed events (a locked vocabulary) with magnitude, direction, and a "
     "SourceLock-verified excerpt that must locate verbatim in the filing"),
    ("Event-study validation",
     "classified events are tested against subsequent abnormal returns and reported as measured — "
     "including where the result is adverse to the hypothesis"),
    ("Public replay",
     "one command re-derives every published statistic from published derived data on anyone's "
     "machine — no account, no API key"),
    ("Ledger anchoring",
     "each day's signal content-hashes roll into a daily root committed to a public git "
     "repository before pages update; edits after the fact are detectable"),
    ("Methodology boundaries",
     "scoring universe and evidence tier are separated by positive gating with a standing "
     "negative check; coverage percentages are stated as measured"),
    ("Adverse-result disclosure",
     "underpowered windows, outages, and results that go against the hypothesis are disclosed "
     "and never deleted — presentation may be compressed, substance may not"),
]


def render() -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    a_rows = "".join(
        f"<li style='margin:7px 0;line-height:1.6'><strong style='color:#E2E8F0'>{escape(t)}</strong>"
        f" — {escape(d)}</li>" for t, d in ASSISTANT_DOES)
    p_rows = "".join(
        f"<li style='margin:7px 0;line-height:1.6'><strong style='color:#E2E8F0'>{escape(t)}</strong>"
        f" — {escape(d)}</li>" for t, d in PROTOCOL_DOES)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YUCLAW's lane — assistant vs evidence protocol</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#0B0E14;color:#E2E8F0;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px}}
  .container{{max-width:900px;margin:0 auto;padding:28px 20px}}
  a{{color:#00E676;text-decoration:none}} a:hover{{text-decoration:underline}}
  code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:'JetBrains Mono',monospace;font-size:11.5px}}
  .header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px}}
  .logo{{font-size:19px;font-weight:800;color:#FFF;letter-spacing:1px}}
  .navlinks a{{margin-left:14px;font-size:12px;color:#A0AEC0}}
  .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
  .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px}}
  .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;line-height:1.55;color:#A0AEC0}}
  .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
  ul{{list-style:none}}
</style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="YUCLAW's lane", active="lane.html", stamp=freshness_strip())}

    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">YUCLAW's lane</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px;line-height:1.65;max-width:780px">
      AI research assistants and evidence protocols are different kinds of tools. Both are useful.
      They answer different questions, and conflating them helps no one — so here is the difference,
      stated factually. No product comparisons, no company names: categories, not competitors.
    </p>

    <div class="disclaimer-line"><strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}</div>

    <div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:20px">
      <div class="panel" style="flex:1;min-width:280px;margin-bottom:0">
        <div class="panel-title" style="color:#4DD0E1">An AI research assistant…</div>
        <p style="font-size:12px;color:#718096;margin-bottom:8px">answers "what should I read, and what does it say?"</p>
        <ul style="font-size:12.5px;color:#A0AEC0">{a_rows}</ul>
        <p style="font-size:11.5px;color:#718096;margin-top:10px;line-height:1.6">
          The output is prose for a human reader, produced on demand. Its value is speed of
          understanding. Verifying it is the reader's job.
        </p>
      </div>
      <div class="panel" style="flex:1;min-width:280px;margin-bottom:0">
        <div class="panel-title" style="color:#00E676">An evidence protocol…</div>
        <p style="font-size:12px;color:#718096;margin-bottom:8px">answers "what exactly was claimed, from what source, knowable when — and does it hold up?"</p>
        <ul style="font-size:12.5px;color:#A0AEC0">{p_rows}</ul>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">The one-sentence version</div>
      <p style="font-size:13.5px;color:#E2E8F0;line-height:1.7;max-width:800px">
        An assistant helps you <em>read</em> the evidence; a protocol makes the evidence —
        its extraction, its classification, its validation, and its record —
        <strong>independently checkable</strong>. YUCLAW is built as the second thing. Where an
        answer needs prose, the prose cites events; where it needs a number, the number replays.
      </p>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.65;margin-top:10px;max-width:800px">
        What that costs: an evidence protocol is narrower. It covers a measured universe (stated
        per page), speaks a locked vocabulary of research classifications, and refuses questions
        its evidence cannot answer — you will see "outside current evidence scope" and
        "not statistically proven" on these pages, by design.
      </p>
    </div>

    {status_block_html()}

    <div class="footer">
      YUCLAW's lane · built {escape(built)} · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> ·
      research &amp; education only
    </div>
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    html = render()
    OUT.write_text(html)
    print(f"[render_lane] wrote {OUT} ({len(html)} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
