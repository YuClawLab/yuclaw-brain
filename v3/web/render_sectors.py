"""
Sector overview (docs/sectors.html). Display layer over existing data
ONLY — per-sector cards: name count, label-distribution mini-bars,
median composite + median ECS (descriptive medians of current
classifications — display, not inference), fresh-evidence weight
(% of names with accepted events <= 7 days old), link into the Explorer
pre-filtered. The U350 plan's sector view, proven on U79 first.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import site_header_html

OUT = _REPO / "docs" / "sectors.html"
LBL_COLOR = {"STRONG_BULLISH": "#00E676", "BULLISH": "#00E676",
             "NEUTRAL": "#A0AEC0", "WATCH": "#A0AEC0",
             "WEAKENING": "#FF3366", "NEGATIVE_EVENT": "#FF3366",
             "BEARISH_WATCH": "#FF3366", "RISK_ALERT": "#FBA94B"}
LABELS = ["STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH", "WEAKENING",
          "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT"]


def main() -> int:
    data = json.loads((_REPO / "docs" / "explorer_data.json").read_text())
    rows = data["rows"]
    sectors: dict[str, list] = {}
    for r in rows:
        sectors.setdefault(r["sector"], []).append(r)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = site_header_html(subtitle="Sector overview",
                              stamp=f"built {stamp}",
                              active="sectors.html")
    cards = []
    for sec in sorted(sectors, key=lambda s: -len(sectors[s])):
        rs = sectors[sec]
        n = len(rs)
        med_score = statistics.median(r["score"] for r in rs)
        ecs_vals = [r["ecs"] for r in rs if r["ecs"] is not None]
        med_ecs = statistics.median(ecs_vals) if ecs_vals else None
        fresh = sum(1 for r in rs if r["evidence_age_days"] is not None
                    and r["evidence_age_days"] <= 7)
        counts = {l: sum(1 for r in rs if r["label"] == l) for l in LABELS}
        bars = "".join(
            f"<div title='{l}: {c}' style='flex:{c};background:"
            f"{LBL_COLOR[l]};min-width:{2 if c else 0}px'></div>"
            for l, c in counts.items() if c)
        cards.append(f"""
      <a class="seccard" href="explorer.html?sector={quote(sec)}">
        <div class="sechead">{sec} <span class="secn">{n} names</span></div>
        <div class="minibar">{bars}</div>
        <div class="secstats">
          <span>median score <b class="mono">{med_score:+.3f}</b></span>
          <span>median coverage <b class="mono">{med_ecs if med_ecs is not None else '—'}</b></span>
          <span>fresh evidence ≤7d <b class="mono">{fresh}/{n}</b></span>
        </div>
      </a>""")
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW Sector overview — 79 names by sector</title>
<meta name="description" content="Per-sector view of the scoring universe: label distributions, descriptive medians, evidence freshness. Research classifications, not recommendations.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.55}}
 .container{{max-width:1060px;margin:0 auto;padding:24px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin-bottom:14px}}
 .amber strong{{color:#FBA94B}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
 .seccard{{display:block;background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:18px;
           text-decoration:none;color:#E2E8F0}}
 .seccard:hover{{border-color:#00E67650}}
 .sechead{{font-weight:800;color:#FFF;font-size:15px;margin-bottom:10px}}
 .secn{{color:#718096;font-size:11px;font-weight:400;margin-left:6px}}
 .minibar{{display:flex;height:10px;border-radius:5px;overflow:hidden;gap:1px;margin-bottom:10px;background:#10141C}}
 .secstats{{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:#A0AEC0}}
 .secstats b{{color:#FFF;font-weight:600}}
 .muted{{color:#718096;font-size:12px}}
</style>
</head>
<body><div class="container">
{header}
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations. All figures below are
descriptive medians of current classifications — display, not inference. Coverage is coverage,
not prediction.</div>
<div class="grid">{''.join(cards)}</div>
<p class="muted" style="margin-top:14px">Each card links into the Universe Explorer pre-filtered to its
sector. Data generated {data['generated'][:16]} UTC · point-in-time, never edited · built {stamp}</p>
</div></body></html>""")
    print(f"[render_sectors] {len(sectors)} sector cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
