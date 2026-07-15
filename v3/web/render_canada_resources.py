"""Render the Canada Resources Evidence page to docs/canada_resources.html.

Static, data-baked, self-contained (inline SVG, no JS/CDNs). EVIDENCE TIER
ONLY: the 49 Canada Resources names are covered for filings evidence and
research dashboards — they are NOT scored, carry no composite scores, and are
not part of the Lab decile study or the 79-ticker forward-track universe
(positive gating in v3/universe_tiers.py). Locked research-only vocabulary.
Coverage is measured and scoped; missing data is excluded, not imputed; the
coverage disclosure renders BEFORE any dashboard visuals. Regenerated daily by
cron/refresh_v3_pages.sh with the same freshness stamp as the other pages.
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

import psycopg2

from v3.lab.cohort_engine import DSN
from v3.lab.etf_evidence import (
    CANADA_CAR_MIN_EVENTS, CANADA_LENS_KEYS, compute_canada,
)
from v3.web.render_etf_evidence import car_chart

OUT = _REPO / "docs" / "canada_resources.html"
OIL_DIR = _REPO / "output" / "oil"
C6_DIR = _REPO / "output" / "swarm" / "canada"

DISCLAIMER_FULL = (
    "Research-only evidence dashboard. Not investment advice, not performance "
    "advertising, not an offer or recommendation of any security, fund, or "
    "product. Research classifications and measured coverage statistics, not "
    "recommendations. Missing data is excluded, not imputed. Forward event "
    "studies accrue only when events mature."
)

LENS_COLOR = {"XEG": "#4DD0E1", "ZEO": "#00E676", "GDX": "#FBA94B", "URNM": "#7C4DFF"}


def _oil_context() -> dict | None:
    """Latest oil-engine brief, if cleanly available. Research-side context only —
    it does not feed scoring and does not alter evidence grades."""
    try:
        briefs = sorted(OIL_DIR.glob("*_brief.json"))
        if not briefs:
            return None
        d = json.loads(briefs[-1].read_text())
        px = d.get("prices", {})
        wti = (px.get("WTI") or {}).get("price")
        brent = (px.get("Brent") or {}).get("price")
        as_of = d.get("date") or briefs[-1].name.split("_")[0]
        if wti is None and brent is None:
            return None
        return {"wti": wti, "brent": brent, "as_of": as_of}
    except Exception:
        return None


def _c6_posture() -> dict[str, dict]:
    """ticker -> latest v5 C6 risk-channel posture from persisted specialized-run
    artifacts (output/swarm/canada/*.json). Empty dict entries mean 'not yet run'
    — rendered as such, never as a score of zero."""
    out: dict[str, dict] = {}
    try:
        for f in sorted(C6_DIR.glob("*.json")):
            d = json.loads(f.read_text())
            tk = d.get("ticker")
            rc = d.get("risk_channel") or {}
            if tk and rc:
                out[tk] = {"level": rc.get("level"), "flag": rc.get("flag"),
                           "accession": d.get("accession_number"),
                           "drivers": (rc.get("drivers") or [])[:3]}
    except Exception:
        pass
    return out


def _price_coverage(tickers: list[str]) -> tuple[int, int]:
    """(names with >=50 close rows, total names) — measured from price_history."""
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM (SELECT ticker FROM price_history "
                "WHERE ticker = ANY(%s) GROUP BY ticker HAVING count(*) >= 50) t",
                (tickers,))
            n = cur.fetchone()[0]
    return int(n), len(tickers)


def _lens_section(lens: str, entry: dict, c6: dict[str, dict], oil: dict | None) -> str:
    p = entry["posture"]
    mat = entry["maturity"]
    color = LENS_COLOR[lens]
    tickers = sorted(p["holdings"])
    n_px, n_names = _price_coverage(tickers)
    n_insider = sum(1 for m in p["members"] if m["filer_class"] == "DOMESTIC")
    n_c6 = sum(1 for m in p["members"] if m["ticker"] in c6)

    # ---- coverage disclosure FIRST (before any dashboard visuals) ----
    cov_html = f"""
      <div style="background:#1A2030;border-radius:8px;padding:14px 18px;margin-bottom:14px;font-size:12px;color:#A0AEC0;line-height:1.65">
        <strong style="color:#E2E8F0">Measured coverage — {lens} ({escape(p['theme'])}).</strong>
        <ul style="margin:6px 0 0 18px">
          <li><strong style="color:{color}">Filings-evidence coverage: {p['sec_filer_weight_pct']:.0f}% of lens weight</strong>
              ({p['n_names_covered']} of {p['n_names_total']} names are current SEC filers) — measured in the
              Phase-1 feasibility study from {escape(p['holdings_source'])}, holdings as of {escape(p['holdings_as_of'])}.
              This is the single measured coverage figure for Phase 2; it covers SEC-filing evidence only and
              is not a total-evidence claim.</li>
          <li>Price-history coverage: {n_px}/{n_names} covered names have research price history
              (WCPRF is a limited OTC proxy line where present — flagged, not equivalent to primary US listings).</li>
          <li>Event-study eligible coverage: accrues with matured events — {mat['n_matured']} matured of
              {mat['n_events']} accepted events so far on this lens.</li>
          <li>Insider-data eligible coverage: {n_insider}/{n_names} covered names (US-domestic filers with a
              Form 4 stream). All other names: outside current evidence scope — SEDI substrate not currently ingested.</li>
        </ul>
        <div style="margin-top:8px"><strong style="color:#E2E8F0">Outside evidence scope:</strong> {escape(p['uncovered_scope'])}</div>
      </div>"""

    # ---- posture dashboard ----
    rows = []
    for m in p["members"]:
        ev_summary = ", ".join(f"{et}×{v['n']}" for et, v in
                               sorted(m["events"].items(), key=lambda kv: -kv[1]["n"])) or "—"
        filed = ", ".join(f"{st}×{n}" for st, n in sorted(m["filings_ingested"].items())) or "—"
        c6m = c6.get(m["ticker"])
        c6_cell = (f"{escape(str(c6m['level']))} / {escape(str(c6m['flag']))}" if c6m
                   else "<span style='color:#718096'>not yet run</span>")
        insider_cell = (m["insider_scope"] if m["filer_class"] == "DOMESTIC"
                        else "<span style='color:#718096'>outside evidence scope (SEDI)</span>")
        quality = ("<span style='color:#FBA94B'> · low-quality OTC proxy line</span>"
                   if m["listing_quality"] == "low" else "")
        rows.append(
            f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>"
            f"<a style='color:#E2E8F0;text-decoration:none' href='https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={escape(m['ticker'])}&type=6-K&dateb=&owner=include&count=10'>{escape(m['ticker'])}</a>{quality}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(m['sec_name'][:28])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{m['weight_pct']:.2f}%</td>"
            f"<td style='padding:7px 12px;color:#718096;font-size:11px'>{escape(m['filer_class'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-size:11px'>{escape(filed)}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-size:11px'>{escape(ev_summary)}</td>"
            f"<td style='padding:7px 12px;color:{color};font-size:11px'>{escape(m['grade'])}</td>"
            f"<td style='padding:7px 12px;font-size:11px'>{c6_cell}</td>"
            f"<td style='padding:7px 12px;font-size:11px'>{insider_cell}</td></tr>")

    # ---- CAR: panels only with matured events; honest placeholder otherwise ----
    if "event_study" in entry:
        es = entry["event_study"]
        pooled = es["pooled_directional"]
        chart = car_chart(pooled["peer"],
                          f"{lens} direction-aligned CAR (peer model, 95% CI)",
                          color=color, spy_curve=pooled["spy"])
        car_html = f"""
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:14px 0 8px">
        Direction-aligned pooled CAR · n={pooled['peer']['n_events']} events
        (dedup: {es['n_raw_filings']} filings → {es['n_events_deduped']} events → {es['n_events_used']} evaluable)</div>
      {chart}
      <p style="font-size:11px;color:#718096;margin-top:8px">Same event-study methodology as the Open Index
      Evidence page (peer + SPY models, [−5,+20] window, dedup, disclosed n). CIs assume independent events
      and are optimistic. {escape(es['insider_stream_note'])}</p>"""
    else:
        car_html = f"""
      <div style="background:#151A23;border:1px dashed #2D3748;border-radius:8px;padding:16px 18px;margin-top:14px;font-size:12px;color:#A0AEC0">
        <strong style="color:#E2E8F0">Event study accrues forward.</strong>
        Matured events so far: {mat['n_matured']} (accepted: {mat['n_events']}).
        CAR panels will render once the lens has at least {CANADA_CAR_MIN_EVENTS} events with
        sufficient post-event windows under the disclosed methodology. No fabricated history,
        no placeholder charts.</div>"""

    oil_html = ""
    if oil and lens in ("XEG", "ZEO"):
        wti = f"WTI {oil['wti']}" if oil.get("wti") is not None else ""
        brent = f"Brent {oil['brent']}" if oil.get("brent") is not None else ""
        oil_html = f"""
      <div style="margin-top:10px;padding:9px 14px;background:#10141C;border:1px solid #1E232D;border-radius:8px;font-size:11px;color:#718096">
        Research-side context (oil-intelligence engine, as of {escape(str(oil['as_of']))}): {escape(' · '.join(x for x in (wti, brent) if x))}.
        Context only — does not feed composite scoring and does not alter evidence grades.</div>"""

    return f"""
    <div class="panel">
      <div class="panel-title" style="color:{color}">{lens} · {escape(p['name'])}</div>
      <div class="panel-sub">{escape(p['theme'])} · evidence-tier research lens · constituent weights are issuer/fund disclosures used only for internal coverage statistics</div>
      {cov_html}
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px">
        <div class="tile"><div class="v">{p['n_covered_names']}</div><div class="k">covered SEC filers</div></div>
        <div class="tile"><div class="v">{p['filings_total']}</div><div class="k">filings ingested</div></div>
        <div class="tile"><div class="v">{p['events_total']}</div><div class="k">accepted evidence events</div></div>
        <div class="tile"><div class="v">{p['prose_total']}</div><div class="k">filings with exhibit/MD&A prose</div></div>
        <div class="tile"><div class="v">{n_c6}/{p['n_covered_names']}</div><div class="k">C6 posture runs</div></div>
      </div>
      <table>
        <thead><tr><th>Name</th><th>Issuer</th><th>Lens weight</th><th>Filer class</th><th>Filings ingested</th><th>Constituent events</th><th>Evidence grade</th><th>C6 posture</th><th>Insider substrate</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">Evidence grades describe coverage depth
      (filings, prose, events on file) — they are research classifications of evidence coverage, not
      rankings and not composite scores. Name links open the issuer's EDGAR filing browser (drill-down
      to primary-source filings).</p>
      {car_html}
      {oil_html}
    </div>"""


def render() -> str:
    data = compute_canada()
    c6 = _c6_posture()
    oil = _oil_context()
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections = "".join(_lens_section(lens, data["lenses"][lens], c6, oil)
                       for lens in CANADA_LENS_KEYS)

    total_names = len({t for lens in CANADA_LENS_KEYS
                       for t in data["lenses"][lens]["posture"]["holdings"]})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · Canada Resources Evidence</title>
  <meta name="description" content="Research evidence dashboard: SEC-filing evidence on Canada resources ETF constituents. Measured coverage, evidence-tier only — not investment advice.">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:'Inter',sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1080px;margin:0 auto;padding:24px}}
    .header{{margin-bottom:16px;padding:18px 24px;background:#151A23;border:1px solid #1E232D;border-radius:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
    .logo{{font-size:20px;font-weight:800;color:#FFF;letter-spacing:-0.3px;text-decoration:none}}
    a.logo:hover{{color:#00E676}}
    .ver{{display:inline-block;background:#00E67620;color:#00E676;border:1px solid #00E67680;padding:3px 9px;border-radius:5px;font-size:10px;font-weight:700;margin-left:8px;font-family:JetBrains Mono,monospace}}
    .navlinks a{{color:#A0AEC0;text-decoration:none;font-size:13px;padding:5px 11px;border-radius:6px;background:#1E232D;margin-left:6px}}
    .navlinks a:hover{{color:#00E676}}
    .fresh{{background:#0F1B14;border:1px solid #00E67640;border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:12px;color:#A0AEC0;font-family:JetBrains Mono,monospace}}
    .fresh strong{{color:#00E676}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:14px 18px;font-size:12px;line-height:1.55;color:#A0AEC0;margin-bottom:22px}}
    .disclaimer strong{{color:#FBA94B}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:14px;font-weight:700;color:#FFF;margin-bottom:4px}}
    .panel-sub{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}}
    table{{width:100%;border-collapse:collapse;margin-top:14px;display:block;overflow-x:auto}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:8px 12px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.6px;white-space:nowrap}}
    td{{font-size:13px;border-bottom:1px solid #1A2030;white-space:nowrap}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
    .footer a{{color:#00E676;text-decoration:none}}
    .tile{{min-width:120px}}
    .tile .v{{font-size:24px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div><a href="index.html" class="logo">YUCLAW</a> <span style="color:#A0AEC0;font-size:14px">· Canada Resources Evidence</span> <span class="ver">v5.0.0</span></div>
      <div class="navlinks">
        <a href="index.html">← Dashboard</a>
        <a href="etf_evidence.html">Open Index Evidence</a>
        <a href="validation_lab.html">Validation Lab</a>
        <a href="methodology/validation_lab.md">Methodology</a>
      </div>
    </div>

    <div class="fresh">
      <strong>Regenerated daily</strong> with the site refresh chain · last build {escape(built)}
    </div>

    <div class="disclaimer">
      <strong>Research-only. Evidence dashboard. Not investment advice.</strong>
      This page shows the <strong>evidence posture</strong> of SEC-filing constituents of four published
      Canada-resources index funds — filings evidence, event records, classifications, grades, and C6
      posture. Coverage is measured and scoped below, <em>before</em> any dashboard content. Missing data
      is excluded, not imputed. Forward event studies accrue only when events mature.
    </div>

    <div class="panel">
      <div class="panel-title">Evidence-tier disclosure &amp; scope boundary</div>
      <div class="panel-sub">what this page is, and what it deliberately is not</div>
      <p style="font-size:13px;color:#A0AEC0;line-height:1.7;max-width:860px">
        The {total_names} names below form an <strong style="color:#E2E8F0">evidence-only coverage tier</strong>
        (metadata: <code>evidence_eligible=true</code>, <code>scoring_eligible=false</code>,
        <code>lab_universe=false</code>, <code>coverage_vertical=canada_resources</code>).
        They are ingested, parsed, classified, and displayed here — they are
        <strong style="color:#E2E8F0">never scored</strong>: no composite scores, no
        <code>signal_snapshots</code> rows, no Lab decile membership, no ranking panels, and no place in
        the 79-ticker forward-track record. Adding these names to the scoring universe mid-record would
        have been a methodology event; this vertical stands on filings evidence instead. Research lenses:
        <strong>XEG</strong>, <strong>ZEO</strong> (oil &amp; gas), <strong>GDX</strong> (gold),
        <strong>URNM</strong> (uranium). <strong>EWC</strong> is reference-only (broad-Canada context, not an
        evidence lens). <strong>GDXJ</strong> is excluded — 52% measured SEC-filer coverage with a 68-name
        silent tail is below the honesty bar for this methodology.
      </p>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.7;max-width:860px;margin-top:10px">
        <strong style="color:#E2E8F0">Insider disclosure.</strong> Most Canadian MJDS issuers file insider
        transactions on <strong>SEDI in Canada, not Form 4 on EDGAR</strong> (the FPI Section 16 exemption
        applies even to domestic-form foreign filers). Insider-derived metrics are therefore
        <strong>excluded</strong> for those issuers rather than rendered as zero — zero would imply observed
        absence; exclusion means outside current evidence scope. A live Form 4 substrate exists only for the
        US-domestic filers in these lenses (e.g. NEM, CDE, HL, RGLD, SSRM, UEC, UUUU, URG).
      </p>
      <p style="font-size:12px;color:#718096;line-height:1.7;max-width:860px;margin-top:10px">
        Constituent lists and weights are dated issuer/fund disclosures used only to derive the coverage
        statistics shown; no licensed index data is redistributed, and none of it is presented as YUCLAW's own.
        Filings evidence: 6-K / 40-F (MJDS), 8-K / 10-K / 10-Q (US-domestic), classified by the same
        SourceLock-guarded pipeline as the rest of the site, with exhibit-level prose extraction for 6-K/40-F
        envelope filings.
      </p>
    </div>

    {sections}

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW Canada Resources Evidence · built {escape(built)} ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only ·
      Phase-1 study: <a href="research/canada_resources/phase1_feasibility.md">feasibility &amp; coverage</a>
    </div>
  </div>
</body>
</html>
"""


def main() -> int:
    html = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"[render_canada_resources] wrote {OUT} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
