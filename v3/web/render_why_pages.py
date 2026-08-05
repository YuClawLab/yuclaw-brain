"""
Per-name Why pages (docs/why/{TICKER}.html, 79 generated in the daily
chain). Display layer over existing data ONLY: the anatomy the CLI's
`why` shows, rendered — current label + score with threshold context,
C1-C9 component breakdown (weights + the C2/C4 disclosures inline), the
Evidence Coverage v1 term breakdown, latest accepted events with
accession-linked citations, a point-in-time label-history ribbon, and
story membership where the geometry artifacts record it.

Rails: the template copy is linted ONCE per build (template-level lint —
the AAPL page is rendered and passed through the pages rail; generated
pages differ only in injected data values). Site-walk covers these via
its generated-page pattern check (template hash + 5-page spot walk),
not by walking all 79.

Pages live in docs/why/ and use <base href="../"> so the shared header's
root-relative links resolve.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.signal.base import SIGNAL_THRESHOLDS
from v3.signal.composite import COMPONENT_WEIGHTS
from v3.web.useful_blocks import site_header_html

OUT_DIR = _REPO / "docs" / "why"
IMPLICATION = ("Investment implication: none established — no buy, sell, "
               "or alpha conclusion is supported by this page.")
COMP_NAMES = {
    "c1": "Price momentum", "c2": "Volume confirmation",
    "c3": "Sector velocity", "c4": "Macro regime", "c5": "Oil/rates/FX",
    "c6": "Event impact", "c7": "Peer correlation",
    "c8": "Cascade effect", "c9": "Model trust"}
COMP_NOTES = {
    "c2": "volume feed not wired — zero-confidence by design (C2 "
          "challenger accrues in a parallel shadow table)",
    "c4": "macro-regime input frozen as of 2026-05-18 with staleness "
          "disclosure, pending macro engine restoration"}


def _threshold_context(score: float, label: str) -> str:
    floors = [(f, l) for f, l in SIGNAL_THRESHOLDS]
    for i, (f, l) in enumerate(floors):
        if l == label:
            hi = floors[i - 1][0] if i else None
            hi_s = f"{hi:+.2f}" if hi is not None else "+∞"
            return (f"score {score:+.4f} sits in the {label} band "
                    f"[{f:+.2f}, {hi_s}) of the published threshold table")
    return f"score {score:+.4f}"


def _load_all():
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("""SELECT DISTINCT ON (ticker) ticker, signal_label,
                total_score, signal_time, c1_price_momentum,
                c2_volume_confirm, c3_sector_velocity, c4_macro_regime,
                c5_oil_rates_fx, c6_event_impact, c7_peer_correlation,
                c8_cascade_effect, c9_model_trust
                FROM signal_snapshots WHERE is_backfill = false
                ORDER BY ticker, signal_time DESC""")
            snaps = {r[0]: r for r in cur.fetchall()}
            cur.execute("""SELECT ticker, signal_time::date, signal_label
                FROM (SELECT DISTINCT ON (ticker, signal_time::date)
                        ticker, signal_time, signal_label
                      FROM signal_snapshots WHERE is_backfill = false
                      ORDER BY ticker, signal_time::date,
                               signal_time DESC) s
                ORDER BY ticker, signal_time::date DESC""")
            hist: dict[str, list] = {}
            for tk, d, lbl in cur.fetchall():
                hist.setdefault(tk, [])
                if len(hist[tk]) < 30:
                    hist[tk].append((d, lbl))
            cur.execute("""SELECT ticker, event_type, magnitude, direction,
                       available_as_of, source_type, source_url,
                       raw_excerpt,
                       extract(epoch FROM now() - available_as_of)/86400
                FROM (SELECT *, row_number() OVER (PARTITION BY ticker
                          ORDER BY available_as_of DESC) rn
                      FROM events WHERE event_status='accepted') e
                WHERE rn <= 5""")
            events: dict[str, list] = {}
            for r in cur.fetchall():
                events.setdefault(r[0], []).append(r)
    try:
        ecs = json.loads((_REPO / "output" / "oie" /
                          "evidence_coverage.json").read_text())["scores"]
    except Exception:
        ecs = {}
    stories = {}
    try:
        geo = json.loads((_REPO / "output" / "oie" /
                          "evidence_geometry.json").read_text())["results"]
        for lens, v in geo.items():
            for i, s in enumerate(v.get("top5_stories", []), 1):
                stories.setdefault(s["dominant_issuer"], []).append(
                    (lens, i, s))
    except Exception:
        pass
    return snaps, hist, events, ecs, stories


LBL_COLOR = {"STRONG_BULLISH": "#00E676", "BULLISH": "#00E676",
             "NEUTRAL": "#A0AEC0", "WATCH": "#A0AEC0",
             "WEAKENING": "#FF3366", "NEGATIVE_EVENT": "#FF3366",
             "BEARISH_WATCH": "#FF3366", "RISK_ALERT": "#FBA94B"}


def _page(tk, snap, hist, events, ecs, stories, stamp) -> str:
    _t, label, score, st, *comps = snap
    color = LBL_COLOR.get(label, "#A0AEC0")
    header = site_header_html(subtitle=f"Why {tk}", stamp=f"built {stamp}")
    comp_rows = []
    for i, cid in enumerate(("c1", "c2", "c3", "c4", "c5", "c6", "c7",
                             "c8", "c9")):
        v = comps[i]
        v = float(v) if v is not None else 0.0
        w = COMPONENT_WEIGHTS[cid]
        bw = min(100, abs(v) * 100)
        bc = "#00E676" if v > 0 else "#FF3366" if v < 0 else "#3A4150"
        note = COMP_NOTES.get(cid)
        note_html = (f"<div class='cnote'>{note}</div>" if note else "")
        comp_rows.append(f"""
        <div class="crow">
          <div class="cname">{cid.upper()} {COMP_NAMES[cid]}
            <span class="cw">w={w:.2f}</span></div>
          <div class="cbarwrap"><div class="cbar" style="width:{bw:.0f}%;
            background:{bc}"></div></div>
          <div class="cval">{v:+.3f}</div>
          {note_html}
        </div>""")
    e = ecs.get(tk, {})
    ev_rows = "".join(f"""
        <div class="ev">
          <div class="evhead"><span class="evtype">{escape(r[1])}</span>
            <span class="evmeta">magnitude {r[2]:.2f} · direction {r[3]:+d} ·
            {escape(r[5])} · {r[8]:.1f} days ago</span></div>
          <div class="evex">{escape((r[7] or '')[:260])}</div>
          <a class="evlink" href="{escape(r[6])}">source filing ↗</a>
        </div>""" for r in events.get(tk, [])) or (
        "<p class='muted'>No accepted events currently on record for this "
        "name — absence of evidence is disclosed, never imputed.</p>")
    ribbon = "".join(
        f"<span class='rb' title='{d} {lbl}' "
        f"style='background:{LBL_COLOR.get(lbl, '#3A4150')}'></span>"
        for d, lbl in reversed(hist.get(tk, [])))
    st_list = stories.get(tk, [])
    story_html = "".join(
        f"<p>This name dominates story #{i} in the {lens} lens "
        f"({s['size']} events, {s['mass_pct']}% of that lens's event mass, "
        f"dominant type {s['dominant_type']}) — see the Evidence structure "
        f"panel on the lens page.</p>" for lens, i, s in st_list) or (
        "<p class='muted'>No mega-story membership recorded for this name "
        "in the current evidence-geometry artifacts.</p>")
    rec = e.get("recency_days")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<base href="../">
<title>Why {tk} — YUCLAW classification anatomy</title>
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:900px;margin:0 auto;padding:24px}}
 h2{{font-size:16px;color:#FFF;margin:22px 0 10px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:20px;margin-bottom:14px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .amber strong{{color:#FBA94B}}
 .mono{{font-family:'JetBrains Mono',monospace}}
 .muted{{color:#718096;font-size:12px}}
 .biglabel{{display:inline-block;padding:6px 16px;border-radius:6px;font-weight:800;letter-spacing:0.5px}}
 .crow{{display:grid;grid-template-columns:220px 1fr 70px;gap:10px;align-items:center;margin:7px 0}}
 .cname{{font-size:12px;color:#CBD5E1}}
 .cw{{color:#718096;font-family:'JetBrains Mono',monospace;font-size:10px}}
 .cbarwrap{{background:#10141C;border-radius:4px;height:10px;overflow:hidden}}
 .cbar{{height:10px}}
 .cval{{font-family:'JetBrains Mono',monospace;font-size:12px;text-align:right}}
 .cnote{{grid-column:1/4;font-size:11px;color:#FBA94B;padding-left:4px}}
 .terms{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
 .term{{background:#10141C;border:1px solid #1E232D;border-radius:8px;padding:12px;text-align:center}}
 .term .v{{font-family:'JetBrains Mono',monospace;font-size:20px;color:#FFF}}
 .term .k{{font-size:10.5px;color:#718096;margin-top:3px}}
 .ev{{border-top:1px solid #1E232D;padding:10px 0}}
 .evtype{{color:#00E676;font-weight:700;font-size:12px;font-family:'JetBrains Mono',monospace}}
 .evmeta{{color:#718096;font-size:11px;margin-left:8px}}
 .evex{{font-size:12px;color:#A0AEC0;margin:5px 0}}
 .evlink{{font-size:11px;color:#00E676}}
 .rb{{display:inline-block;width:11px;height:16px;border-radius:2px;margin-right:2px}}
</style>
</head>
<body><div class="container">
{header}
<div class="card">
  <h1 style="font-size:24px;color:#FFF">Why {tk}</h1>
  <p style="margin:10px 0 6px"><span class="biglabel"
    style="background:{color}26;color:{color};border:1px solid {color}80">{label}</span>
    <span class="mono" style="font-size:20px;margin-left:12px;color:#FFF">{float(score):+.4f}</span></p>
  <p class="muted">{_threshold_context(float(score), label)} ·
    snapshot {st.strftime('%Y-%m-%d %H:%M UTC')} · point-in-time, never edited</p>
</div>
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations.
{IMPLICATION}</div>

<div class="card"><h2>Component breakdown (C1–C9, confidence-weighted composite)</h2>
{''.join(comp_rows)}
<p class="muted" style="margin-top:8px">Weights are the published composite weights; component scores are
the current snapshot's stored values. C6 event impact carries the highest single weight by design —
evidence is meant to correct price-only signals, not echo them.</p></div>

<div class="card"><h2>Evidence coverage — the four terms</h2>
<div class="terms">
  <div class="term"><div class="v">{e.get('ecs', '—')}</div><div class="k">ECS (0–100)</div></div>
  <div class="term"><div class="v">{e.get('events_90d', '—')}</div><div class="k">accepted events, 90d</div></div>
  <div class="term"><div class="v">{rec if rec is not None else '—'}</div><div class="k">days since latest event</div></div>
  <div class="term"><div class="v">{e.get('type_diversity', '—')}</div><div class="k">distinct event types</div></div>
  <div class="term"><div class="v">{e.get('substrate_active', '—')}</div><div class="k">substrate active (0/1)</div></div>
</div>
<p class="muted" style="margin-top:8px">Evidence Coverage v1 (registered protocol): how much evidence stands
under this classification — coverage, not prediction.</p></div>

<div class="card"><h2>Latest accepted events</h2>{ev_rows}</div>

<div class="card"><h2>Label history (last {len(hist.get(tk, []))} snapshot days)</h2>
<div>{ribbon}</div>
<p class="muted" style="margin-top:6px">Point-in-time record, oldest → newest; colors follow the label
legend on the home page. Never edited after the fact.</p></div>

<div class="card"><h2>Story membership</h2>{story_html}</div>

<div class="amber"><strong>Research and education only — not investment advice.</strong>
{IMPLICATION} Past results — in-sample or forward-tracked — do not predict future performance.</div>
<p class="muted">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a> ·
<a href="explorer.html" style="color:#A0AEC0">Universe Explorer</a> · built {stamp}</p>
</div></body></html>"""


def template_hash() -> str:
    """Hash of this generator's source — the site-walk pattern check pins
    it so template drift is visible."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(exist_ok=True)
    snaps, hist, events, ecs, stories = _load_all()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for tk, snap in sorted(snaps.items()):
        safe = tk.replace(".", "-")
        (OUT_DIR / f"{safe}.html").write_text(
            _page(tk, snap, hist, events, ecs, stories, stamp))
    # template-level lint: the AAPL page stands in for the template copy
    sys.path.insert(0, str(_REPO / "tools"))
    from check_language import lint_text
    sample = (OUT_DIR / "AAPL.html").read_text()
    bad = lint_text(sample, pages_mode=True)
    if bad:
        for b in bad:
            print(f"TEMPLATE RAIL FAIL line {b['line_no']}: [{b['word']}] "
                  f"{b['line']}")
        return 1
    dt = time.time() - t0
    print(f"[render_why_pages] {len(snaps)} pages in {dt:.1f}s · template "
          f"{template_hash()} · template-rail clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
