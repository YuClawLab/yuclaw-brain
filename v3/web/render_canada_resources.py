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
from v3.universe_tiers import evidence_cik_map
from v3.web.render_etf_evidence import car_chart
from v3.web.useful_blocks import (freshness_strip, build_footer, site_header_html,
                                  packet_block_from_manifest as _packet_block,
                                  status_block_html as _shared_status_block,
                                  use_in_research_html as _use_in_research)
from v3.web import oie_v51_blocks as _v51

OUT = _REPO / "docs" / "canada_resources.html"
OIL_DIR = _REPO / "output" / "oil"
C6_DIR = _REPO / "output" / "swarm" / "canada"

# D-grade names manually verified against EDGAR submissions (all form types,
# coverage window since 2026-01-01). A listed name genuinely filed nothing in
# the window — display distinguishes quiet-filer from not-yet-ingested. The
# grade taxonomy (letter) is unchanged; only the parenthetical differs.
VERIFIED_QUIET = {"WCPRF": "2026-07-16"}

# Names beyond this count collapse behind a CSS-only expander (top names by
# lens weight stay visible; every name remains one tap away — nothing is
# permanently hidden).
TABLE_COLLAPSE_VISIBLE = 10
TABLE_COLLAPSE_THRESHOLD = 12

# Plain-language reference lines for the event-type vocabulary as it appears
# in the constituent tables. Descriptions of the classification labels only —
# they do not alter the classifications themselves.
EVENT_TYPE_LEGEND = {
    "OTHER_MATERIAL": "a development disclosed in a filing that does not fit a more specific category below",
    "DIVIDEND_CHANGE": "a dividend declaration, increase, decrease, or suspension",
    "EARNINGS_BEAT": "reported results above the comparison stated in the filing",
    "EARNINGS_MISS": "reported results below the comparison stated in the filing",
    "EARNINGS_RESULT": "an earnings release without a stated beat or miss direction",
    "GUIDANCE_RAISE": "management raised a stated forward target or outlook",
    "GUIDANCE_CUT": "management lowered a stated forward target or outlook",
    "BUYBACK_ANNOUNCE": "a share repurchase program announced or renewed",
    "REGULATORY_ACTION": "a regulator decision, permit, or proceeding disclosed in the filing",
    "EXEC_CHANGE": "a change in a named executive or board role",
    "CAPACITY_CHANGE": "a production or capacity change stated in the filing",
    "M_AND_A_ANNOUNCE": "an acquisition, merger, or disposition announced",
    "M_AND_A_CLOSE": "a previously announced transaction completed",
    "CONTRACT_WIN": "a contract or offtake agreement disclosed in the filing",
}

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
    # Real Form-4 substrate only (excludes Section-16-exempt DOMESTIC FPIs like
    # ENB/IMO) — insider_scope is set from CANADA_FORM4_TICKERS in etf_evidence.
    n_insider = sum(1 for m in p["members"] if m["insider_scope"].startswith("Form 4 stream"))
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
          <li>Form 4 coverage: {n_insider}/{n_names} covered names (US-domestic filers with a
              Form 4 stream). All other names: outside current evidence scope — SEDI substrate not currently ingested.</li>
        </ul>
        <div style="margin-top:8px"><strong style="color:#E2E8F0">Outside evidence scope:</strong> {escape(p['uncovered_scope'])}</div>
      </div>"""

    # ---- posture dashboard ----
    ciks = evidence_cik_map()
    rows = []
    for m in p["members"]:
        ev_summary = ", ".join(f"{et}×{v['n']}" for et, v in
                               sorted(m["events"].items(), key=lambda kv: -kv[1]["n"])) or "—"
        # Bare numeric SEC form names ("4", "3", "144") read ambiguously in
        # "<form>×<count>" cells — prefix with "Form" (same fix as the digest).
        filed = ", ".join(
            f"{'Form ' + st if st.split('/')[0].isdigit() else st}×{n}"
            for st, n in sorted(m["filings_ingested"].items())) or "—"
        c6m = c6.get(m["ticker"])
        c6_cell = (f"{escape(str(c6m['level']))} / {escape(str(c6m['flag']))}" if c6m
                   else "<span class='dim'>not yet run</span>")
        insider_cell = (m["insider_scope"] if m["filer_class"] == "DOMESTIC"
                        else "<span class='dim'>outside evidence scope (SEDI)</span>")
        quality = ("<span style='color:#FBA94B'> · low-quality OTC proxy line</span>"
                   if m["listing_quality"] == "low" else "")
        # EDGAR drill-down: CIK-keyed filing browser (resolves for every name,
        # OTC proxy lines included); company-name search kept only as fallback.
        cik = ciks.get(m["ticker"])
        href = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
                f"&type=&dateb=&owner=include&count=40" if cik else
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company="
                f"{escape(m['ticker'])}&type=6-K&dateb=&owner=include&count=10")
        # Display-layer only: a D-grade name verified quiet on EDGAR reads as
        # such, so quiet-filer is distinguished from not-yet-ingested. Letter
        # taxonomy is untouched.
        grade = m["grade"]
        if m["ticker"] in VERIFIED_QUIET and grade.startswith("D ("):
            grade = (f"D (no EDGAR filings in coverage window; "
                     f"verified {VERIFIED_QUIET[m['ticker']]})")
        rows.append(
            f"<tr><td class='c-tk'>"
            f"<a class='tk' href='{href}'>{escape(m['ticker'])}</a>{quality}</td>"
            f"<td class='c-is' title='{escape(m['sec_name'])}'>"
            f"{escape(m['sec_name'] if len(m['sec_name']) <= 28 else m['sec_name'][:27] + '…')}</td>"
            f"<td class='c-wt'>{m['weight_pct']:.2f}%</td>"
            f"<td class='c-sm'>{escape(m['filer_class'])}</td>"
            f"<td class='c-sm'>{escape(filed)}</td>"
            f"<td class='c-sm'>{escape(ev_summary)}</td>"
            f"<td class='c-gr' style='color:{color}'>{escape(grade)}</td>"
            f"<td class='c-cx'>{c6_cell}</td>"
            f"<td class='c-cx'>{insider_cell}</td></tr>")

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

    ecs_note = ("<p style='font-size:11px;color:#718096;margin-top:6px'>"
                "Evidence coverage column: not computed for this tier — the "
                "registered Evidence Coverage v1 computation covers the "
                "79-name scoring universe only (coverage, not prediction).</p>")
    thead = ("<thead><tr><th>Name</th><th>Issuer</th><th>Lens weight</th>"
             "<th>Filer class</th><th>Filings ingested</th><th>Constituent events</th>"
             "<th>Evidence grade</th><th>C6 posture</th><th>Insider substrate</th></tr></thead>")
    if len(rows) > TABLE_COLLAPSE_THRESHOLD:
        # CSS-only expander: top names by lens weight stay visible; the rest
        # are one tap away. Nothing is permanently hidden.
        n_hidden = len(rows) - TABLE_COLLAPSE_VISIBLE
        table_html = f"""
      <div class="tblwrap"><table>
        {thead}
        <tbody>{''.join(rows[:TABLE_COLLAPSE_VISIBLE])}</tbody>
      </table></div>
      <details class="expander">
        <summary>Show all {len(rows)} covered names ({n_hidden} more, sorted by lens weight)</summary>
        <div class="tblwrap"><table>
          {thead}
          <tbody>{''.join(rows[TABLE_COLLAPSE_VISIBLE:])}</tbody>
        </table></div>
      </details>{ecs_note}"""
    else:
        table_html = f"""
      <div class="tblwrap"><table>
        {thead}
        <tbody>{''.join(rows)}</tbody>
      </table></div>{ecs_note}"""

    # Lens summary card (usefulness build 2026-07-16) — one short paragraph,
    # every number pulled from the SAME `p`/`mat` data this section renders
    # below, never hand-typed. Sits ABOVE the coverage disclosure, which stays
    # byte-untouched.
    # First clause of uncovered_scope: split on "; " and on SENTENCE periods
    # (". " / trailing ".") only — a bare "." split truncates decimals like
    # "Tourmaline (5.6%)" at the decimal point (the 2026-07-22 clipped-copy bug).
    major_scope = p["uncovered_scope"].split("; ")[0].split(". ")[0].strip().rstrip(".")
    summary_card = f"""
      <p style="background:#10141C;border:1px solid #1E232D;border-left:3px solid {color};
                border-radius:8px;padding:11px 15px;margin-bottom:12px;font-size:12.5px;
                color:#A0AEC0;line-height:1.65">
        <strong style="color:{color}">{lens} in one paragraph.</strong>
        Filings-evidence coverage is <strong style="color:#E2E8F0">{p['sec_filer_weight_pct']:.0f}% of lens
        weight</strong> across <strong style="color:#E2E8F0">{p['n_names_covered']} SEC filers</strong>
        ({p['n_names_total']} names total). On file: <strong style="color:#E2E8F0">{p['filings_total']}
        filings ingested</strong>, <strong style="color:#E2E8F0">{p['events_total']} accepted evidence
        events</strong>, of which <strong style="color:#E2E8F0">{mat['n_matured']} have matured</strong> into
        the event study. Form 4 coverage:
        <strong style="color:#E2E8F0">{n_insider}/{p['n_covered_names']}</strong> — most covered
        Canadian issuers report insider trades through Canada's SEDI system, which is not yet
        ingested. Major outside-scope block: {escape(major_scope)}.
      </p>"""

    return f"""
    <div class="panel" id="lens-{lens}">
      <div class="panel-title" style="color:{color}">{lens} · {escape(p['name'])}</div>
      <div class="panel-sub">{escape(p['theme'])} · evidence-tier research lens · constituent weights are issuer/fund disclosures used only for internal coverage statistics
        · <a href="todays_evidence.html" style="color:{color};text-transform:none;letter-spacing:0">What changed today →</a></div>
      {summary_card}
      {cov_html}
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px">
        <div class="tile"><div class="v">{p['n_covered_names']}</div><div class="k">covered SEC filers</div></div>
        <div class="tile"><div class="v">{p['filings_total']}</div><div class="k">filings ingested</div></div>
        <div class="tile"><div class="v">{p['events_total']}</div><div class="k">accepted evidence events</div></div>
        <div class="tile"><div class="v">{p['prose_total']}</div><div class="k">filings with exhibit/MD&A prose</div></div>
        <div class="tile"><div class="v">{n_c6}/{p['n_covered_names']}</div><div class="k">Issuers with current C6 analysis</div></div>
      </div>
      {table_html}
      <p style="font-size:11px;color:#718096;margin-top:8px">Evidence grades describe coverage depth
      (filings, prose, events on file) — they are research classifications of evidence coverage, not
      rankings and not composite scores. Name links open the issuer's EDGAR filing browser (drill-down
      to primary-source filings).</p>
      <p style="font-size:11px;margin-top:6px"><a class="ref" href="#event-legend">Reading the event types ↑</a>
      · <a class="ref" href="#top">Back to top ↑</a></p>
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

    # §24 intro block numbers — all queried, none typed.
    from v3.universe_tiers import evidence_tier_tickers, scoring_universe
    n_evidence = len(evidence_tier_tickers())
    n_scoring = len(scoring_universe())
    covs = [data["lenses"][lens]["posture"]["sec_filer_weight_pct"]
            for lens in CANADA_LENS_KEYS]
    min_coverage, max_coverage = min(covs), max(covs)

    # Sticky lens navigation (display chrome only).
    lensnav = "".join(
        f'<a href="#lens-{lens}" style="color:{LENS_COLOR[lens]}">{lens}</a>'
        for lens in CANADA_LENS_KEYS)

    # Event-type reference built from the types actually present in the
    # tables (plain-language description per classification label).
    types_present = sorted({et for lens in CANADA_LENS_KEYS
                            for m in data["lenses"][lens]["posture"]["members"]
                            for et in m["events"]})
    legend_items = "".join(
        f"<li><code>{escape(et)}</code> — "
        f"{escape(EVENT_TYPE_LEGEND.get(et, et.replace('_', ' ').lower()))}</li>"
        for et in types_present)

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
    .tblwrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-top:14px}}
    table{{width:100%;border-collapse:collapse}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:8px 12px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.6px;white-space:nowrap}}
    td{{font-size:13px;border-bottom:1px solid #1A2030;white-space:nowrap;padding:7px 12px}}
    td.c-tk{{color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700}}
    a.tk{{color:#E2E8F0;text-decoration:none}}
    a.tk:hover{{color:#00E676}}
    td.c-is{{color:#A0AEC0;font-size:11px}}
    td.c-wt{{color:#A0AEC0;font-family:JetBrains Mono,monospace}}
    td.c-sm{{color:#718096;font-size:11px}}
    td.c-gr,td.c-cx{{font-size:11px}}
    .dim{{color:#718096}}
    a.ref{{color:#4DD0E1;text-decoration:none}}
    svg{{max-width:100%;height:auto}}
    .lensnav{{position:sticky;top:0;z-index:20;display:flex;gap:8px;align-items:center;background:#0B0E14F2;padding:8px 0;margin-bottom:12px;overflow-x:auto;white-space:nowrap}}
    .lensnav a{{text-decoration:none;font-size:12px;font-weight:700;font-family:JetBrains Mono,monospace;padding:4px 12px;border-radius:6px;background:#1E232D;border:1px solid #2D3748}}
    .lensnav .lbl{{font-size:10px;text-transform:uppercase;letter-spacing:0.6px;color:#718096}}
    details.infobox{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:14px 18px;margin-bottom:14px;font-size:12px;color:#A0AEC0;line-height:1.7}}
    details.infobox summary{{cursor:pointer;color:#E2E8F0;font-size:13px;font-weight:600}}
    details.infobox ul{{margin:8px 0 0 18px}}
    details.infobox li{{margin-bottom:4px}}
    details.expander summary{{cursor:pointer;color:#4DD0E1;font-size:12px;padding:8px 2px}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
    .footer a{{color:#00E676;text-decoration:none}}
    .tile{{min-width:120px}}
    .tile .v{{font-size:24px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
    @media (max-width:640px){{
      .container{{padding:12px}}
      .header{{padding:14px 16px}}
      .panel{{padding:16px 14px}}
      td{{font-size:12px}}
      .tile{{min-width:96px}}
      .tile .v{{font-size:20px}}
      .navlinks a{{margin-left:0;margin-right:6px;display:inline-block;margin-bottom:6px}}
    }}
  </style>
</head>
<body>
  <div class="container" id="top">
    {site_header_html(subtitle="Canada Resources Evidence", active="canada_resources.html")}

    <div class="lensnav"><span class="lbl">Jump to lens</span>{lensnav}</div>

    <div class="fresh">
      <strong>Regenerated daily</strong> with the site refresh chain · last build {escape(built)}
    </div>

    <div class="disclaimer">
      <strong>Canada Resources Evidence</strong> — A source-traceable research view of four Canadian
      resource lenses: XEG, ZEO, GDX and URNM. YUCLAW tracks filings, extracts material evidence,
      classifies events, measures coverage and follows event outcomes as their forward windows mature.
      Every accepted event links to a primary filing and can be reproduced from the published evidence
      bundle. These {n_evidence} issuers belong to an evidence-only research tier. They are not included
      in YUCLAW's {n_scoring}-ticker scoring universe, are not ranked and do not affect the existing
      forward record. Current research status: filing-weight coverage ranges from {min_coverage:.0f}%
      to {max_coverage:.0f}%; peer-adjusted event results do not yet establish a reliable return
      advantage; Form 4 evidence covers only eligible US domestic issuers; C6 sign confirmation is
      accruing — direction is not yet established; all statistics, source links and evidence-ledger roots are
      available for replay.
      <br><strong>Research-only. Evidence dashboard. Not investment advice.</strong>
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

    <details class="infobox" id="reading-this-page">
      <summary>Reading this page — filing types and terms</summary>
      <ul>
        <li><strong style="color:#E2E8F0">MJDS</strong> — the US–Canada Multijurisdictional Disclosure
            System. Eligible Canadian issuers meet SEC reporting obligations with documents prepared
            under Canadian rules.</li>
        <li><strong style="color:#E2E8F0">6-K</strong> — the form a foreign private issuer uses to
            furnish material information to the SEC between annual reports. Its nearest US-domestic
            counterpart is the 8-K.</li>
        <li><strong style="color:#E2E8F0">40-F</strong> — the annual report form for MJDS filers. Its
            US-domestic counterpart is the 10-K.</li>
        <li><strong style="color:#E2E8F0">8-K / 10-K / 10-Q</strong> — current-event, annual, and
            quarterly report forms filed by US-domestic issuers.</li>
        <li><strong style="color:#E2E8F0">SEDI</strong> — Canada's System for Electronic Disclosure by
            Insiders. MJDS issuers report insider transactions on SEDI, not on EDGAR Form 4, so insider
            metrics for those names are outside this page's evidence scope and are marked excluded
            rather than zero.</li>
        <li><strong style="color:#E2E8F0">Evidence grades</strong> — describe how much filing evidence
            is on file for a name (filings ingested, exhibit/MD&amp;A prose, accepted events). They are
            coverage classifications, not rankings, scores, or recommendations.</li>
      </ul>
    </details>

    <details class="infobox" id="event-legend">
      <summary>Reading the event types</summary>
      <ul>{legend_items}</ul>
    </details>

    {sections}

    {_v51.falsification_panel("XEG", pid="falsification-xeg")}
    {_v51.falsification_panel("ZEO", pid="falsification-zeo")}
    {_v51.falsification_panel("GDX", pid="falsification-gdx")}
    {_v51.falsification_panel("URNM", pid="falsification-urnm")}
    {_v51.taxonomy_panel("GDX", pid="taxonomy-gdx")}

    {_packet_block("canada")}

    {_use_in_research("packets/yuclaw_canada_resources_packet.zip")}

    {_shared_status_block()}

    <div class="disclaimer">
      <strong>Disclaimer —</strong> {escape(DISCLAIMER_FULL)}
    </div>

    <div class="footer">
      YUCLAW Canada Resources Evidence ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only ·
      Phase-1 study: <a href="research/canada_resources/phase1_feasibility.md">feasibility &amp; coverage</a> ·
      example: <a href="examples/evidence_memo_su.md">evidence memo (Suncor)</a>
    </div>
  </div>
{build_footer()}
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
