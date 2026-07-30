#!/usr/bin/env python3
"""
OIE v5.1 extended SMH preview (ORDER v5.1 Parts B/C/D render step).

Re-renders docs/preview/smh_lens.html = the ORDER-2 page (recomputed from the
same registered protocols; NO new registry entries — statistics unchanged from
the recorded runs, whose line hashes are cited) PLUS:

  - Falsification battery panel (Part B; reads output/oie/falsification_run.json)
  - Form-4 transaction taxonomy panel (Part C; reads output/oie/form4_taxonomy.json,
    renders a 'pending' stub if the fetch has not completed)
  - Live maturity funnel (Part D / review §16)
  - Holdings intelligence block (Part D / review §20)
  - Cross-ETF issuer map + sector-ETF data-gap statement (Part D)

Display-only composition: every inferential number on this page comes from a
registered protocol's recorded run.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Registry
from yuclaw_smh_lens_run import (PROTOCOL_NAME, PROTOCOL_PARAMS, METHOD_SPEC,
                                 breadth_states, facts_and_admission,
                                 render_preview, run_estimands)
from yuclaw_protocol_registry import protocol_id as _pid

from v3.lab.cohort_engine import DSN, FORWARD_DAY0, load_prices
from v3.lab.etf_evidence import (CAR_PRE, CAR_POST, EST_GAP, EST_MIN, EST_WIN,
                                 SMH_AS_OF, SMH_HOLDINGS, canada_lens_holdings,
                                 event_study, overlap_summary)
from v3.lab.stats import ols

HOLDINGS_RETRIEVED = "2026-07-05"   # commit dce9cf6f introduced the snapshot
REQUIRED = {"events": 10, "issuers": 8, "dates": 10}  # 5bff6b28 badge floors


def _panel(title, sub, body):
    return (f'<div class="panel"><div class="panel-title">{title}</div>'
            f'<div class="panel-sub">{sub}</div>{body}</div>')


# ---------------------------------------------------------------- Part B
def falsification_html() -> str:
    p = _REPO / "output" / "oie" / "falsification_run.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    panel = data["panels"]["SMH-E4"]
    ds, sf, pl = (panel["date_shuffle"], panel["sign_flip"],
                  panel["placebo_minus20d"])
    body = f"""
      <table>
        <thead><tr><th>Test</th><th>Real value</th><th>Null mean ± sd</th><th>Null 2.5–97.5%</th><th>Percentile of real in null</th></tr></thead>
        <tbody>
        <tr><td style='padding:7px 12px;color:#E2E8F0'>Event-date shuffle (PRIMARY)</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{panel['real_pct']:+.2f}%</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{ds['null']['mean']:+.2f}% ± {ds['null']['sd']:.2f}</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#718096'>({ds['null']['p2_5']:+.2f}, {ds['null']['p97_5']:+.2f})</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{ds['percentile_in_null']:.3f}</td></tr>
        <tr><td style='padding:7px 12px;color:#E2E8F0'>Direction sign-flip</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{panel['real_pct']:+.2f}%</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{sf['null']['mean']:+.2f}% ± {sf['null']['sd']:.2f}</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#718096'>({sf['null']['p2_5']:+.2f}, {sf['null']['p97_5']:+.2f})</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{sf['percentile_in_null']:.3f}</td></tr>
        <tr><td style='padding:7px 12px;color:#E2E8F0'>Pre-event placebo (−20d)</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{pl['value_pct']:+.2f}%</td>
        <td style='padding:7px 12px;color:#718096;font-size:11px' colspan='2'>located in the date-shuffle null · {pl['dropped']} of {panel['n_events']} events dropped (shifted day0 pre-dates usable estimation history — disclosed)</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{pl['percentile_in_shuffle_null']:.3f}</td></tr>
        </tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
        <strong style="color:#E2E8F0">Reading:</strong> the real E4 value sits at the
        {ds['percentile_in_null']:.0%} point of its own event-date-shuffle null — unremarkable. The null's
        mean is itself deeply negative ({ds['null']['mean']:+.2f}%): under this era's melt-up, sell-direction
        alignment is negative on <em>randomly chosen</em> days for these issuers, so the adverse headline
        appears to be era-generic direction alignment rather than event-timing information. The placebo
        window (+{pl['value_pct']:.2f}% at −20d) is consistent with that reading. Extremity is read
        two-sided: percentiles near 0 and near 100 are both extreme. Exploratory; every cell
        ledger-counted under Falsification Battery v1.
      </p>"""
    return _panel("Falsification battery · SMH E4 estimand",
                  f"protocol {escape(data['protocol_id'])} · N={data['n_null']} per null · "
                  f"seed {data['seed']} · registered before computation", body)


# ---------------------------------------------------------------- Part C
def taxonomy_html() -> str:
    p = _REPO / "output" / "oie" / "form4_taxonomy.json"
    if not p.exists():
        return _panel("Form-4 transaction taxonomy",
                      "deterministic XML parse — build pending",
                      "<p style='font-size:12px;color:#718096'>Taxonomy build "
                      "pending on this box; panel renders on next build.</p>")
    data = json.loads(p.read_text())
    roll = data["lenses"]["SMH"]
    c, v = roll["tx_counts"], roll["value_usd"]
    total = sum(c.values()) or 1
    label = {"S_discretionary": "S · discretionary open-market sale",
             "S_plan_10b5_1": "S · Rule 10b5-1 plan sale",
             "F_tax_withholding": "F · tax-withholding disposition (mechanical)",
             "M_exercise": "M · option exercise / conversion (mechanical)",
             "A_award": "A · award / grant (mechanical)",
             "D_to_issuer": "D · disposition to issuer",
             "P_purchase": "P · open-market purchase", "other": "other codes"}
    rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{label[k]}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c[k]}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c[k]/total*100:.1f}%</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{('$' + format(v[k], ',')) if k in v else '—'}</td></tr>"
        for k in data["classes"] if c[k])
    t3 = []
    for tk in roll["top3_by_events"]:
        m = roll["members"][tk]
        mc = m["tx_counts"]
        t3.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{tk}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{m['ingested_events']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{m['ingested_events_plan_10b5_1']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['S_discretionary']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['S_plan_10b5_1']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['F_tax_withholding']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['M_exercise'] + mc['A_award']}</td></tr>")
    sd, sp = c["S_discretionary"], c["S_plan_10b5_1"]
    mech = c["F_tax_withholding"] + c["M_exercise"] + c["A_award"]
    vd, vp = v["S_discretionary"], v["S_plan_10b5_1"]
    body = f"""
      <table>
        <thead><tr><th>Code class</th><th>Transactions</th><th>Share</th><th>$ mass (non-deriv rows)</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="font-size:11px;color:#718096;margin:14px 0 4px;text-transform:uppercase;letter-spacing:1px">Top-3 covered issuers by ingested events</div>
      <table>
        <thead><tr><th>Ticker</th><th>Ingested events</th><th>… plan-flagged</th><th>S discretionary</th><th>S 10b5-1</th><th>F withholding</th><th>M+A mechanical</th></tr></thead>
        <tbody>{''.join(t3)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
        <strong style="color:#E2E8F0">The sharpest OIE question, first cut:</strong> of the covered sleeve's
        S-coded sale transactions, {sd} are discretionary open-market and {sp} carry the filing-level
        Rule 10b5-1 checkbox; {mech} further transactions are mechanical (F withholding, M exercise,
        A grants). By dollar mass, discretionary S = ${vd:,} vs plan S = ${vp:,}. Zero LLM involvement,
        zero scoring-path contact — C6 inputs untouched.
      </p>"""
    return _panel("Form-4 transaction taxonomy · covered sleeve",
                  f"deterministic XML parse of {data['n_filings']} ingested filings "
                  f"({data['n_parse_errors']} fetch/parse failures disclosed) · display-only · "
                  f"built {escape(data['built_utc'])}", body)


# ------------------------------------------------- sale-type decomposition
def sale_type_html() -> str:
    p = _REPO / "output" / "oie" / "sale_type_split.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    bf, ae = data["results"]["backfill"], data["results"]["all_era"]

    def cls_row(name, c, n):
        if not c:
            return (f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{name}</td>"
                    f"<td style='padding:7px 12px;color:#718096' colspan='5'>n={n} — not computable</td></tr>")
        sh = c["shuffle"]
        return (f"<tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{name}</td>"
                f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{n}</td>"
                f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{c['mean_pct']:+.2f}%</td>"
                f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B;font-size:11px'>({c['envelope'][0]:+.2f}, {c['envelope'][1]:+.2f})</td>"
                f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(c['badge'])}</td>"
                f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{sh['percentile_in_null']:.3f} <span style='color:#718096;font-weight:400'>(null {sh['null']['mean']:+.2f}±{sh['null']['sd']:.2f})</span></td></tr>")

    d = bf.get("difference", {})
    diff_row = ""
    if d:
        diff_row = (f"<tr style='background:#1A2334'><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>discretionary − plan</td>"
                    f"<td style='padding:7px 12px;color:#718096'>—</td>"
                    f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{d['value']:+.2f}pp</td>"
                    f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B;font-size:11px'>({d['envelope'][0]:+.2f}, {d['envelope'][1]:+.2f})</td>"
                    f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>envelope includes 0</td><td></td></tr>")
    fm = data["fm_mechanical"]
    body = f"""
      <table>
        <thead><tr><th>Class (backfill era)</th><th>n event-days</th><th>E4 CAR +20d</th><th>Envelope</th><th>Badge</th><th>Date-shuffle percentile</th></tr></thead>
        <tbody>
          {cls_row("S · discretionary", bf["discretionary"], bf["n_discretionary"])}
          {cls_row("S · Rule 10b5-1 plan", bf["plan"], bf["n_plan"])}
          {diff_row}
        </tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
        <strong style="color:#E2E8F0">The decisive cell:</strong> the discretionary class sits at the
        {bf['discretionary']['shuffle']['percentile_in_null']:.0%} point of its own date-shuffle null —
        no evidence that discretionary selling carries timing information that plan selling lacks, at this
        sample. Point estimates even run the other way (plan more adverse than discretionary in the backfill
        era), with every interval UNDERPOWERED and the difference envelope spanning zero — thin-but-honest.
        All-era sensitivity: discretionary {ae['discretionary']['mean_pct']:+.2f}% (shuffle
        {ae['discretionary']['shuffle']['percentile_in_null']:.3f}), plan {ae['plan']['mean_pct']:+.2f}%
        (shuffle {ae['plan']['shuffle']['percentile_in_null']:.3f}).
        F/M-mechanical class: {fm['n']} events — {escape(fm['reason'])}.
        Class = S-mass dollar majority per event day (filing-level 10b5-1 checkbox); unclassified days:
        {data['unclassified_event_days_total']}.
      </p>"""
    return _panel("Sale-type decomposition · discretionary vs plan (registered)",
                  f"protocol {escape(data['protocol_id'])} · registered before computation · "
                  "two-sided extremity, exploratory beyond the primary", body)


# ------------------------------------------------- momentum conditioning
def momentum_html() -> str:
    p = _REPO / "output" / "oie" / "momentum_conditioning.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    r = data["results"]["SMH-E4"]
    rows = []
    for wk, lbl in (("W60", "prior 60d (PRIMARY diff)"), ("W20", "prior 20d")):
        c = r[wk]
        if "difference" not in c:
            continue
        d = c["difference"]
        hl = " style='background:#1A2334'" if wk == "W60" else ""
        rows.append(
            f"<tr{hl}><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{lbl}</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c['median_rel_momentum_pct']:+.1f}%</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{c['outperformed']['value_pct']:+.2f}% (n={c['outperformed']['n']})</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c['underperformed']['value_pct']:+.2f}% (n={c['underperformed']['n']})</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{d['value']:+.2f}pp</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B;font-size:11px'>({d['envelope'][0]:+.2f}, {d['envelope'][1]:+.2f})</td></tr>")
    lens_bits = []
    for lens in ("XEG", "ZEO", "GDX", "URNM"):
        c = data["results"][lens]["W60"]
        if "difference" in c:
            d = c["difference"]
            ex = d["envelope"][1] < 0 or d["envelope"][0] > 0
            lens_bits.append(f"{lens} {d['value']:+.1f}pp "
                             f"({'excludes' if ex else 'includes'} 0)")
    body = f"""
      <table>
        <thead><tr><th>Window</th><th>Median rel-momentum</th><th>Outperformed half · E4</th><th>Underperformed half · E4</th><th>Difference</th><th>Envelope</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
        <strong style="color:#E2E8F0">Reading:</strong> the registered primary (W=60 difference) is
        inconclusive — the envelope spans zero. The secondary cross-lens picture is more coherent: at W=60
        the outperformed-minus-underperformed difference is negative in every lens
        ({escape(' · '.join(lens_bits))}), i.e. prior-60-day winners systematically deliver more adverse
        aligned CARs than prior losers across unrelated sectors — consistent with a market-wide 60-day
        reversal structure, not event-specific information. The pattern vanishes at W=20. Secondary cells
        are exploratory and ledger-counted; extremity is read two-sided.
      </p>"""
    return _panel("Pre-event momentum conditioning (registered)",
                  f"protocol {escape(data['protocol_id'])} · median split by prior issuer-vs-peer "
                  "relative momentum · registered before computation", body)


_IMPLICATION = ("Investment implication: none established — no buy, sell, or "
                "alpha conclusion is supported by this page.")


# ------------------------------------------------- Fields-review panels
def geometry_html() -> str:
    p = _REPO / "output" / "oie" / "evidence_geometry.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    g = data["results"]["SMH"]
    t5 = "".join(
        f"<tr><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{s['size']}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{s['mass_pct']}%</td>"
        f"<td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{escape(s['dominant_issuer'])}</td>"
        f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(s['dominant_type'])}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{s['span_trading_days']}d</td></tr>"
        for s in g["top5_stories"])
    body = f"""
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v">{g['n_raw_filings']}</div><div class="k">filings</div></div>
        <div class="tile"><div class="v">{g['n_events']}</div><div class="k">deduped events</div></div>
        <div class="tile"><div class="v">{g['n_stories']}</div><div class="k">stories (linked clusters)</div></div>
        <div class="tile"><div class="v">{g['n_eff_story']}</div><div class="k">effective evidence count</div></div>
      </div>
      <table>
        <thead><tr><th>Story size</th><th>Event mass</th><th>Dominant issuer</th><th>Dominant type</th><th>Span</th></tr></thead>
        <tbody>{t5}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Many events, fewer stories — statistics on this page use cluster-aware inference accordingly.
        Linkage rule (pre-committed): same issuer within 5 trading days, or same type and lens within 3.
        Story-level design effect {g['deff_story']} (issuer-level effective count {g['n_eff_issuer']});
        with only {g['n_stories']} stories the story-level variance read is itself thin — both structure
        and variance are shown rather than choosing one. Top story carries {g['top_story_share_pct']}% of
        event mass. {escape(_IMPLICATION)}
      </p>"""
    return _panel("Evidence structure",
                  f"protocol {escape(data['protocol_id'])} · registered before computation · seed 20260730", body)


def robustness_html() -> str:
    p = _REPO / "output" / "oie" / "robustness_profile.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    cells, summ = data["smh"]["cells"], data["smh"]["summary"]
    rows = []
    for k, v in cells.items():
        if v is None:
            rows.append(f"<tr><td style='padding:6px 12px;color:#718096;font-size:12px'>{escape(k)}</td>"
                        f"<td colspan='4' style='padding:6px 12px;color:#718096;font-size:11px'>empty — SPY history begins 2026-02-02, so a trailing-120-trading-day window is not computable at these event dates (own-data rule; cell reported, not estimated)</td></tr>")
            continue
        rows.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{escape(k)}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{v['estimate']:+.2f}%</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({v['ci'][0]:+.2f}, {v['ci'][1]:+.2f})</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{v['n']}/{v['G']}</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(v['badge'])}</td></tr>")
    body = f"""
      <table>
        <thead><tr><th>Context cell</th><th>E4 estimate</th><th>Cluster CI</th><th>n/G</th><th>Badge</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Sign held in {summ['sign_held']}/{summ['n_computed']} computed cells · CI excluded zero in
        {summ['ci_excluded_zero']}/{summ['n_computed']} · breaks in: {escape(', '.join(summ['breaks']) or 'none')} ·
        UNDERPOWERED cells: {escape(', '.join(summ['underpowered']) or 'none')}.
        Context grid pre-declared at registration; every cell ledger-counted.
        {escape(data['expected_fp_line'])}. {escape(_IMPLICATION)}
      </p>"""
    return _panel("Context robustness",
                  f"protocol {escape(data['protocol_id'])} · pre-declared grid · registered before computation", body)


def lifecycle_html() -> str:
    p = _REPO / "output" / "oie" / "evidence_lifecycle.json"
    if not p.exists():
        return ""
    data = json.loads(p.read_text())
    rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px;font-family:JetBrains Mono,monospace'>{escape(et)}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{r['n']}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{r['peak_tau']}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{r['peak_value_pct']}%</td>"
        f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(r['half_life'])}</td></tr>"
        for et, r in data["pooled_types"].items())
    thin = ", ".join(f"{escape(et)} (n={r['n']})"
                     for et, r in data["thin_types"].items())
    st = data["staleness"].get("SMH") or {}
    body = f"""
      <table>
        <thead><tr><th>Event type (pooled, backfill era)</th><th>n</th><th>Peak day</th><th>Peak |CAR|</th><th>Half-life</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Median time-to-peak across qualifying types: {data['median_time_to_peak_pooled']} trading days —
        at the window edge for every qualifying type, with no half-life reached. An absolute cumulative
        path rises mechanically with horizon, so this pattern is what no-decay looks like under this
        estimator; it is not evidence of late-arriving impact. Types below the n≥15 floor, listed not
        plotted: {thin or 'none'}. Evidence freshness (this sleeve): median age {st.get('median_age_days', '—')}d,
        {st.get('share_le_7d_pct', '—')}% within 7d, {st.get('share_gt_30d_pct', '—')}% older than 30d.
        {escape(_IMPLICATION)}
      </p>"""
    return _panel("Evidence lifecycle",
                  f"protocol {escape(data['protocol_id'])} · display-only diffusion read · registered before computation", body)


# ---------------------------------------------------------------- Part D
def funnel_html() -> str:
    cov = overlap_summary()["covered"]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT count(*) FROM events_raw WHERE ticker = ANY(%s)",
                        (cov,))
            n_filings = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*),
                          count(*) FILTER (WHERE event_status='accepted')
                   FROM events WHERE ticker = ANY(%s)
                     AND event_time::date >= %s""", (cov, FORWARD_DAY0))
            n_cand, n_acc = cur.fetchone()
            cur.execute(
                """SELECT count(*) FROM (
                     SELECT DISTINCT ticker, event_type, direction,
                            event_time::date
                     FROM events WHERE event_status='accepted'
                       AND ticker = ANY(%s) AND event_time::date >= %s) d""",
                (cov, FORWARD_DAY0))
            n_dedup = cur.fetchone()[0]
            cur.execute(
                """SELECT DISTINCT ticker, direction, event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND event_time::date >= %s
                     AND direction <> 0""", (cov, FORWARD_DAY0))
            directional = cur.fetchall()

    # completed event windows at +5/+10/+20 — same walk as the estimand path
    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}

    def rets(tk):
        out, prev = {}, None
        for d in trade_dates:
            p = prices.get(tk, {}).get(d)
            if p is not None and prev not in (None, 0):
                out[d] = p / prev - 1.0
            if p is not None:
                prev = p
        return out

    tk_ret = {tk: rets(tk) for tk in cov}
    peer = {}
    for tk in cov:
        others = [o for o in cov if o != tk]
        pr = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in others]
            vals = [x for x in vals if x is not None]
            if vals:
                pr[d] = sum(vals) / len(vals)
        peer[tk] = pr

    completed = {5: 0, 10: 0, 20: 0}
    for tk, _dirn, ev_date in directional:
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            continue
        i0 = idx[day0]
        est = trade_dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        pairs = [(tk_ret[tk].get(d), peer[tk].get(d)) for d in est]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < EST_MIN or ols([a for a, _ in pairs],
                                       [b for _, b in pairs]) is None:
            continue
        for h in completed:
            j = i0 + h
            if j < len(trade_dates) and tk_ret[tk].get(trade_dates[j]) is not None \
                    and peer[tk].get(trade_dates[j]) is not None:
                completed[h] += 1

    issuers = len({t for t, _d, _e in directional})
    dates = len({e for _t, _d, e in directional})
    cur20 = completed[20]

    def gap(cur, req):
        return ("<span style='color:#00E676'>met</span>" if cur >= req else
                f"<span style='color:#FBA94B'>{req - cur} short</span>")

    stages = [
        ("Live filings polled (events_raw, covered tickers)", n_filings),
        (f"Candidate events since forward Day 0 ({FORWARD_DAY0})", n_cand),
        ("Accepted", n_acc),
        ("Deduped (ticker · type · direction · day)", n_dedup),
        ("Direction-classified (direction ≠ 0)", len(directional)),
        ("Completed +5d windows", completed[5]),
        ("Completed +10d windows", completed[10]),
        ("Completed +20d windows", completed[20]),
        ("Distinct issuers (directional)", issuers),
        ("Distinct event dates (directional)", dates),
    ]
    rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{s}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{n}</td></tr>"
        for s, n in stages)
    req_rows = (
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>events with +20d window</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{cur20} / {REQUIRED['events']}</td>"
        f"<td style='padding:6px 12px;font-size:12px'>{gap(cur20, REQUIRED['events'])}</td></tr>"
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>distinct issuers</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{issuers} / {REQUIRED['issuers']}</td>"
        f"<td style='padding:6px 12px;font-size:12px'>{gap(issuers, REQUIRED['issuers'])}</td></tr>"
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>distinct event dates</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{dates} / {REQUIRED['dates']}</td>"
        f"<td style='padding:6px 12px;font-size:12px'>{gap(dates, REQUIRED['dates'])}</td></tr>")
    body = f"""
      <table><thead><tr><th>Stage</th><th>Count</th></tr></thead><tbody>{rows}</tbody></table>
      <div style="font-size:11px;color:#718096;margin:14px 0 4px;text-transform:uppercase;letter-spacing:1px">Minimum clusters for live-era standalone inference (locked badge floors) vs current</div>
      <table><thead><tr><th>Requirement</th><th>Current / required</th><th>Status</th></tr></thead><tbody>{req_rows}</tbody></table>
      <p style="font-size:11px;color:#718096;margin-top:8px">Counts are point-in-time reads of the live pipeline; the live era is never blended with the backfill era in any statistic.</p>"""
    return _panel("Live maturity funnel · covered sleeve",
                  "review §16 · live-era pipeline stages through today", body)


def holdings_html() -> str:
    today = datetime.now(timezone.utc).date()
    asof = date.fromisoformat(SMH_AS_OF)
    disclosed = round(sum(SMH_HOLDINGS.values()), 2)
    covered_w = overlap_summary()["covered_weight_pct"]
    body = f"""
      <table>
        <tbody>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Holdings as-of date (issuer disclosure)</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{SMH_AS_OF}</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Retrieved into the evidence store</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{HOLDINGS_RETRIEVED}</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Snapshot age today</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B'>{(today - asof).days} days</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Disclosed holdings / weight</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{len(SMH_HOLDINGS)} names · {disclosed}%</td></tr>
        </tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        <strong style="color:#E2E8F0">Renormalization statement:</strong> posture and E3/E4 estimand weights
        renormalize issuer fund weights over the covered {covered_w}% sleeve only; no statistic on this page
        weights by full-fund share. Constituent weights are dated issuer disclosures, not market data.
      </p>
      <p style="font-size:11px;color:#718096;margin-top:6px">
        Rounding footnote (per disposition): the issuer's disclosed weights sum to {disclosed}%, so the
        undisclosed residual computes to {round(100 - disclosed, 2)}% — shown as measured, an artifact of
        the issuer's two-decimal rounding, not a data error.
      </p>"""
    return _panel("Holdings intelligence",
                  "review §20 · provenance and freshness of the constituent snapshot", body)


def cross_etf_html() -> str:
    groups = {"SMH": {t: w for t, w in SMH_HOLDINGS.items()
                      if t in overlap_summary()["covered"]}}
    groups.update({k: v for k, v in canada_lens_holdings().items()})
    issuers: dict = {}
    for g, hold in groups.items():
        for tk, w in hold.items():
            issuers.setdefault(tk, {})[g] = w
    multi = {tk: d for tk, d in issuers.items() if len(d) >= 2}
    if multi:
        rows = "".join(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(tk)}</td>"
            + "".join(f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{d.get(g, 0) or '—'}</td>"
                      for g in groups) + "</tr>"
            for tk, d in sorted(multi.items()))
        table = (f"<table><thead><tr><th>Issuer</th>"
                 + "".join(f"<th>{g}</th>" for g in groups)
                 + f"</tr></thead><tbody>{rows}</tbody></table>")
    else:
        table = ("<p style='font-size:12px;color:#A0AEC0'>0 multi-lens issuers across "
                 "SMH and the four Canada lenses — the sectors are disjoint, as expected. "
                 "The machinery is the shipped cross-lens overlap map, extended to include SMH.</p>")
    body = f"""{table}
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        <strong style="color:#E2E8F0">Sector-ETF overlap — stated data gap, not a silent cap:</strong>
        the universe file lists sector ETFs (XLK, SOXX-class, and peers) as fund tickers only; no
        constituent-weight snapshots for them exist in the evidence store (SMH is the only sector ETF
        with a dated holdings snapshot). SMH↔sector-ETF issuer overlaps therefore cannot be computed
        from stored data today. Filling the gap requires ingesting those funds' holdings disclosures —
        staged as a v5.2 item; nothing is estimated in the meantime.
      </p>"""
    return _panel("Cross-ETF issuer map",
                  "shipped cross-lens machinery · SMH + XEG/ZEO/GDX/URNM membership overlap", body)


# ---------------------------------------------------------------- main
def main() -> int:
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = _pid(METHOD_SPEC, PROTOCOL_PARAMS)
    proto = reg.assert_registered(pid)
    run_line = ""
    for ln in reg._lines:
        if ln["kind"] == "run" and ln["payload"]["protocol_id"] == pid:
            run_line = ln["line_hash"][:16]

    ov, facts, verdict, anatomy, top = facts_and_admission()
    br, states = breadth_states(ov)
    es = event_study()
    est = run_estimands(es)

    extra = (falsification_html() + sale_type_html() + momentum_html()
             + geometry_html() + robustness_html() + lifecycle_html()
             + taxonomy_html() + funnel_html() + holdings_html()
             + cross_etf_html())
    render_preview(proto, verdict, facts, anatomy, top, br, states, est,
                   es, run_line, extra_html=extra)
    print("[v5.1] smh_lens.html re-rendered with falsification / taxonomy / "
          "funnel / holdings / cross-ETF sections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
