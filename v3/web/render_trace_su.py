"""
Render the Suncor evidence-trace page (docs/trace_su.html) — Part B of the
usefulness build (2026-07-16): ONE real filing followed end to end,

    filing → exhibit → extracted prose → event type → grade → C6 posture

Every value on the page is pulled live from the same substrate the Canada
Resources page renders (events_raw / yuclaw_v5.swarm_inputs / events /
canada_posture / output/swarm/canada/*.json) — nothing hand-typed.

The traced filing is fixed: Suncor Energy (SU) 6-K, accession
0001104659-26-055746 (2026-05-06 results release) — chosen because it is
complete across every pipeline layer. Evidence-tier name: displayed, never
scored.

CLI: python3 -m v3.web.render_trace_su
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import psycopg2

from v3.web.useful_blocks import (footer_stamp_html, freshness_strip, VERSION,
                                  site_header_html, use_in_research_html)

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "trace_su.html"
DSN = "dbname=yuclaw_events"

TICKER = "SU"
ACCESSION = "0001104659-26-055746"
C6_JSON = _REPO / "output" / "swarm" / "canada" / f"{ACCESSION}.json"

DISCLAIMER_LINE = ("Research & education only. Not investment advice. Event types and "
                   "grades are research classifications, not buy/sell recommendations.")

EXCERPT_CHARS = 700


def _fetch() -> dict:
    """Pull every layer of the trace from the live substrate."""
    out: dict = {"ticker": TICKER, "accession": ACCESSION}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT source_type, source_url, source_publish_time, fetched_at,
                          extraction_status
                   FROM events_raw WHERE accession_number = %s""", (ACCESSION,))
            r = cur.fetchone()
            if not r:
                raise RuntimeError(f"trace filing {ACCESSION} not in events_raw")
            out["filing"] = {"form": r[0], "url": r[1], "published": r[2],
                             "fetched": r[3], "status": r[4]}

            cur.execute(
                """SELECT narrative_section, char_len, narrative_text
                   FROM yuclaw_v5.swarm_inputs WHERE accession_number = %s
                   ORDER BY narrative_section""", (ACCESSION,))
            out["exhibits"] = [{"section": a, "chars": b, "text": c}
                               for a, b, c in cur.fetchall()]

            cur.execute(
                """SELECT event_id, event_type, magnitude, direction, llm_confidence,
                          raw_excerpt, llm_reasoning, event_status, available_as_of,
                          llm_model
                   FROM events
                   WHERE ticker = %s
                     AND event_id LIKE %s || '\\_' || '20260506' || '\\_%%'
                   ORDER BY event_id""", (TICKER, TICKER))
            out["events"] = [dict(zip(
                ("event_id", "event_type", "magnitude", "direction", "confidence",
                 "excerpt", "reasoning", "status", "available_as_of", "model"), row))
                for row in cur.fetchall()]

    # Evidence grade: the SAME member record the Canada page renders.
    from v3.lab.etf_evidence import canada_posture
    member = next((m for m in canada_posture("XEG")["members"]
                   if m["ticker"] == TICKER), None)
    out["member"] = member

    out["c6"] = json.loads(C6_JSON.read_text()) if C6_JSON.exists() else None
    return out


def _step(n: int, title: str, sub: str, body: str, color: str = "#00E676") -> str:
    return f"""
    <div style="background:#151A23;border:1px solid #1E232D;border-left:3px solid {color};
                border-radius:12px;padding:20px 22px;margin-bottom:14px" id="step{n}">
      <div style="font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:{color}">Step {n}</div>
      <div style="font-size:15px;font-weight:800;color:#FFF;margin:2px 0 2px">{escape(title)}</div>
      <div style="font-size:11.5px;color:#718096;margin-bottom:10px">{sub}</div>
      {body}
    </div>"""


def render(d: dict) -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    f = d["filing"]

    # 1 — filing
    s1 = _step(1, f"SEC filing — {TICKER} {f['form']}",
               f"accession <code>{escape(ACCESSION)}</code> · accepted by EDGAR {escape(str(f['published']))}",
               f"""<p style="font-size:12.5px;color:#A0AEC0;line-height:1.65;margin:0">
        Suncor Energy furnished this 6-K to the SEC. YUCLAW's live poller picked it up from the
        issuer's EDGAR submissions index and recorded it with a canonical accession number
        (ingestion status: <code>{escape(f['status'])}</code>).
        <a href="{escape(f['url'])}">Open the primary document on sec.gov →</a></p>""")

    # 2 — exhibit
    ex_rows = "".join(
        f"<li style='margin:4px 0'><code>{escape(e['section'])}</code> — {e['chars']:,} characters ingested</li>"
        for e in d["exhibits"])
    ex0 = d["exhibits"][0] if d["exhibits"] else None
    quote = escape(ex0["text"][:EXCERPT_CHARS]) + "…" if ex0 else "—"
    s2 = _step(2, "Exhibit → extracted prose",
               "6-K filings carry the substance in EX-99.x exhibits; the envelope has no item codes",
               f"""<ul style="list-style:none;padding:0;font-size:12px;color:#A0AEC0">{ex_rows}</ul>
        <div style="background:#0B0E14;border:1px solid #1E232D;border-radius:8px;padding:12px 14px;
                    font-size:11.5px;color:#A0AEC0;line-height:1.6;margin-top:8px;font-family:JetBrains Mono,monospace">
          {quote}
        </div>
        <p style="font-size:11px;color:#718096;margin:8px 0 0">Clean exhibit prose, exactly as stored in
        the extraction substrate (<code>yuclaw_v5.swarm_inputs</code>) — this text, not the raw HTML
        envelope, is what downstream classification reads.</p>""", "#4DD0E1")

    # 3 — event
    ev_rows = ""
    for e in d["events"]:
        ev_rows += f"""
        <div style="background:#0B0E14;border:1px solid #1E232D;border-radius:8px;padding:12px 14px;margin-top:8px">
          <div style="font-size:12px"><code>{escape(e['event_id'])}</code></div>
          <div style="font-size:13px;color:#E2E8F0;margin:4px 0">
            <strong>{escape(e['event_type'])}</strong> · magnitude {e['magnitude']:.1f} · direction {e['direction']:+d}
            · extraction confidence {e['confidence']:.1f} · status <code>{escape(e['status'])}</code>
          </div>
          <div style="font-size:12px;color:#A0AEC0;line-height:1.6">
            <strong style="color:#718096">Verified quote (SourceLock):</strong> “{escape(e['excerpt'] or '')}”
          </div>
          <div style="font-size:11.5px;color:#718096;line-height:1.6;margin-top:4px">
            Extractor rationale ({escape(e['model'] or '')}): {escape(e['reasoning'] or '—')}
          </div>
        </div>"""
    s3 = _step(3, "Classified evidence event",
               "deterministic schema: type · magnitude · direction · confidence · verified excerpt",
               (ev_rows or "<p style='font-size:12px;color:#718096'>no accepted event for this filing</p>")
               + """<p style="font-size:11px;color:#718096;margin:8px 0 0">The excerpt is
        SourceLock-verified — it must locate verbatim in the filing text or the event is rejected.
        Event types are research classifications from a locked vocabulary, not recommendations.</p>""",
               "#7C4DFF")

    # 4 — grade
    m = d["member"]
    grade_body = ("<p style='font-size:12px;color:#718096'>member record unavailable</p>" if not m else f"""
        <p style="font-size:12.5px;color:#A0AEC0;line-height:1.65;margin:0">
        On the Canada Resources page, {escape(m['sec_name'][:40])} currently carries evidence grade
        <strong style="color:#E2E8F0">{escape(m['grade'])}</strong> — derived deterministically from
        coverage depth: <strong style="color:#E2E8F0">{m['n_filings']}</strong> filings ingested,
        <strong style="color:#E2E8F0">{m['prose_filings']}</strong> with exhibit/MD&amp;A prose,
        <strong style="color:#E2E8F0">{m['n_events']}</strong> accepted events. Grades describe how much
        evidence is on file, never desirability. Insider substrate: {escape(m['insider_scope'])}.</p>""")
    s4 = _step(4, "Evidence grade (coverage depth)",
               "the same member record the Canada Resources page renders — pulled live, not copied",
               grade_body, "#FBA94B")

    # 5 — C6 posture
    c6 = d["c6"]
    if c6:
        rc = c6["risk_channel"]
        drivers = "".join(f"<li style='margin:2px 0'>{escape(x)}</li>" for x in rc.get("drivers", []))
        contribs = " · ".join(f"{escape(k)}: {escape(v)}" for k, v in rc.get("contributors", {}).items())
        c6_body = f"""
        <p style="font-size:12.5px;color:#A0AEC0;line-height:1.65;margin:0 0 8px">
          The v5 specialist swarm read this filing's prose and produced a risk-channel posture —
          <strong style="color:#E2E8F0">level {escape(str(rc['level']))} / flag {escape(str(rc['flag']))}</strong>
          (aggregation <code>{escape(str(rc['agg']))}</code>, insider gate
          <code>{str(rc.get('insider_gate', False)).lower()}</code>). Posture is display-layer evidence
          context for the Canada page — it never enters composite scoring for evidence-tier names.
        </p>
        <div style="font-size:11.5px;color:#718096">Flagged drivers (counts and classifications, no judgments):</div>
        <ul style="font-size:11.5px;color:#A0AEC0;margin:4px 0 8px 18px">{drivers}</ul>
        <div style="font-size:11px;color:#718096">Per-agent contribution: {contribs} · grounding-verified
        quotes only (verifier: <code>v5/swarm/grounding.py</code>)</div>"""
    else:
        c6_body = "<p style='font-size:12px;color:#718096'>no C6 posture artifact for this filing</p>"
    s5 = _step(5, "C6 posture (risk channel)", "specialist-swarm reading of the same filing — evidence display, never a score",
               c6_body, "#FF3366")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YUCLAW — one evidence trace, end to end (Suncor 6-K)</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#0B0E14;color:#E2E8F0;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px}}
  .container{{max-width:900px;margin:0 auto;padding:28px 20px}}
  a{{color:#00E676;text-decoration:none}} a:hover{{text-decoration:underline}}
  code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:'JetBrains Mono',monospace;font-size:11.5px}}
  .header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px}}
  .logo{{font-size:19px;font-weight:800;color:#FFF;letter-spacing:1px}}
  .navlinks a{{margin-left:14px;font-size:12px;color:#A0AEC0}}
  .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;line-height:1.55;color:#A0AEC0}}
  .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
</style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Evidence trace", active="trace_su.html")}

    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">One evidence trace, end to end</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px;line-height:1.6">
      A single real filing — Suncor Energy's Q1-2026 results 6-K — followed through every stage of
      YUCLAW's evidence pipeline. Every value below is pulled live from the same data the public
      pages render. Suncor is an <strong>evidence-tier</strong> name: ingested, classified, displayed —
      never scored.
    </p>

    <div class="disclaimer-line"><strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}</div>

    {s1}{s2}{s3}{s4}{s5}

    {use_in_research_html(None)}

    {footer_stamp_html(freshness_strip())}
    <div class="footer">
      YUCLAW evidence trace · {TICKER} {escape(f['form'])} <code>{escape(ACCESSION)}</code> ·
      rebuilt {escape(built)} · <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> ·
      research &amp; education only
    </div>
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    html = render(_fetch())
    OUT.write_text(html)
    print(f"[render_trace_su] wrote {OUT} ({len(html)} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
