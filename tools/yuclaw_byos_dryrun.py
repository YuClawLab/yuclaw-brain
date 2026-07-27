#!/usr/bin/env python3
"""
Concierge BYOS dry-run v2 (commercial lane; internal proof, no revenue).

Simulates the CAD-5,000 pilot deliverable end-to-end on SYNTHETIC client
input, timing every stage:

  1. Synthetic client CSVs — a basket (ticker,weight) AND a point-in-time
     signal file (date,ticker,signal_value) — clearly marked SYNTHETIC-CLIENT.
  2. Intake schema validation (yuclaw_client_intake) — friendly errors.
  3. CLIENT-SIGNAL decomposition suite (yuclaw_client_signal_lab): IC + CIs,
     quantile monotonicity, churn, horizon decay, placebo on THEIR signal.
  4. Basket estimands (E1-E4) + falsification battery.
  5. Reproduction bundle: input hashes, protocol records, seed, environment
     manifest, standalone rerun script -> admission re-check with
     reproduction_bundle=True.
  6. Deliverable memo: markdown + WeasyPrint PDF (house style, identity band,
     evidence-ledger table, non-canonical banner prominent).

All client-namespace: Registry(..., namespace='client') (guarded in code);
everything lands in output/byos_dryrun/ (gitignored). Nothing public,
nothing canonical, nothing committed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import LensFacts, WeightedClusteredCAR, admit
from yuclaw_falsification import TargetGrid, battery
from yuclaw_client_signal_lab import run_suite

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import EST_MIN

OUT_DIR = _REPO / "output" / "byos_dryrun"
BUNDLE = OUT_DIR / "bundle"
SEED = 20260727

CLIENT_SPEC = """CLIENT-LENS multi-estimand CAR (user_defined=true,
non_canonical=true). Same estimator family as canonical protocol 15052741ba2a
(E1-E4 weighted direction-aligned peer-model CAR at tau=+20, issuer/date
cluster envelopes, locked badges) applied to a user-supplied basket. The peer
model is the client basket itself (EW of the other members). Falsification:
date-shuffle / sign-flip / placebo per Falsification Battery v1 machinery,
N=1000. Not part of the canonical public record; results are research
classifications for the submitting user only."""


def now():
    return time.monotonic()


def synth_inputs(rng):
    uni = json.loads((_REPO / "v3" / "universe.json").read_text())["equities"]
    picks = sorted(rng.sample(uni, 10))
    weights = [rng.uniform(3, 18) for _ in picks]
    tot = sum(weights)
    weights = [round(w / tot * 100, 2) for w in weights]
    basket_csv = OUT_DIR / "client_input.csv"
    with basket_csv.open("w", newline="") as f:
        f.write("# SYNTHETIC-CLIENT — generated dry-run input; no real client\n")
        w = csv.writer(f)
        w.writerow(["ticker", "weight_pct", "as_of", "client_note"])
        for tk, wt in zip(picks, weights):
            w.writerow([tk, wt, "2026-07-24", "synthetic thesis placeholder"])
    # point-in-time signal file: weekly dates, random signal (an honest null)
    sig_csv = OUT_DIR / "client_signals.csv"
    d0, d1 = date(2026, 5, 18), date(2026, 7, 15)
    with sig_csv.open("w", newline="") as f:
        f.write("# SYNTHETIC-CLIENT — random synthetic signal; no real client\n")
        w = csv.writer(f)
        w.writerow(["date", "ticker", "signal_value"])
        d = d0
        while d <= d1:
            if d.weekday() < 5:
                for tk in picks:
                    w.writerow([d.isoformat(), tk, round(rng.gauss(0, 1), 4)])
            d += timedelta(days=1 if d.weekday() < 4 else 3)
    return picks, weights, basket_csv, sig_csv


def env_manifest():
    def pkg_ver(name):
        try:
            mod = __import__(name)
            return getattr(mod, "__version__", "unknown")
        except Exception:
            return "absent"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                            capture_output=True, text=True).stdout.strip()
    return {"python": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": commit,
            "packages": {n: pkg_ver(n) for n in
                         ("psycopg2", "weasyprint")},
            "seed": SEED}


def build_bundle(basket_csv, sig_csv, results, client_reg_path):
    BUNDLE.mkdir(parents=True, exist_ok=True)
    for src in (basket_csv, sig_csv):
        (BUNDLE / src.name).write_bytes(src.read_bytes())
    manifest = {
        "input_sha256": {src.name: hashlib.sha256(src.read_bytes()).hexdigest()
                         for src in (basket_csv, sig_csv)},
        "environment": env_manifest(),
        "client_chain_copy": "registry_client.jsonl",
        "result_hashes": results,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    (BUNDLE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (BUNDLE / "registry_client.jsonl").write_bytes(
        Path(client_reg_path).read_bytes())
    (BUNDLE / "rerun.sh").write_text(f"""#!/bin/bash
# Standalone reproduction — reruns the deliverable's numbers from this bundle.
# Requires: the YUCLAW repo + its Postgres price/event store on this box.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[rerun] verifying input hashes against manifest.json"
python3 - "$HERE" << 'PYEOF'
import hashlib, json, sys
here = sys.argv[1]
m = json.load(open(f"{{here}}/manifest.json"))
for name, want in m["input_sha256"].items():
    got = hashlib.sha256(open(f"{{here}}/{{name}}", "rb").read()).hexdigest()
    assert got == want, f"hash mismatch: {{name}}"
    print(f"  OK {{name}}")
PYEOF

echo "[rerun] recomputing client-signal suite"
python3 "{_REPO}/tools/yuclaw_client_signal_lab.py" \\
    "$HERE/client_signals.csv" "$HERE/rerun_out"

echo "[rerun] comparing against the delivered suite"
python3 - "$HERE" << 'PYEOF'
import json, sys
here = sys.argv[1]
a = json.load(open("{OUT_DIR}/signal_suite.json"))
b = json.load(open(f"{{here}}/rerun_out/signal_suite.json"))
for side in (a, b):
    side.pop("built_utc", None)
    side.pop("result_hash", None)
match = (json.dumps(a, sort_keys=True, default=str)
         == json.dumps(b, sort_keys=True, default=str))
print("REPRODUCTION " + ("OK — suite numbers identical" if match
                         else "MISMATCH"))
raise SystemExit(0 if match else 1)
PYEOF
""")
    (BUNDLE / "rerun.sh").chmod(0o755)
    return manifest


PDF_CSS = """
@page { size: A4; margin: 22mm 18mm; @bottom-center {
  content: "YUCLAW BYOS pilot dry-run · research & education only · page " counter(page);
  font-size: 8pt; color: #666; } }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; color: #111;
       line-height: 1.5; }
.band { background: #0B0E14; color: #fff; padding: 14px 18px;
        border-left: 6px solid #00C853; margin-bottom: 14px; }
.band .t { font-size: 16pt; font-weight: 800; letter-spacing: -0.5px; }
.band .s { font-size: 9pt; color: #9adbb4; font-family: monospace; }
.banner { background: #FFF3E0; border: 2px solid #E65100; color: #7f2d00;
          padding: 10px 14px; font-weight: 700; font-size: 10pt;
          margin-bottom: 14px; }
h2 { font-size: 12pt; border-bottom: 1px solid #ccc; padding-bottom: 3px;
     margin: 18px 0 8px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; }
th { text-align: left; font-size: 8pt; text-transform: uppercase;
     color: #555; border-bottom: 1.5px solid #333; padding: 4px 8px; }
td { font-size: 9.5pt; border-bottom: 0.5px solid #ddd; padding: 4px 8px;
     font-family: monospace; }
.small { font-size: 8.5pt; color: #555; }
"""


def render_pdf(md_path: Path, pdf_path: Path, context: dict) -> bool:
    try:
        from weasyprint import HTML
    except Exception as exc:                     # noqa: BLE001
        print(f"[byos] PDF skipped — weasyprint unavailable: {exc}")
        return False
    est, fals, suite = (context["estimands"], context["falsification"],
                        context["suite"])
    ic = suite["ic_primary_k5"] or {}
    q = suite["quantiles"]
    ledger_rows = "".join(
        f"<tr><td>{lbl}</td><td>{est[k]['mean_pct']:+.2f}%</td>"
        f"<td>({est[k]['envelope'][0]:+.2f}, {est[k]['envelope'][1]:+.2f})</td>"
        f"<td>{est[k]['badge']}</td></tr>"
        for k, lbl in (("event", "E1 event-weighted"),
                       ("issuer", "E2 issuer-weighted"),
                       ("etf", "E3 basket-weighted"),
                       ("capped", "E4 capped (primary)")))
    decay_rows = "".join(
        f"<tr><td>k={h['k']}</td><td>{h['mean_ic']:+.4f}</td>"
        f"<td>({h['ci'][0]:+.4f}, {h['ci'][1]:+.4f})</td><td>{h['badge']}</td></tr>"
        for h in suite["horizon_decay"] if h)
    html = f"""
<div class="band"><div class="t">YUCLAW · Client-Defined Lens — Research Memo</div>
<div class="s">protocol {context['pid']} · run {context['run_line']} ·
result {context['result_hash']} · {context['built']}</div></div>
<div class="banner">USER-DEFINED RESEARCH LENS — NOT PART OF THE CANONICAL
PUBLIC RECORD. SYNTHETIC-CLIENT dry-run. Research classifications, not
recommendations. Not investment advice.</div>
<h2>1 · Admission</h2>
<p>Verdict: <b>{context['verdict']['label']}</b> · effective issuers
{context['verdict']['effective_issuers']} · reproduction bundle: included
(bundle/manifest.json, rerun.sh).</p>
<h2>2 · Client signal — validation suite (primary: IC at k=5)</h2>
<p>IC(k=5) = <b>{ic.get('mean_ic', '—')}</b>, CI ({ic.get('ci', ('—', '—'))[0]},
{ic.get('ci', ('—', '—'))[1]}), {ic.get('days', '—')} days
[{ic.get('badge', '—')}]. Monotonicity {q['monotonicity_spearman']:+.3f},
top-minus-bottom {q['top_minus_bottom_pct']}%, adjacent ordering
{q['adjacent_ordering']}. Placebo percentile
{suite['placebo']['percentile_in_null']} (two-sided extremity). Churn
rank-autocorr {suite['churn'].get('rank_autocorr_1d', '—')}.</p>
<table><tr><th>Horizon</th><th>Mean IC</th><th>Block-bootstrap CI</th>
<th>Badge</th></tr>{decay_rows}</table>
<h2>3 · Basket evidence ledger — CAR at +20d</h2>
<table><tr><th>Estimand</th><th>Mean</th><th>Envelope</th><th>Badge</th></tr>
{ledger_rows}</table>
<p class="small">Falsification: date-shuffle percentile
{fals['date_shuffle']['percentile_in_null']}; sign-flip
{fals['sign_flip']['percentile_in_null']}; placebo −20d
{fals['placebo_minus20d']['value_pct']}%. Mid-range percentiles mean the
value is unremarkable within its null.</p>
<h2>4 · Coverage</h2>
<p class="small">Covered tickers: {', '.join(context['covered'])}.
Out-of-universe exclusions: {context['excluded'] or 'none'}.</p>
<h2>5 · Limitations</h2>
<p class="small">Peer model is the client basket itself; UNDERPOWERED cells
cannot support standalone inference; synthetic input throughout — this is an
internal dry-run artifact prepared for process validation only.</p>
"""
    HTML(string=f"<style>{PDF_CSS}</style>{html}").write_pdf(str(pdf_path))
    return True


def main() -> int:
    t0 = now()
    stamps = {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    picks, weights, basket_csv, sig_csv = synth_inputs(rng)
    stamps["1_inputs"] = now() - t0
    print(f"[byos] synthetic basket: {picks}")

    # ---- 2+3. intake + client-signal suite (registry-first inside) ---------
    suite_res = run_suite(sig_csv, OUT_DIR)
    stamps["3_signal_suite"] = now() - t0
    ic = suite_res["suite"]["ic_primary_k5"]
    print(f"[byos] signal suite: IC(k=5)={ic['mean_ic']:+.4f} "
          f"CI{ic['ci']} [{ic['badge']}] · placebo "
          f"{suite_res['suite']['placebo']['percentile_in_null']}")

    # ---- 4. basket estimands + falsification --------------------------------
    reg = Registry(str(OUT_DIR / "registry_client.jsonl"), namespace="client")
    params = {"user_defined": True, "non_canonical": True,
              "basket": picks, "weights": weights, "seed": SEED}
    pid = protocol_id(CLIENT_SPEC, params)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid,
            name="CLIENT-LENS synthetic pilot v1 [user_defined, non_canonical]",
            method_hash=hashlib.sha256(CLIENT_SPEC.encode()).hexdigest()[:16],
            spec_summary=CLIENT_SPEC.replace("\n", " "),
            primary_endpoint=("E4 capped-weighted mean CAR at +20d on the "
                              "client basket (conservative envelope)"),
            secondary_endpoints=["E1/E2/E3 envelopes",
                                 "falsification battery (3 tests)"],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
    reg.verify_chain()
    reg.assert_registered(pid)

    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    grid = TargetGrid(picks, prices, trade_dates)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, direction, event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND direction <> 0""", (picks,))
            evs = cur.fetchall()
    events = []
    for tk, d, ev_date in evs:
        day0 = next((dd for dd in trade_dates if dd >= ev_date), None)
        if day0 is None:
            continue
        v = grid.car20(tk, idx[day0])
        if v is not None:
            events.append((tk, idx[day0], int(d), v * int(d)))
    fund_w = dict(zip(picks, weights))
    ev4 = [(t, str(i), s) for t, i, _d, s in events]
    est = {k: vars(v) for k, v in
           WeightedClusteredCAR(ev4, fund_w, B=4000, seed=SEED).run_all().items()}
    fals = battery("CLIENT-SYNTH", events, grid, "capped", fund_w)
    stamps["4_estimands_falsification"] = now() - t0

    # ---- 5. reproduction bundle + re-admission ------------------------------
    results_hashes = {"signal_suite": suite_res["result_hash"]}
    manifest = build_bundle(basket_csv, sig_csv, results_hashes,
                            OUT_DIR / "registry_client.jsonl")
    n_priced = sum(1 for t in picks if len(prices.get(t, {})) >= EST_MIN)
    facts = LensFacts(
        ticker="CLIENT-SYNTH", holdings_source="SYNTHETIC-CLIENT CSV upload",
        holdings_date="2026-07-24", covered_issuers=len(picks),
        covered_weight_pct=100.0, covered_weights=weights,
        price_coverage_pct=round(100 * n_priced / len(picks), 1),
        substrate_disclosed=True, reproduction_bundle=True,
        live_protocol_registered=True)
    verdict = admit(facts)
    stamps["5_bundle_admission"] = now() - t0
    print(f"[byos] re-admission with reproduction bundle: {verdict['label']} "
          f"N_eff={verdict['effective_issuers']}")

    # ---- 6. memo (md + pdf) --------------------------------------------------
    results = {"facts": vars(facts), "verdict": verdict, "estimands": est,
               "falsification": fals, "signal_suite": suite_res}
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2,
                                                     default=str))
    result_hash = hashlib.sha256(
        json.dumps(results, sort_keys=True, default=str).encode()).hexdigest()[:16]
    line = reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=f"client basket events through {trade_dates[-1].isoformat()}",
        n_primary_cells=1, n_secondary_cells=6, result_hash=result_hash,
        note="BYOS dry-run v2 deliverable (synthetic client; bundle included)."))
    reg.verify_chain()

    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    e4, ds = est["capped"], fals["date_shuffle"]
    q = suite_res["suite"]["quantiles"]
    memo = "\n".join([
        "# Research Memo — Client-Defined Lens (PILOT DRY-RUN v2)", "",
        "> **User-defined research lens — not part of the canonical public "
        "record.** SYNTHETIC-CLIENT input; internal dry-run artifact. "
        "Research classifications, not recommendations; not investment advice.", "",
        f"- Client chain: lens protocol `{pid}` + signal protocol "
        f"`{suite_res['protocol_id']}` · run line `{line[:16]}` · result hash "
        f"`{result_hash}`",
        f"- Reproduction bundle: `bundle/` (inputs + hashes + environment + "
        f"rerun.sh); admission now passes the bundle requirement.", "",
        "## 1 · Admission",
        f"**{verdict['label']}** · N_eff {verdict['effective_issuers']} · "
        f"reasons: {verdict.get('reasons') or 'none'}", "",
        "## 2 · Client signal — validation suite",
        f"IC(k=5) {ic['mean_ic']:+.4f} CI {ic['ci']} over {ic['days']} days "
        f"[{ic['badge']}]; monotonicity {q['monotonicity_spearman']:+.3f}; "
        f"T-B {q['top_minus_bottom_pct']}%; placebo percentile "
        f"{suite_res['suite']['placebo']['percentile_in_null']}; churn "
        f"{suite_res['suite']['churn']}", "",
        "## 3 · Basket estimands (+20d)",
        f"E4 capped {e4['mean_pct']:+.2f}% env({e4['envelope'][0]:+.2f}, "
        f"{e4['envelope'][1]:+.2f}) [{e4['badge']}]; falsification: shuffle "
        f"{ds['percentile_in_null']}, sign-flip "
        f"{fals['sign_flip']['percentile_in_null']}, placebo "
        f"{fals['placebo_minus20d']['value_pct']}%", "",
        f"Generated {built} · deterministic template v2",
    ])
    memo += (f"\n---\nMemo hash: `{hashlib.sha256(memo.encode()).hexdigest()[:16]}`\n")
    (OUT_DIR / "CLIENT_MEMO.md").write_text(memo)
    pdf_ok = render_pdf(OUT_DIR / "CLIENT_MEMO.md", OUT_DIR / "CLIENT_MEMO.pdf",
                        {"pid": pid, "run_line": line[:16],
                         "result_hash": result_hash, "built": built,
                         "verdict": verdict, "estimands": est,
                         "falsification": fals, "suite": suite_res["suite"],
                         "covered": suite_res["coverage"]["covered_tickers"],
                         "excluded": suite_res["coverage"]["excluded_out_of_universe"]})
    stamps["6_memo_pdf"] = now() - t0

    print("[byos] stage wall-clock (cumulative seconds):")
    for k, v in stamps.items():
        print(f"    {k:>26}: {v:7.1f}s")
    print(f"[byos] TOTAL {stamps['6_memo_pdf']:.1f}s · PDF={'yes' if pdf_ok else 'NO'} "
          f"· bundle files: {sorted(p.name for p in BUNDLE.iterdir())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
