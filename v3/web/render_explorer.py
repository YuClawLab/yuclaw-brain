"""
Universe Explorer (docs/explorer.html + docs/explorer_data.json).

Display layer over existing data ONLY — no new registered statistics.
Every number here already exists in the canonical record (latest OOS
snapshot, Evidence Coverage v1 artifact, accepted-event counts); the
page renders counts as display with captions, never badges.

Client-side filter/sort over the embedded JSON: zero network calls,
zero forms. The filter <input> and dropdown <select> elements carry no
name attribute — the documented transmit-nothing exemption in
tools/check_no_forms.py (F1 bans <form> outright, so nothing can
submit; nothing is transmitted anywhere).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.web.useful_blocks import site_header_html

OUT_HTML = _REPO / "docs" / "explorer.html"
OUT_JSON = _REPO / "docs" / "explorer_data.json"

SECTOR_NAMES = {
    "XLK": "Technology", "XLC": "Communications", "XLF": "Financials",
    "XLE": "Energy", "XLV": "Health Care", "XLI": "Industrials",
    "XLY": "Consumer Disc.", "XLP": "Consumer Staples", "XLB": "Materials",
    "XLRE": "Real Estate", "XLU": "Utilities", "SMH": "Semiconductors",
    "KRE": "Regional Banks", "IBB": "Biotech", "XBI": "Biotech",
}


def sector_of(tk: str, u: dict) -> str:
    from v3.signal.components.c3_sector_velocity import TICKER_TO_SECTOR_ETF
    if tk in u.get("sector_etfs", []):
        return "Sector ETF"
    if tk in u.get("broad_etfs", []):
        return "Broad ETF"
    if tk in u.get("macro", []):
        return "Macro"
    etf = TICKER_TO_SECTOR_ETF.get(tk)
    return SECTOR_NAMES.get(etf, "Other") if etf else "Other"


def grade_of(ecs) -> str:
    """Display bucket of the coverage score — coverage, not prediction."""
    if ecs is None:
        return "n/a"
    if ecs >= 75:
        return "High"
    if ecs >= 40:
        return "Medium"
    if ecs >= 1:
        return "Thin"
    return "None"


def build_data() -> dict:
    u = json.loads((_REPO / "v3" / "universe.json").read_text())
    try:
        ecs_art = json.loads((_REPO / "output" / "oie" /
                              "evidence_coverage.json").read_text())["scores"]
    except Exception:
        ecs_art = {}
    rows = []
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("""SELECT DISTINCT ON (ticker) ticker, signal_label,
                total_score, signal_time FROM signal_snapshots
                WHERE is_backfill = false ORDER BY ticker, signal_time DESC""")
            snaps = {r[0]: r for r in cur.fetchall()}
            cur.execute("""SELECT ticker, count(*),
                       extract(epoch FROM now() - max(available_as_of))/86400
                FROM events WHERE event_status='accepted'
                  AND available_as_of > now() - interval '30 days'
                GROUP BY ticker""")
            ev30 = {r[0]: (r[1], round(float(r[2]), 1))
                    for r in cur.fetchall()}
            cur.execute("""SELECT ticker,
                       extract(epoch FROM now() - max(available_as_of))/86400
                FROM events WHERE event_status='accepted' GROUP BY ticker""")
            age_all = {r[0]: round(float(r[1]), 1) for r in cur.fetchall()}
    for tk in sorted(snaps):
        _t, label, score, st = snaps[tk]
        e = ecs_art.get(tk, {})
        ecs = e.get("ecs")
        rows.append({
            "ticker": tk, "label": label, "score": round(float(score), 4),
            "ecs": ecs, "grade": grade_of(ecs),
            "sector": sector_of(tk, u),
            "events_30d": ev30.get(tk, (0, None))[0],
            "evidence_age_days": age_all.get(tk),
            "why": f"why/{tk.replace('.', '-')}.html",
        })
    return {"generated": datetime.now(timezone.utc).isoformat(),
            "caption": "research classifications — not recommendations; "
                       "counts and coverage are display, never inference",
            "rows": rows}


def render(data: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = site_header_html(subtitle="Universe Explorer",
                              stamp=f"built {stamp}",
                              active="explorer.html")
    sectors = sorted({r["sector"] for r in data["rows"]})
    labels = ["STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH", "WEAKENING",
              "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT"]
    grades = ["High", "Medium", "Thin", "None", "n/a"]
    opt = lambda xs: "".join(f'<option value="{x}">{x}</option>' for x in xs)
    payload = json.dumps(data["rows"], separators=(",", ":"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW Universe Explorer — 79 names, filterable</title>
<meta name="description" content="The full 79-name scoring universe: labels, scores, evidence coverage — filterable and sortable, entirely in your browser. Research classifications, not recommendations.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.5}}
 .container{{max-width:1100px;margin:0 auto;padding:24px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin-bottom:14px}}
 .amber strong{{color:#FBA94B}}
 .bar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}}
 input,select{{background:#151A23;border:1px solid #1E232D;border-radius:8px;color:#E2E8F0;padding:8px 12px;font-size:13px}}
 table{{width:100%;border-collapse:collapse;background:#151A23;border:1px solid #1E232D;border-radius:12px;overflow:hidden}}
 th{{padding:10px 12px;color:#718096;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;text-align:left;cursor:pointer;user-select:none;background:#10141C}}
 th:hover{{color:#00E676}}
 td{{padding:9px 12px;border-top:1px solid #1E232D;font-size:13px}}
 td a{{color:#FFF;text-decoration:none;font-weight:600}}
 td a:hover{{color:#00E676}}
 .lbl{{padding:3px 9px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:0.4px}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 .muted{{color:#718096;font-size:12px}}
 .capline{{background:#151A23;border:1px solid #1E232D;border-bottom:none;border-radius:12px 12px 0 0;padding:10px 14px;font-size:12px;color:#A0AEC0}}
</style>
</head>
<body><div class="container">
{header}
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations. Evidence coverage is coverage,
not prediction. Nothing on this page transmits anything — filtering and sorting run entirely in your browser
over data embedded in the page.</div>

<div class="bar">
  <input id="ftk" placeholder="filter ticker…" oninput="refresh()" style="width:160px">
  <select id="flb" onchange="refresh()"><option value="">all labels</option>{opt(labels)}</select>
  <select id="fgr" onchange="refresh()"><option value="">all evidence grades</option>{opt(grades)}</select>
  <select id="fsc" onchange="refresh()"><option value="">all sectors</option>{opt(sectors)}</select>
</div>

<div class="capline">research classifications — not recommendations · evidence grade = display bucket of the
coverage score (coverage, not prediction) · <span id="count"></span></div>
<table>
  <thead><tr>
    <th onclick="sortBy('ticker')">Ticker</th>
    <th onclick="sortBy('label')">Label</th>
    <th onclick="sortBy('score')">Score ▾</th>
    <th onclick="sortBy('ecs')">Evidence coverage</th>
    <th onclick="sortBy('grade')">Grade</th>
    <th onclick="sortBy('sector')">Sector</th>
    <th onclick="sortBy('events_30d')">Events 30d</th>
    <th onclick="sortBy('evidence_age_days')">Evidence age (d)</th>
  </tr></thead>
  <tbody id="tb"></tbody>
</table>
<p class="muted" style="margin-top:10px">Every row links to its Why page — the full anatomy of the current
classification. Data generated {data['generated'][:16]} UTC · point-in-time, never edited.</p>

<script>
const ROWS = {payload};
const COLORS = {{"STRONG_BULLISH":"#00E676","BULLISH":"#00E676","NEUTRAL":"#A0AEC0","WATCH":"#A0AEC0",
"WEAKENING":"#FF3366","NEGATIVE_EVENT":"#FF3366","BEARISH_WATCH":"#FF3366","RISK_ALERT":"#FBA94B"}};
let sortKey = "score", sortDir = -1;
function sortBy(k) {{
  if (sortKey === k) sortDir = -sortDir; else {{ sortKey = k; sortDir = -1; }}
  refresh();
}}
function refresh() {{
  const tk = document.getElementById("ftk").value.toUpperCase();
  const lb = document.getElementById("flb").value;
  const gr = document.getElementById("fgr").value;
  const sc = document.getElementById("fsc").value;
  let rows = ROWS.filter(r =>
    (!tk || r.ticker.includes(tk)) && (!lb || r.label === lb) &&
    (!gr || r.grade === gr) && (!sc || r.sector === sc));
  rows.sort((a, b) => {{
    let x = a[sortKey], y = b[sortKey];
    if (x == null) return 1; if (y == null) return -1;
    if (typeof x === "string") return sortDir * x.localeCompare(y);
    return sortDir * (x - y);
  }});
  document.getElementById("count").textContent = rows.length + " of " + ROWS.length + " names";
  document.getElementById("tb").innerHTML = rows.map(r => {{
    const c = COLORS[r.label] || "#A0AEC0";
    return `<tr><td><a href="${{r.why}}">${{r.ticker}}</a></td>` +
      `<td><span class="lbl" style="background:${{c}}26;color:${{c}};border:1px solid ${{c}}80">${{r.label}}</span></td>` +
      `<td class="mono" style="color:${{r.score > 0 ? "#00E676" : r.score < 0 ? "#FF3366" : "#A0AEC0"}}">${{r.score >= 0 ? "+" : ""}}${{r.score.toFixed(3)}}</td>` +
      `<td class="mono">${{r.ecs ?? "—"}}</td><td>${{r.grade}}</td><td>${{r.sector}}</td>` +
      `<td class="mono">${{r.events_30d}}</td><td class="mono">${{r.evidence_age_days ?? "—"}}</td></tr>`;
  }}).join("");
}}
const params = new URLSearchParams(location.search);
if (params.get("sector")) document.getElementById("fsc").value = params.get("sector");
refresh();
</script>
</div></body></html>"""


def main() -> int:
    data = build_data()
    OUT_JSON.write_text(json.dumps(data, indent=1))
    OUT_HTML.write_text(render(data))
    print(f"[render_explorer] {len(data['rows'])} rows → explorer.html + "
          f"explorer_data.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
