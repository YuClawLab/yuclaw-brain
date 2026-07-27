#!/usr/bin/env python3
"""
SMH lens staged run (ORDER 2, 2026-07-27) — registry-first activation of the
ETF lens engine (tools/yuclaw_etf_lens.py, METHOD_HASH 5bff6b28) on the REAL
SMH covered-sleeve event set.

Sequence (order is the point — REGISTRY-FIRST):
  1. Register protocol "SMH multi-estimand CAR v1" in registry/protocols.jsonl
     BEFORE any real-data computation. Primary endpoint = E4 capped-ETF-weighted
     mean CAR at +20d (the lens is concentration-limited, so the capped estimand
     is the mandatory headline per the admission standard). E1/E2/E3 and every
     CI variant are secondary, ledger-counted.
  2. Build LensFacts from the real SMH holdings snapshot (v3.lab.etf_evidence)
     -> admission verdict, coverage anatomy, breadth.
  3. Run the four estimands (event/issuer/etf/capped) on the real backfill-era
     direction-aligned event set (peer model, CAR at tau=+20), plus the same
     four on the all-era set as a disclosed sensitivity.
  4. Render docs/preview/smh_lens.html (PREVIEW — unlinked, staged; public
     pages untouched).
  5. Record the run (with result hash) in the registry; chain-verify.

Stdlib + repo modules only. Deterministic given the registered seed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_etf_lens import (LensFacts, METHOD_HASH, METHOD_SPEC, SEED,
                             UncoveredSlice, WeightedClusteredCAR, admit,
                             breadth, coverage_anatomy)
from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id

import psycopg2

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import (EST_MIN, FOREIGN_DOMICILED, SMH_AS_OF,
                                 SMH_HOLDINGS, SMH_SOURCE, event_study,
                                 evidence_rollup, overlap_summary)
from v3.web.useful_blocks import public_label

REGISTRY_PATH = str(_REPO / "registry" / "protocols.jsonl")
OUT_HTML = _REPO / "docs" / "preview" / "smh_lens.html"
OUT_JSON = _REPO / "output" / "oie" / "smh_lens_run.json"

PROTOCOL_NAME = "SMH multi-estimand CAR v1"
PROTOCOL_PARAMS = {
    "lens": "SMH", "holdings_as_of": SMH_AS_OF,
    "sleeve": "covered (US EDGAR filers in the 79-ticker universe)",
    "car_horizon_tau": 20, "car_window": [-5, 20], "ar_model": "peer",
    "alignment": "direction-aligned (AR x direction, direction != 0)",
    "primary_era": "backfill (2026-02-18..2026-05-15) — the adverse-headline sample",
    "estimands": ["event", "issuer", "etf", "capped"],
    "cap_pct_of_sleeve": 20, "B": 4000, "seed": SEED,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------- step 1
def register_first(reg: Registry) -> dict:
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    existing = reg.get_protocol(pid)
    if existing:
        print(f"[registry] protocol {pid} already LOCKED (idempotent rerun)")
        return existing
    reg.register(Protocol(
        protocol_id=pid,
        name=PROTOCOL_NAME,
        method_hash=METHOD_HASH,
        spec_summary=(
            "Multi-estimand direction-aligned CAR on the SMH covered sleeve "
            f"(US EDGAR filers, holdings as of {SMH_AS_OF}). Four pre-committed "
            "weightings (E1 event, E2 issuer, E3 ETF, E4 capped-ETF at 20% of "
            "sleeve); issuer- and date-cluster bootstrap CIs with the wider "
            "taken as a conservative envelope; badges UNDERPOWERED/DESCRIPTIVE/"
            "PRELIMINARY per the locked spec (yuclaw_etf_lens.METHOD_SPEC)."),
        primary_endpoint=(
            "E4 capped-ETF-weighted mean CAR at tau=+20d, peer model, "
            "direction-aligned, backfill era — capped estimand chosen as the "
            "single primary because the lens is concentration-limited "
            "(admission standard makes E4 the mandatory headline)"),
        secondary_endpoints=[
            "E1 event-weighted mean CAR at +20d (envelope CI)",
            "E2 issuer-weighted mean CAR at +20d (envelope CI)",
            "E3 ETF-weighted mean CAR at +20d (envelope CI)",
            "naive independence-assuming CIs, all four estimands (labeled naive)",
            "single-way issuer-cluster and date-cluster CIs, all four "
            "estimands (envelope components, disclosed separately)",
            "all-era sensitivity rerun of E1-E4 (live sample disclosed as "
            "too small for standalone inference)",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — registered BEFORE computation")
    return reg.get_protocol(pid)


# ---------------------------------------------------------------- step 2
def facts_and_admission():
    ov = overlap_summary()
    covered = ov["covered"]
    weights = [ov["weights_covered"][t] for t in covered]

    prices, _ = load_prices()
    n_priced = sum(1 for t in covered if len(prices.get(t, {})) >= EST_MIN)
    price_cov_pct = round(100.0 * n_priced / len(covered), 1) if covered else 0.0

    facts = LensFacts(
        ticker="SMH", holdings_source=SMH_SOURCE, holdings_date=SMH_AS_OF,
        covered_issuers=len(covered), covered_weight_pct=ov["covered_weight_pct"],
        covered_weights=weights, price_coverage_pct=price_cov_pct,
        substrate_disclosed=True, reproduction_bundle=True,
        live_protocol_registered=True,
    )
    verdict = admit(facts)

    disclosed_total = round(sum(SMH_HOLDINGS.values()), 2)
    foreign_w = round(sum(SMH_HOLDINGS[t] for t in ov["uncovered"]
                          if t in FOREIGN_DOMICILED), 2)
    foreign_n = sum(1 for t in ov["uncovered"] if t in FOREIGN_DOMICILED)
    other_w = round(sum(SMH_HOLDINGS[t] for t in ov["uncovered"]
                        if t not in FOREIGN_DOMICILED), 2)
    other_n = len(ov["uncovered"]) - foreign_n
    undisclosed_w = round(100.0 - disclosed_total, 2)
    uncovered = [
        UncoveredSlice("foreign private issuer (6-K / 20-F substrate; "
                       "ingestible via the Canada-vertical 6-K/40-F path — "
                       "coverage decision pending)", foreign_w, foreign_n),
        UncoveredSlice("US filer outside the 79-ticker scored universe",
                       other_w, other_n),
        UncoveredSlice("not disclosed in the free holdings listing",
                       undisclosed_w, 1),
    ]
    top = sorted(ov["weights_covered"].items(), key=lambda kv: -kv[1])
    anatomy = coverage_anatomy(facts, uncovered, top)
    return ov, facts, verdict, anatomy, top


def breadth_states(ov):
    ru = evidence_rollup()
    today = datetime.now(timezone.utc).date()
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT ticker, max(event_time)::date FROM events
                   WHERE event_status = 'accepted' AND ticker = ANY(%s)
                   GROUP BY 1""", (ov["covered"],))
            ages = {t: (today - d).days for t, d in cur.fetchall()}
    states = [(m["ticker"], m["weight_pct"], public_label(m["label"]),
               ages.get(m["ticker"])) for m in ru["members"]]
    return breadth(states), states


# ---------------------------------------------------------------- step 3
def run_estimands(es):
    rows = es["per_event_rows"]
    fund_w = overlap_summary()["weights_covered"]

    def run_set(subset, tag):
        ev = [(r["ticker"], r["date"], r["car20_peer_aligned_pct"]) for r in subset]
        if not ev:
            return None
        wc = WeightedClusteredCAR(ev, fund_w, B=4000, seed=SEED)
        res = wc.run_all()
        return {k: vars(v) for k, v in res.items()}

    backfill = [r for r in rows if r["era"] == "backfill"]
    live = [r for r in rows if r["era"] == "live"]
    return {
        "backfill": run_set(backfill, "backfill"),
        "all_era_sensitivity": run_set(rows, "all"),
        "n_backfill": len(backfill), "n_live": len(live),
        "n_rows_total": len(rows),
        "issuers_backfill": len({r["ticker"] for r in backfill}),
        "dates_backfill": len({r["date"] for r in backfill}),
    }


# ---------------------------------------------------------------- step 4
def _ci(t):  # (lo, hi) -> string
    return f"({t[0]:+.2f}, {t[1]:+.2f})"


def render_preview(proto, verdict, facts, anatomy, top, br, states, est,
                   es, run_line_hash, extra_html: str = ""):
    built = utc_now()
    e = est["backfill"]
    order = [("event", "E1 event-weighted (each event counts once)"),
             ("issuer", "E2 issuer-weighted (each issuer counts once)"),
             ("etf", "E3 ETF-weighted (fund weight, renormalized to sleeve)"),
             ("capped", "E4 capped-ETF-weighted (issuer cap 20% of sleeve) — PRIMARY")]
    est_rows = []
    for k, desc in order:
        r = e[k]
        star = " style='background:#1A2334'" if k == "capped" else ""
        est_rows.append(
            f"<tr{star}><td style='padding:7px 12px;color:#E2E8F0;font-size:12px'>{escape(desc)}</td>"
            f"<td style='padding:7px 12px;color:#FF3366;font-family:JetBrains Mono,monospace;font-weight:700'>{r['mean_pct']:+.2f}%</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['naive_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['issuer_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['date_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#FBA94B;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['envelope'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")

    unc_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#A0AEC0;font-size:12px'>{escape(u['reason'])}</td>"
        f"<td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{u['weight_pct']:.2f}%</td>"
        f"<td style='padding:6px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{u['names']}</td></tr>"
        for u in anatomy["uncovered_by_reason"])

    state_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#4DD0E1;font-size:12px;font-family:JetBrains Mono,monospace'>{escape(s)}</td>"
        f"<td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>{w:.1f}%</td></tr>"
        for s, w in br["state_share_pct"].items())

    member_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{escape(t)}</td>"
        f"<td style='padding:6px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace'>{w:.2f}%</td>"
        f"<td style='padding:6px 12px;color:#4DD0E1;font-size:12px'>{escape(st)}</td>"
        f"<td style='padding:6px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{a if a is not None else '—'}</td></tr>"
        for t, w, st, a in states)

    survives = e["issuer"]["envelope"][1] < 0.0
    primary_adverse = e["capped"]["envelope"][1] < 0.0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PREVIEW — SMH lens (admission + multi-estimand CAR)</title>
  <meta name="robots" content="noindex">
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:Inter,sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:1080px;margin:0 auto;padding:24px}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:4px}}
    .panel-sub{{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:14px}}
    table{{width:100%;border-collapse:collapse;margin-top:12px}}
    th{{font-size:10px;font-weight:600;text-transform:uppercase;color:#718096;padding:8px 12px;text-align:left;border-bottom:1px solid #2D3748;letter-spacing:0.6px}}
    td{{font-size:13px;border-bottom:1px solid #1A2030}}
    code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    .tile{{min-width:120px}}
    .tile .v{{font-size:22px;font-weight:800;color:#FFF;font-family:JetBrains Mono,monospace}}
    .tile .k{{font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:0.6px}}
  </style>
</head>
<body>
  <div class="container">
    <div style="background:#2A1A1A;border:1px solid #FBA94B80;border-radius:8px;padding:12px 18px;margin-bottom:18px;font-size:12px;color:#FBA94B;font-weight:700">
      PREVIEW — real data, not yet part of the daily build. Unlinked staged page; public pages untouched.
    </div>

    <h1 style="font-size:24px;font-weight:800;color:#FFF;letter-spacing:-0.5px;margin-bottom:4px">SMH Lens — Admission + Multi-Estimand CAR</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px">
      Registered protocol <code>{escape(proto['protocol_id'])}</code> ({escape(PROTOCOL_NAME)}) ·
      method <code>{escape(METHOD_HASH)}</code> · registry-first: protocol locked before computation ·
      built {escape(built)}
    </p>
    <div style="background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;color:#A0AEC0">
      <strong style="color:#FBA94B">Disclaimer —</strong> Hypothetical research illustration. Not investment
      advice, not performance advertising. Research classifications, not recommendations. Coverage and
      evidence statistics on the covered sleeve only — not a full-fund inference. Research &amp; education only.
    </div>

    <div class="panel">
      <div class="panel-title">Admission verdict</div>
      <div class="panel-sub">standard: yuclaw_etf_lens v1 thresholds · holdings as of {escape(facts.holdings_date)}</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px">
        <div class="tile"><div class="v" style="color:#FBA94B;font-size:16px">{escape(verdict['label'])}</div><div class="k">lens label</div></div>
        <div class="tile"><div class="v">{verdict['effective_issuers']:.2f}</div><div class="k">effective issuers (inverse HHI)</div></div>
        <div class="tile"><div class="v">{facts.covered_issuers}</div><div class="k">covered issuers</div></div>
        <div class="tile"><div class="v">{facts.covered_weight_pct:.2f}%</div><div class="k">covered weight</div></div>
        <div class="tile"><div class="v">{facts.price_coverage_pct:.0f}%</div><div class="k">price coverage</div></div>
      </div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.6">
        {escape(verdict.get('requirement', ''))}
      </p>
      <p style="font-size:11px;color:#718096;margin-top:6px">{escape(verdict.get('note', ''))}</p>
    </div>

    <div class="panel">
      <div class="panel-title">Coverage anatomy</div>
      <div class="panel-sub">identity check: covered {anatomy['covered_weight_pct']:.2f}% + uncovered {anatomy['uncovered_weight_pct']:.2f}% = {anatomy['identity_check_pct']:.2f}%</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v">{anatomy['top1_covered_pct']:.2f}%</div><div class="k">top-1 covered ({escape(anatomy['largest_covered'][0])})</div></div>
        <div class="tile"><div class="v">{anatomy['top3_covered_pct']:.2f}%</div><div class="k">top-3 covered</div></div>
        <div class="tile"><div class="v">{anatomy['top5_covered_pct']:.2f}%</div><div class="k">top-5 covered</div></div>
        <div class="tile"><div class="v">{anatomy['effective_covered_issuers']:.2f}</div><div class="k">effective covered issuers</div></div>
      </div>
      <table>
        <thead><tr><th>Uncovered — reason</th><th>Weight</th><th>Names</th></tr></thead>
        <tbody>{unc_rows}</tbody>
      </table>
    </div>

    <div class="panel">
      <div class="panel-title">Breadth — covered sleeve by research state</div>
      <div class="panel-sub">share of covered weight per locked signal label · evidence freshness split</div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:8px">
        <div class="tile"><div class="v">{br['fresh_7d_weight_pct']:.1f}%</div><div class="k">weight with evidence ≤ 7d old</div></div>
        <div class="tile"><div class="v">{br['stale_30d_weight_pct']:.1f}%</div><div class="k">weight with evidence &gt; 30d old</div></div>
      </div>
      <table>
        <thead><tr><th>Research state (locked label)</th><th>Share of covered weight</th></tr></thead>
        <tbody>{state_rows}</tbody>
      </table>
      <table>
        <thead><tr><th>Ticker</th><th>SMH weight</th><th>State</th><th>Evidence age (days)</th></tr></thead>
        <tbody>{member_rows}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:8px">Research classifications, not recommendations.</p>
    </div>

    <div class="panel">
      <div class="panel-title">Multi-estimand direction-aligned CAR at τ=+20 · backfill era (the adverse-headline sample)</div>
      <div class="panel-sub">peer model · n={est['n_backfill']} events · {est['issuers_backfill']} issuers · {est['dates_backfill']} dates · B=4000, seed {SEED} · live era n={est['n_live']} (disclosed, too small for standalone inference)</div>
      <table>
        <thead><tr><th>Estimand</th><th>Mean CAR</th><th>Naive CI</th><th>Issuer-cluster CI</th><th>Date-cluster CI</th><th>Conservative envelope</th><th>Badge</th></tr></thead>
        <tbody>{''.join(est_rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:12px;line-height:1.6">
        <strong style="color:#E2E8F0">Does the adverse result survive issuer weighting?</strong>
        Issuer-weighted (E2) envelope {_ci(e['issuer']['envelope'])}:
        {"the entire envelope is below zero — the adverse result is NOT an artifact of one issuer's event count; it survives issuer weighting" if survives else
         "the envelope includes zero — under issuer weighting the adverse result is not distinguishable from zero at this sample; it does NOT clearly survive issuer weighting"}.
        Primary endpoint E4 (capped-ETF-weighted) envelope {_ci(e['capped']['envelope'])}:
        {"adverse and excludes zero under the conservative envelope" if primary_adverse else "envelope includes zero — descriptive at this sample"}.
        Envelope = wider of the issuer-/date-cluster bootstrap CIs; formal two-way clustering pending — stated, not faked.
      </p>
    </div>

    {extra_html}

    <div class="panel">
      <div class="panel-title">Provenance</div>
      <div class="panel-sub">registry-first discipline</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.8">
        Protocol: <code>{escape(proto['protocol_id'])}</code> locked {escape(proto['lock_date'])} ·
        method hash <code>{escape(METHOD_HASH)}</code><br>
        Primary endpoint: {escape(proto['primary_endpoint'])}<br>
        Run recorded: registry line <code>{escape(run_line_hash)}</code> ·
        events {es['n_raw_filings']} filings → {es['n_events_deduped']} deduped → {es['n_events_used']} with estimation window →
        {est['n_rows_total']} directional with complete τ=+20 path<br>
        Chain: verified at build time. Registered before computation on real lens data.
      </p>
    </div>

    <div style="text-align:center;padding:14px;color:#718096;font-size:11px">
      YUCLAW SMH lens preview · built {escape(built)} · research &amp; education only
    </div>
  </div>
</body>
</html>
"""
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html)
    print(f"[preview] wrote {OUT_HTML} ({len(html)} bytes)")


# ---------------------------------------------------------------- main
def main() -> int:
    reg = Registry(REGISTRY_PATH)

    # STEP 1 — registry first, before any real computation
    proto = register_first(reg)
    reg.assert_registered(proto["protocol_id"])

    # STEP 2 — real facts
    ov, facts, verdict, anatomy, top = facts_and_admission()
    br, states = breadth_states(ov)

    # STEP 3 — real event set + estimands
    es = event_study()
    est = run_estimands(es)

    results = {
        "protocol_id": proto["protocol_id"], "method_hash": METHOD_HASH,
        "built_utc": utc_now(), "facts": vars(facts), "verdict": verdict,
        "anatomy": anatomy, "breadth": br, "estimands": est,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, default=str))
    result_hash = hashlib.sha256(
        json.dumps(results, sort_keys=True, default=str).encode()).hexdigest()[:16]

    # STEP 5 — record the run (before render so the page can cite the line)
    line_hash = reg.record_run(Run(
        protocol_id=proto["protocol_id"],
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"backfill-era directional events 2026-02-18..2026-05-15 "
                     f"(n={est['n_backfill']}), live era n={est['n_live']} "
                     f"disclosed; prices through page data-through date"),
        n_primary_cells=1,
        n_secondary_cells=15,
        result_hash=result_hash,
        note=("ORDER-2 staged activation run. Primary = E4 capped backfill "
              "envelope (1 cell). Secondary = E1/E2/E3 backfill envelopes (3) "
              "+ 4 naive CIs + 8 single-way cluster CIs; all-era sensitivity "
              "rerun disclosed, not counted as separate cells (same events). "
              f"Preview: docs/preview/smh_lens.html (unlinked). "
              f"result_hash over output/oie/smh_lens_run.json content."),
    ))
    reg.verify_chain()
    print(f"[registry] run recorded, line {line_hash[:16]}…, chain OK")

    # STEP 4 — render preview
    render_preview(proto, verdict, facts, anatomy, top, br, states, est,
                   es, line_hash[:16])

    # console report
    print(f"[admission] {verdict['label']}  N_eff={verdict['effective_issuers']}")
    e = est["backfill"]
    for k in ("event", "issuer", "etf", "capped"):
        r = e[k]
        print(f"[estimand] {k:>7}: mean={r['mean_pct']:+.2f}%  "
              f"naive{r['naive_ci']}  issuer{r['issuer_ci']}  "
              f"date{r['date_ci']}  env{r['envelope']}  [{r['badge']}]  "
              f"n={r['n_events']}/{r['n_issuers']}iss/{r['n_dates']}d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
