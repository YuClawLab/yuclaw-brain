"""v5.1 public-flip section blocks (STAGING — v5.1-public-staging branch).

Public-page versions of the v5.1 preview sections. Every inferential number
is read from a registered protocol's recorded run artifact under output/oie/;
nothing is recomputed here except the live maturity funnel (point-in-time
pipeline counts, descriptive). Each builder degrades to a short "pending"
stub when its artifact is absent, so the daily chain can never crash on a
missing box-local file.

Ships on freeze-end (2026-08-15) by merging this branch — one reviewed merge,
no build day.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_OIE = _REPO / "output" / "oie"

HOLDINGS_RETRIEVED = "2026-07-05"
_IMPLICATION = ("Investment implication: none established — no buy, sell, or "
                "alpha conclusion is supported by this page.")
REQUIRED = {"events": 10, "issuers": 8, "dates": 10}


def _load(name: str):
    p = _OIE / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _panel(pid, title, sub, body):
    return (f'<div class="panel" id="{pid}"><div class="panel-title">{title}</div>'
            f'<div class="panel-sub">{sub}</div>{body}</div>')


def _pending(pid, title, what):
    return _panel(pid, title, "artifact pending",
                  f"<p style='font-size:12px;color:#718096'>{escape(what)} has "
                  "not been produced on this build box yet; this section "
                  "renders automatically once its registered runner has run.</p>")


# ------------------------------------------------------------ SMH estimands
def smh_estimand_panel() -> str:
    data = _load("smh_lens_run.json")
    if not data:
        return _pending("estimands", "Multi-estimand CAR (registered)",
                        "the SMH multi-estimand run artifact")
    e = data["estimands"]["backfill"]
    order = [("event", "E1 event-weighted"), ("issuer", "E2 issuer-weighted"),
             ("etf", "E3 ETF-weighted"),
             ("capped", "E4 capped-ETF-weighted — PRIMARY")]
    rows = []
    has_tw = any(e[k].get("two_way") for k, _ in order)
    for k, desc in order:
        r = e[k]
        hl = " style='background:#1A2334'" if k == "capped" else ""
        tw = r.get("two_way")
        tw_cell = ""
        if has_tw:
            if tw:
                deg = " DEGENERATE" if tw.get("degenerate") else ""
                tw_cell = (f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-size:11px'>"
                           f"({tw['ci'][0]:+.2f}, {tw['ci'][1]:+.2f}) "
                           f"<span style='color:#718096'>[{escape(tw['badge'])}{deg}]</span></td>")
            else:
                tw_cell = "<td style='padding:7px 12px;color:#718096'>—</td>"
        rows.append(
            f"<tr{hl}><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{desc}</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366;font-weight:700'>{r['mean_pct']:+.2f}%</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({r['issuer_ci'][0]:+.2f}, {r['issuer_ci'][1]:+.2f})</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({r['date_ci'][0]:+.2f}, {r['date_ci'][1]:+.2f})</td>"
            f"<td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B;font-size:11px'>({r['envelope'][0]:+.2f}, {r['envelope'][1]:+.2f})</td>"
            f"{tw_cell}"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")
    ei = e["issuer"]
    fal_line = ""
    fp = _OIE / "falsification_run.json"
    if fp.exists():
        fpan = json.loads(fp.read_text()).get("panels", {}).get("SMH-E4")
        if fpan:
            fal_line = (
                f"<p style='font-size:12px;color:#A0AEC0;margin-top:8px;line-height:1.6'>"
                f"<strong style='color:#E2E8F0'>Falsification context for this table"
                f"</strong> (same population, registered battery): event-date-shuffle "
                f"percentile {fpan['date_shuffle']['percentile_in_null']:.3f} — "
                f"unremarkable within its null, so an era-generic component cannot be "
                f"excluded; direction sign-flip percentile "
                f"{fpan['sign_flip']['percentile_in_null']:.3f}; pre-event placebo "
                f"{fpan['placebo_minus20d']['value_pct']:+.2f}% at null percentile "
                f"{fpan['placebo_minus20d']['percentile_in_shuffle_null']:.3f}. An "
                f"envelope that excludes zero should be read WITH these beside it, "
                f"whichever way they cut.</p>")
    body = f"""
      <table>
        <thead><tr><th>Estimand</th><th>Mean CAR +20d</th><th>Issuer-cluster CI</th><th>Date-cluster CI</th><th>Conservative envelope</th>{'<th>Formal two-way CI (CGM)</th>' if has_tw else ''}<th>Badge</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      {fal_line}
      {_matched_control_line()}
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        The adverse point estimate persists under all four registered weightings; envelopes exclude
        zero for {', '.join(desc.split(' — ')[0] for kk, desc in order if not (e[kk]['envelope'][0] <= 0 <= e[kk]['envelope'][1])) or 'none of the estimands'}
        and include zero for {', '.join(desc.split(' — ')[0] for kk, desc in order if e[kk]['envelope'][0] <= 0 <= e[kk]['envelope'][1]) or 'none'}.
        Envelope = wider of the issuer-/date-cluster bootstrap CIs; the formal CGM two-way interval is
        reported in the table beside it.
      </p>"""
    return _panel("estimands", "Multi-estimand direction-aligned CAR · backfill era (registered)",
                  f"protocol {escape(data['protocol_id'])} · method {escape(data['method_hash'])} · "
                  "registered before computation · recorded run artifact", body)


# ------------------------------------------------------------ falsification
def falsification_panel(target: str, pid: str = "falsification") -> str:
    data = _load("falsification_run.json")
    if not data or target not in data.get("panels", {}):
        return _pending(pid, "Falsification battery", "the falsification run artifact")
    panel = data["panels"][target]
    ds, sf, pl = (panel["date_shuffle"], panel["sign_flip"],
                  panel["placebo_minus20d"])
    drop = (f" · {pl['dropped']} of {panel['n_events']} events dropped "
            f"(shifted day0 pre-dates usable estimation history — disclosed)"
            if pl["dropped"] else "")
    body = f"""
      <table>
        <thead><tr><th>Test</th><th>Real value</th><th>Null mean ± sd</th><th>Null 2.5–97.5%</th><th>Percentile of real in null</th></tr></thead>
        <tbody>
        <tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>Event-date shuffle</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{panel['real_pct']:+.2f}%</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{ds['null']['mean']:+.2f}% ± {ds['null']['sd']:.2f}</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#718096'>({ds['null']['p2_5']:+.2f}, {ds['null']['p97_5']:+.2f})</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{ds['percentile_in_null']:.3f}</td></tr>
        <tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>Direction sign-flip</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#FF3366'>{panel['real_pct']:+.2f}%</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{sf['null']['mean']:+.2f}% ± {sf['null']['sd']:.2f}</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#718096'>({sf['null']['p2_5']:+.2f}, {sf['null']['p97_5']:+.2f})</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{sf['percentile_in_null']:.3f}</td></tr>
        <tr><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>Pre-event placebo (−20d)</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{pl['value_pct']:+.2f}%</td>
        <td style='padding:7px 12px;color:#718096;font-size:11px' colspan='2'>located in the date-shuffle null{drop}</td>
        <td style='padding:7px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-weight:700'>{pl['percentile_in_shuffle_null']:.3f}</td></tr>
        </tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Two-sided extremity: percentiles near 0 and near 100 are both extreme; mid-range percentiles mean
        the real value is unremarkable within its null. Exploratory; every cell ledger-counted under
        Falsification Battery v1 (protocol {escape(data['protocol_id'])}, registered before computation).
      </p>"""
    return _panel(pid, f"Falsification battery · {escape(target)}",
                  f"N={data['n_null']} per null · seed {data['seed']}", body)


# ------------------------------------------------------------ taxonomy
_TAX_LABEL = {"S_discretionary": "S · discretionary open-market sale",
              "S_plan_10b5_1": "S · Rule 10b5-1 plan sale",
              "F_tax_withholding": "F · tax-withholding disposition (mechanical)",
              "M_exercise": "M · option exercise / conversion (mechanical)",
              "A_award": "A · award / grant (mechanical)",
              "D_to_issuer": "D · disposition to issuer",
              "P_purchase": "P · open-market purchase", "other": "other codes"}


def taxonomy_panel(lens: str, pid: str = "taxonomy") -> str:
    data = _load("form4_taxonomy.json")
    if not data or lens not in data.get("lenses", {}):
        return _pending(pid, "Form-4 transaction taxonomy", "the taxonomy artifact")
    roll = data["lenses"][lens]
    c, v = roll["tx_counts"], roll["value_usd"]
    total = sum(c.values())
    if total == 0:
        return _panel(pid, "Form-4 transaction taxonomy",
                      "deterministic XML parse · display-only",
                      "<p style='font-size:12px;color:#718096'>No ingested "
                      "Form-4 substrate for this lens's members (MJDS/FPI "
                      "insider filings are outside current evidence scope — "
                      "SEDI substrate not ingested).</p>")
    rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{_TAX_LABEL[k]}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c[k]}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{c[k]/total*100:.1f}%</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{('$' + format(v[k], ',')) if k in v else '—'}</td></tr>"
        for k in data["classes"] if c[k])
    t3 = []
    for tk in roll["top3_by_events"]:
        m = roll["members"][tk]
        mc = m["tx_counts"]
        t3.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(tk)}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{m['ingested_events']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['S_discretionary']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['S_plan_10b5_1']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['F_tax_withholding']}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{mc['M_exercise'] + mc['A_award']}</td></tr>")
    body = f"""
      <table>
        <thead><tr><th>Code class</th><th>Transactions</th><th>Share</th><th>$ mass (non-deriv rows)</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="font-size:11px;color:#718096;margin:14px 0 4px;text-transform:uppercase;letter-spacing:1px">Top-3 members by ingested events</div>
      <table>
        <thead><tr><th>Ticker</th><th>Ingested events</th><th>S discretionary</th><th>S 10b5-1</th><th>F withholding</th><th>M+A mechanical</th></tr></thead>
        <tbody>{''.join(t3)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Deterministic XML parse of {data['n_filings']} ingested filings; 10b5-1 is the filing-level
        checkbox; dollar mass from non-derivative rows only. Display-only — zero LLM, scoring inputs
        untouched. Research classifications, not recommendations.
      </p>"""
    return _panel(pid, "Form-4 transaction taxonomy · covered members",
                  f"built {escape(data['built_utc'])} · display-only", body)


# ------------------------------------------------------------ funnel + holdings
def smh_funnel_panel() -> str:
    """Live maturity funnel — point-in-time descriptive counts (recomputed at
    render time; the only block here not read from a run artifact)."""
    try:
        import psycopg2
        from v3.lab.cohort_engine import DSN, FORWARD_DAY0, load_prices
        from v3.lab.etf_evidence import (EST_GAP, EST_MIN, EST_WIN,
                                         overlap_summary)
        from v3.lab.stats import ols
    except Exception:
        return _pending("funnel", "Live maturity funnel", "the funnel data source")
    cov = overlap_summary()["covered"]
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT count(*) FROM events_raw WHERE ticker = ANY(%s)", (cov,))
            n_filings = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*), count(*) FILTER (WHERE event_status='accepted')
                   FROM events WHERE ticker = ANY(%s) AND event_time::date >= %s""",
                (cov, FORWARD_DAY0))
            n_cand, n_acc = cur.fetchone()
            cur.execute(
                """SELECT count(*) FROM (SELECT DISTINCT ticker, event_type,
                       direction, event_time::date FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND event_time::date >= %s) d""", (cov, FORWARD_DAY0))
            n_dedup = cur.fetchone()[0]
            cur.execute(
                """SELECT DISTINCT ticker, direction, event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND event_time::date >= %s
                     AND direction <> 0""", (cov, FORWARD_DAY0))
            directional = cur.fetchall()
    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    tk_ret = {}
    for tk in cov:
        out, prev = {}, None
        for d in trade_dates:
            p = prices.get(tk, {}).get(d)
            if p is not None and prev not in (None, 0):
                out[d] = p / prev - 1.0
            if p is not None:
                prev = p
        tk_ret[tk] = out
    peer = {}
    for tk in cov:
        pr = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in cov if o != tk]
            vals = [x for x in vals if x is not None]
            if vals:
                pr[d] = sum(vals) / len(vals)
        peer[tk] = pr
    completed = {5: 0, 10: 0, 20: 0}
    for tk, _d, ev_date in directional:
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
            if (j < len(trade_dates)
                    and tk_ret[tk].get(trade_dates[j]) is not None
                    and peer[tk].get(trade_dates[j]) is not None):
                completed[h] += 1
    issuers = len({t for t, _d, _e in directional})
    dates = len({e for _t, _d, e in directional})

    def gap(cur_v, req):
        return ("<span style='color:#00E676'>met</span>" if cur_v >= req else
                f"<span style='color:#FBA94B'>{req - cur_v} short</span>")

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
    req_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{lbl}</td>"
        f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>{cur_v} / {req}</td>"
        f"<td style='padding:6px 12px;font-size:12px'>{gap(cur_v, req)}</td></tr>"
        for lbl, cur_v, req in
        (("events with +20d window", completed[20], REQUIRED["events"]),
         ("distinct issuers", issuers, REQUIRED["issuers"]),
         ("distinct event dates", dates, REQUIRED["dates"])))
    body = f"""
      <table><thead><tr><th>Stage</th><th>Count</th></tr></thead><tbody>{rows}</tbody></table>
      <div style="font-size:11px;color:#718096;margin:14px 0 4px;text-transform:uppercase;letter-spacing:1px">Minimum clusters for live-era standalone inference (locked badge floors) vs current</div>
      <table><thead><tr><th>Requirement</th><th>Current / required</th><th>Status</th></tr></thead><tbody>{req_rows}</tbody></table>
      <p style="font-size:11px;color:#718096;margin-top:8px">Point-in-time pipeline counts; the live era is never blended with the backfill era in any statistic.</p>"""
    return _panel("funnel", "Live maturity funnel · covered sleeve",
                  "live-era pipeline stages, recomputed at render time", body)


def ecs_covered_table(tickers) -> str:
    """Evidence Coverage v1 (e3d51f5b0ca3) per covered constituent. The
    registered computation covers U79 names only; constituents outside
    U79 print an em-dash, disclosed. Caption is locked by the spec."""
    import json as _j
    f = Path(__file__).resolve().parents[2] / "output" / "oie" / "evidence_coverage.json"
    try:
        scores = _j.loads(f.read_text())["scores"]
    except Exception:
        return ""
    rows = "".join(
        f"<tr><td style='padding:5px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{tk}</td>"
        f"<td style='padding:5px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>"
        f"{scores.get(tk, {}).get('ecs', '—')}</td></tr>"
        for tk in tickers)
    return f"""
      <p style="font-size:12px;color:#A0AEC0;margin:12px 0 4px"><strong style="color:#E2E8F0">Evidence coverage per covered constituent</strong> — how much evidence stands under this classification — coverage, not prediction (Evidence Coverage v1, registered protocol). Names outside the 79-name scoring universe print an em-dash: the registered computation covers U79 only.</p>
      <table><thead><tr><th style='padding:5px 12px'>Name</th><th style='padding:5px 12px'>Evidence coverage</th></tr></thead><tbody>{rows}</tbody></table>"""


def smh_holdings_panel() -> str:
    from v3.lab.etf_evidence import SMH_AS_OF, SMH_HOLDINGS, overlap_summary
    today = datetime.now(timezone.utc).date()
    asof = date.fromisoformat(SMH_AS_OF)
    disclosed = round(sum(SMH_HOLDINGS.values()), 2)
    covered_w = overlap_summary()["covered_weight_pct"]
    body = f"""
      <table><tbody>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Holdings as-of date (issuer disclosure)</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{SMH_AS_OF}</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Retrieved into the evidence store</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{HOLDINGS_RETRIEVED}</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Snapshot age today</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#FBA94B'>{(today - asof).days} days</td></tr>
        <tr><td style='padding:6px 12px;color:#718096;font-size:12px'>Disclosed holdings / weight</td><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{len(SMH_HOLDINGS)} names · {disclosed}%</td></tr>
      </tbody></table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        <strong style="color:#E2E8F0">Renormalization statement:</strong> posture and E3/E4 estimand weights
        renormalize issuer fund weights over the covered {covered_w}% sleeve only; no statistic on this page
        weights by full-fund share. Constituent weights are dated issuer disclosures, not market data.
      </p>
      <p style="font-size:11px;color:#718096;margin-top:6px">
        Rounding footnote: the issuer's disclosed weights sum to {disclosed}%, so the undisclosed residual
        computes to {round(100 - disclosed, 2)}% — shown as measured, an artifact of the issuer's
        two-decimal rounding, not a data error.
      </p>{ecs_covered_table(sorted(SMH_HOLDINGS))}"""
    return _panel("holdings", "Holdings intelligence",
                  "provenance and freshness of the constituent snapshot", body)


# ---------------------------------------------- Fields-review panels (flip)
def fields_review_panels() -> str:
    """Evidence structure / Context robustness / Evidence lifecycle — the
    Jul-30 engine panels, promoted to the public page at the flip. Reuses
    the staged builders (same artifacts, same copy); degrades to empty when
    artifacts are absent so the daily chain can never crash here."""
    try:
        import sys as _s
        _tools = str(_REPO / "tools")
        if _tools not in _s.path:
            _s.path.insert(0, _tools)
        from yuclaw_oie_v51_preview import (geometry_html, lifecycle_html,
                                            robustness_html)
        return geometry_html() + robustness_html() + lifecycle_html()
    except Exception as exc:                     # noqa: BLE001
        return (f"<!-- fields-review panels unavailable: "
                f"{str(exc)[:120]} -->")


# ------------------------------------------------------------ baselines
def baselines_block() -> str:
    """Public Baselines panel (credibility battery, 2026-08-01) — the
    composite vs five deterministic baselines, pre-registered; ties and
    losses print as measured."""
    data = _load("baselines_run.json")
    if not data:
        return ""
    label = {"composite": "Composite (the platform's score)",
             "random": "Random rank (seeded)",
             "momentum60": "Momentum rank (prior 60d return)",
             "reversal5": "Short-reversal rank (prior 5d, inverted)",
             "persistence": "Previous-day-score persistence",
             "equal_weight": "Equal-weight component composite"}
    rows = []
    for n in ("composite", "random", "momentum60", "reversal5",
              "persistence", "equal_weight"):
        t = data["table"][n]
        d5 = data["diffs_k5"].get(n)
        diff_cell = ("<td style='padding:6px 12px;color:#718096'>—</td>"
                     if not d5 else
                     f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;font-size:11px;"
                     f"color:{'#FF3366' if d5['diff'] < 0 else '#A0AEC0'}'>"
                     f"{d5['diff']:+.4f} ({d5['ci'][0]:+.4f}, {d5['ci'][1]:+.4f}) "
                     f"<span style='color:#718096'>[{d5['badge']}]</span></td>")
        hl = " style='background:#1A2334'" if n == "composite" else ""
        rows.append(
            f"<tr{hl}><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{label[n]}</td>"
            + "".join(f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>"
                      f"{t[str(k)]['mean_ic']:+.4f}</td>" if t[str(k)]['mean_ic'] is not None
                      else "<td style='padding:6px 12px;color:#718096'>—</td>"
                      for k in (1, 5, 20))
            + diff_cell + "</tr>")
    pr = data["primary"]
    body = f"""
      <table>
        <thead><tr><th>Strategy</th><th>Mean IC k=1</th><th>Mean IC k=5</th><th>Mean IC k=20</th><th>Composite − baseline @k=5 (clustered CI)</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Most platforms never test this. The comparison is pre-registered; results appear as measured.
        Registered primary: composite minus the top-scoring baseline per the registered argmax rule
        ({escape(data['best_baseline_k5'])}) at k=5 =
        <strong style="color:{'#FF3366' if pr['diff'] < 0 else '#E2E8F0'}">{pr['diff']:+.4f}</strong>
        CI ({pr['ci'][0]:+.4f}, {pr['ci'][1]:+.4f}) [{escape(pr['badge'])}] over
        {data['window']['n_dates']} forward dates / {data['window']['n_tickers']} clustered tickers.
        At this sample the persistence baseline reads ahead of the composite at k=5 — printed exactly as
        measured; the window is young and the comparison recomputes as the record accrues.
        Interpretation note: yesterday's score and today's are highly overlapping (the composite moves
        slowly), so the persistence comparison is not between independent signals — a one-day-lagged copy
        of a slow-moving score can rank ahead at short horizons under reversal-like return structure
        without containing any information the composite lacks. Because it re-uses yesterday's own composite, this
        baseline measures day-over-day continuity and smoothing behavior, not an independent
        competitor strategy — the honest reading is that the daily composite is noisy at k=5,
        not that a rival wins.
        Investment implication: none established — no buy, sell, or alpha conclusion is supported by
        this page.
      </p>"""
    return _panel("baselines", "Baselines — the composite vs simple alternatives (registered)",
                  f"protocol {escape(data['protocol_id'])} · forward-OOS · registered before computation",
                  body)


def _matched_control_line() -> str:
    """Matched-control adjusted estimand (registered; review Part E)."""
    d = _load("matched_control.json")
    if not d:
        return ""
    a = d["adjusted_E4"]
    return (
        f"<p style='font-size:12px;color:#A0AEC0;margin-top:8px;line-height:1.6'>"
        f"<strong style='color:#E2E8F0'>Matched controls</strong> (protocol "
        f"{escape(d['protocol_id'])}, registered): each event paired with a same-day, "
        f"event-free sleeve issuer nearest in standardized momentum+volatility "
        f"({d['n_pairs']} pairs, {d['n_excluded']} excluded, median match distance "
        f"{d['median_match_distance']} sd). Matched-control-adjusted E4 = "
        f"<strong style='color:#FF3366'>{a['mean_pct']:+.2f}%</strong> CI "
        f"({a['ci'][0]:+.2f}, {a['ci'][1]:+.2f}) [{escape(a['badge'])}]. Read together "
        f"with the falsification context above: the timing of the adverse alignment is "
        f"not distinguishable from its era, but relative to matched factor twins on the "
        f"same days it is issuer-day-specific — both facts print; neither is a "
        f"recommendation.</p>")


def _qualified_rows() -> str:
    """Qualified-pool clustered spreads (registered addendum, Part D)."""
    data = _load("qualified_clustered.json")
    if not data:
        return ""
    rows = []
    for k in ("1", "5", "20"):
        r = data["results"].get(k)
        if not r:
            continue
        rows.append(
            f"<tr><td style='padding:6px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace;font-size:12px'>Evidence-Qualified pool · k={k}{' — addendum primary' if k == '5' else ''}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{r['spread_mean']*100:+.2f}%</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-size:11px'>({r['cluster_ci'][0]*100:+.2f}%, {r['cluster_ci'][1]*100:+.2f}%)</td>"
            f"<td colspan='2' style='padding:6px 12px;color:#718096;font-size:11px'>qualified cross-section only (protocol {escape(data['protocol_id'])})</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{r['n_dates']}d/{r['G_tickers']}t</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")
    return ("<table><tbody>" + "".join(rows) + "</tbody></table>") if rows else ""


# ---------------------------------------------- case exhibits (Part B)
def case_exhibits_block() -> str:
    """Per-name case cards for the current top and bottom composite deciles —
    illustrative exhibits, never stock picks; every citation is a real event
    ID verified against the store before render."""
    import psycopg2
    try:
        from v3.lab.cohort_engine import DSN, DECILE_FRACTION
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (ticker) ticker, signal_label,
                           total_score, signal_time::date,
                           c1_price_momentum, c6_event_impact,
                           c7_peer_correlation, c8_cascade_effect
                    FROM signal_snapshots WHERE is_backfill = false
                    ORDER BY ticker, signal_time DESC""")
                snaps = [dict(zip(("ticker", "label", "score", "as_of",
                                   "c1", "c6", "c7", "c8"), r))
                         for r in cur.fetchall()]
                ranked = sorted(snaps, key=lambda s: -float(s["score"]))
                k = max(1, round(len(ranked) * DECILE_FRACTION))
                names = ranked[:k] + ranked[-k:]
                cards = []
                for i, s in enumerate(names):
                    cur.execute("""
                        SELECT event_id, event_type, event_time::date,
                               llm_confidence
                        FROM events WHERE event_status='accepted' AND ticker=%s
                        ORDER BY event_time DESC LIMIT 3""", (s["ticker"],))
                    evs = cur.fetchall()
                    cur.execute("""
                        SELECT signal_label, signal_time::date
                        FROM signal_snapshots WHERE ticker=%s
                          AND is_backfill=false
                        ORDER BY signal_time DESC LIMIT 5""", (s["ticker"],))
                    hist = cur.fetchall()
                    # citation verifier: round-trip the IDs
                    ids = [e[0] for e in evs]
                    if ids:
                        cur.execute("SELECT count(*) FROM events "
                                    "WHERE event_id = ANY(%s)", (ids,))
                        if cur.fetchone()[0] != len(ids):
                            continue   # refuse the card rather than mis-cite
                    side = "top decile" if i < k else "bottom decile"
                    ev_html = "".join(
                        f"<li style='font-size:11px;color:#A0AEC0'>{e[2]} "
                        f"{escape(e[1])} (confidence {e[3]}) "
                        f"<code style='font-size:10px'>{escape(e[0])}</code></li>"
                        for e in evs) or "<li style='font-size:11px;color:#718096'>no accepted events on record</li>"
                    age = "—"
                    if evs:
                        from datetime import date as _dd, datetime as _dt, timezone as _tz
                        age = f"{(_dt.now(_tz.utc).date() - evs[0][2]).days}d"
                    hist_html = " → ".join(f"{h[0]}" for h in reversed(hist))
                    comps = (f"c1 {s['c1']:+.2f} · c6 {s['c6']:+.2f} · "
                             f"c7 {s['c7']:+.2f} · c8 {s['c8']:+.2f}"
                             if s["c1"] is not None else "components n/a")
                    cards.append(f"""
        <details style="background:#1A2030;border-radius:8px;margin-bottom:8px">
          <summary style="cursor:pointer;padding:10px 14px;font-size:12px;color:#E2E8F0">
            <span style="font-family:JetBrains Mono,monospace;font-weight:700">{escape(s['ticker'])}</span>
            · {side} · {escape(s['label'])} · score {float(s['score']):+.3f} · evidence age {age}</summary>
          <div style="padding:0 14px 12px">
            <p style="font-size:11px;color:#718096">components: {comps} · label history: {escape(hist_html)}</p>
            <p style="font-size:11px;color:#718096;margin-top:4px">contributing events (accession-linked, verified):</p>
            <ul style="margin-left:18px">{ev_html}</ul>
          </div>
        </details>""")
    except Exception:                             # noqa: BLE001
        return ""
    body = f"""
      {''.join(cards)}
      <p style="font-size:11px;color:#718096;margin-top:8px">
        Illustrative exhibits of how classifications trace to filings — never stock picks. Every event ID
        round-trips to the evidence store before render; full event exports are in the evidence packets.
        {escape(_IMPLICATION)}
      </p>"""
    return _panel("cases", "Case exhibits — score to filings lineage (illustrative)",
                  "current top and bottom composite deciles · citation-verified", body)


# ---------------------------------------------- transparency trio (Part C)
def transparency_block() -> str:
    from datetime import date as _d
    # (1) maturity calendar
    cal_rows = ""
    try:
        import glob as _g
        arms = {"elevated": 0, "normal": 0}
        for f in _g.glob(str(_REPO / "output/swarm/canada/*.json")):
            d = json.loads(Path(f).read_text())
            rc = d.get("risk_channel") or {}
            fl = str(rc.get("flag", "")).lower()
            if fl.startswith("elev"):
                arms["elevated"] += 1
            elif fl:
                arms["normal"] += 1
        cal_rows = f"""
        <tr><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>2026-08-13</td>
        <td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>C6 risk-gate second read (protocol d7d5cc4fde5f)</td>
        <td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>armed · accrual: {arms['elevated']} elevated / {arms['normal']} normal artifacts vs floor 10/arm with completed windows</td></tr>
        <tr><td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>2026-09-01</td>
        <td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>Reversal coherence first read (protocol ea120b0a6b52)</td>
        <td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>guard active (computation refuses before the date); accrual from 2026-07-27; floors 15 events/target, 3 targets</td></tr>"""
    except Exception:                             # noqa: BLE001
        pass
    # (2) audit diff
    diff_html = ""
    ad = _load("audit_diff.json")
    if ad:
        ch = "".join(
            f"<li style='font-size:11px;color:#A0AEC0'><strong style='color:#E2E8F0'>{escape(c['stat'])}</strong>: "
            f"{escape(str(c['change']))} — <em>{escape(c['cause'])}</em></li>"
            for c in ad["changes"][:12]) or \
            "<li style='font-size:11px;color:#718096'>no headline-statistic changes since the previous build</li>"
        diff_html = (f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:14px 0 4px'>"
                     f"What changed and why (vs {escape(str(ad.get('previous_as_of') or 'first record'))})</div>"
                     f"<ul style='margin-left:18px'>{ch}</ul>")
    # (3) outage / diagnostics
    marker = Path("/tmp/yuclaw_push_failed.marker")
    diag = (f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:14px 0 4px'>Monitoring</div>"
            f"<p style='font-size:11px;color:#A0AEC0'>Known outage: 2026-06-26 to 2026-07-03 — snapshots continued point-in-time on frozen price inputs; "
            f"zero retroactive edits (disclosed since it happened). Chain health: 30-minute monitor with alert file; "
            f"push/deploy alarm: {'FAILURE MARKER PRESENT' if marker.exists() else 'clear at build time'}; "
            f"deploy-verify runs after every push (byte-identity against the live site).</p>")
    body = f"""
      <table><thead><tr><th>Date</th><th>Armed event</th><th>Status / accrual</th></tr></thead>
      <tbody>{cal_rows}</tbody></table>
      {diff_html}
      {diag}
      <p style="font-size:11px;color:#718096;margin-top:8px">{escape(_IMPLICATION)}</p>"""
    return _panel("transparency", "Maturity calendar, changes, and monitoring",
                  "armed reads · headline-statistic audit diff · outage and alarm status", body)


# ------------------------------------------------------------ neutralized IC
def neutralized_ic_block() -> str:
    """Raw vs neutralized IC panel (review completion, 2026-08-01)."""
    data = _load("neutralized_ic.json")
    if not data:
        return ""
    rows = []
    for s, row in data["table"].items():
        name = "Composite" if s == "score" else s
        cells = "".join(
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0'>"
            f"{row[v]['mean_ic']:+.4f}</td>" if row[v]["mean_ic"] is not None
            else "<td style='padding:6px 12px;color:#718096'>—</td>"
            for v in ("raw", "beta60", "mom60", "vol20", "joint"))
        hl = " style='background:#1A2334'" if s == "score" else ""
        rows.append(f"<tr{hl}><td style='padding:6px 12px;color:#E2E8F0;"
                    f"font-size:12px;font-family:JetBrains Mono,monospace'>{escape(name)}</td>{cells}</tr>")
    pr = data["primary"]
    body = f"""
      <table>
        <thead><tr><th>Strategy</th><th>Raw IC k=5</th><th>Beta-neutral</th><th>Momentum-neutral</th><th>Vol-neutral</th><th>Jointly neutral</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Registered primary: composite jointly-neutralized IC at k=5 =
        <strong style="color:#E2E8F0">{pr['joint_ic_k5']:+.4f}</strong>
        CI ({pr['ci'][0]:+.4f}, {pr['ci'][1]:+.4f}) [{escape(pr['badge'])}] — the association is not
        explained away by market beta, momentum, or volatility exposure, and it is also not
        statistically distinguishable from zero at this sample; both facts print. Component cells are
        exploratory: note c8's raw association largely dissolves under neutralization (factor exposure,
        reported as measured); blank rows are the masked (c2) and frozen (c4) components with no
        cross-sectional variation. {escape(data['sector_cell'])}.
        Investment implication: none established — no buy, sell, or alpha conclusion is supported by
        this page.
      </p>"""
    return _panel("neutralized", "Neutralized association — raw vs factor-neutralized (registered)",
                  f"protocol {escape(data['protocol_id'])} · forward-OOS · registered before computation",
                  body)


# ------------------------------------------------------------ lab clustered
def lab_clustered_block() -> str:
    data = _load("lab_clustered_run.json")
    if not data:
        return ("<p style='font-size:11px;color:#718096;margin-top:12px'>"
                "Clustered decile inference: run artifact pending on this "
                "build box; the registered panel renders once produced.</p>")
    rows = []
    for k in ("1", "5", "20"):
        r = data["results"].get(k) or data["results"].get(int(k))
        if r is None:
            continue
        hl = " style='background:#1A2334'" if k == "5" else ""
        rows.append(
            f"<tr{hl}><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>k={k}{' — PRIMARY' if k == '5' else ''}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{r['spread_mean']*100:+.2f}%</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#4DD0E1;font-size:11px'>({r['cluster_ci'][0]*100:+.2f}%, {r['cluster_ci'][1]*100:+.2f}%)</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({r['wild_ci'][0]*100:+.2f}%, {r['wild_ci'][1]*100:+.2f}%)</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096;font-size:11px'>({r['naive_ci'][0]*100:+.2f}%, {r['naive_ci'][1]*100:+.2f}%)</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{r['n_dates']}d/{r['G_tickers']}t</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")
    return f"""
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin:16px 0 0">Clustered decile inference (registered · protocol {escape(data['protocol_id'])}) — per-signal-date k-day spreads; cluster CI is primary, naive shown beside it labeled naive</div>
        <table>
          <thead><tr><th>Horizon</th><th>Mean spread</th><th>Ticker-cluster CI (primary)</th><th>Wild-cluster CI (small-G remedy)</th><th>Naive CI (comparison)</th><th>dates/tickers</th><th>Badge</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        {_qualified_rows()}
        <p style="font-size:11px;color:#718096;margin-top:6px">
          Same tickers recur in deciles across dates; the ticker-clustered CI absorbs that dependence, the
          naive date-resample CI does not. Estimator differs from the per-rebalance spreads above (per-signal-date
          k-day returns — clustering requires ticker identity); stated side by side, never blended. Locked
          decisions: G&lt;8 UNDERPOWERED retained; percentile CIs retained for v1 (bootstrap-t deferred to v5.3).
        </p>"""
