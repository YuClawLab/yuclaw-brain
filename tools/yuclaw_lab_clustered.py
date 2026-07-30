#!/usr/bin/env python3
"""
Lab clustered decile inference v1 (ORDER v5.1 Part A) — REGISTRY-FIRST.

Adds ticker-clustered inference to the Validation Lab's decile spread,
computed on per-signal-date k-day forward returns from track_record
(forward-OOS window only), and renders docs/preview/lab_clustered.html
beside the Lab's naive statistics using the lens reporting rule:
cluster CI is primary; naive shown beside it labeled naive.

Two deferred estimator-parameter decisions, LOCKED in this spec (D No.1):
  (1) G<8 UNDERPOWERED threshold RETAINED. Rationale: the wild-cluster
      (Rademacher) small-G remedy is computed beside the cluster CI; 8
      matches the smallest live lens; changing thresholds after results
      exist is forbidden by our own discipline.
  (2) Percentile CIs RETAINED for v1. Bootstrap-t is deferred: it needs
      studentization machinery we have not validated; revisit at v5.3
      under its own registered spec.

Estimator (pre-committed):
  Observations: (ticker, signal_date, return_kd) from track_record,
  is_backfill = false, return_kd not null. Dates with < 40 scored tickers
  are excluded (the Lab's standing inclusion rule). Per date, rank by
  total_score desc; top decile = first max(1, round(n*0.10)), bottom =
  last, ties by rank order (the Lab's _decile_members rule).
  Spread statistic at horizon k: mean over dates of
  (mean top-decile return_kd - mean bottom-decile return_kd).
  Inference:
   (a) ticker-clustered bootstrap: resample tickers with replacement
       (a ticker drawn m times contributes all its decile observations m
       times); per replicate, per-date decile means use only sampled
       tickers' rows within that date's ORIGINAL decile membership; a
       date drops out of a replicate if either side is empty. Percentile
       2.5/97.5, B=4000, seed 20260727.
   (b) wild-cluster bootstrap: Rademacher signs on centered per-ticker
       cluster contributions to the date-mean spread (small-G remedy).
   (c) naive i.i.d. date-resample percentile CI on the per-date spread
       series (the Lab's existing bootstrap style), labeled naive.
  Badges (locked): UNDERPOWERED if G < 8 distinct clustered tickers or
  < 10 dates; DESCRIPTIVE if the cluster CI includes 0; else PRELIMINARY.
  Primary endpoint: k=5 spread cluster CI, forward-OOS. All else secondary.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from v3.lab.cohort_engine import DSN, MIN_UNIVERSE_FOR_DECILES, DECILE_FRACTION

SEED = 20260727
B = 4000
HORIZONS = (1, 5, 20)
Z = 1.959964

REGISTRY_PATH = str(_REPO / "registry" / "protocols.jsonl")
OUT_HTML = _REPO / "docs" / "preview" / "lab_clustered.html"
OUT_JSON = _REPO / "output" / "oie" / "lab_clustered_run.json"

METHOD_SPEC = __doc__  # the docstring above IS the locked spec
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]

PROTOCOL_NAME = "Lab clustered decile inference v1"
PROTOCOL_PARAMS = {
    "window": "forward-OOS only (is_backfill = false)",
    "horizons": list(HORIZONS), "primary_horizon": 5,
    "decile_fraction": DECILE_FRACTION,
    "min_universe": MIN_UNIVERSE_FOR_DECILES,
    "cluster": "ticker", "B": B, "seed": SEED,
    "ci": "percentile 2.5/97.5 (bootstrap-t deferred to v5.3)",
    "underpowered_guard": "G < 8 clustered tickers or < 10 dates (retained)",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------- registry
def register_first(reg: Registry) -> dict:
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if (p := reg.get_protocol(pid)):
        print(f"[registry] protocol {pid} already LOCKED (idempotent rerun)")
        return p
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=(
            "Ticker-clustered bootstrap inference on the Lab decile spread, "
            "per-signal-date k-day forward returns, forward-OOS only. "
            "Cluster CI primary, wild-cluster (Rademacher) small-G remedy and "
            "naive date-resample CI beside. D-No.1 decisions locked: G<8 "
            "UNDERPOWERED retained; percentile CIs retained for v1 "
            "(bootstrap-t deferred to v5.3 under its own spec)."),
        primary_endpoint=(
            "ticker-clustered bootstrap 95% CI on the top-minus-bottom decile "
            "spread of return_5d (k=5), forward-OOS window only"),
        secondary_endpoints=[
            "spread cluster CIs at k=1 and k=20",
            "wild-cluster CIs at k=1/5/20 (small-G remedy, shown beside)",
            "naive i.i.d. date-resample CIs at k=1/5/20 (labeled naive)",
            "per-decile (top, bottom) ticker-clustered mean CIs at k=1/5/20",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — registered BEFORE computation")
    return reg.get_protocol(pid)


# ---------------------------------------------------------------- data
def load_decile_obs(k: int):
    """[(date_iso, side, ticker, ret)] for forward-OOS dates with >= 40 scored
    tickers; deciles per the Lab's ranking rule."""
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                f"SELECT signal_date, ticker, total_score, return_{k}d "
                f"FROM track_record WHERE is_backfill = false "
                f"AND return_{k}d IS NOT NULL ORDER BY signal_date")
            rows = cur.fetchall()
    by_date: dict = {}
    for d, tk, score, ret in rows:
        by_date.setdefault(d, []).append((tk, float(score), float(ret)))
    obs = []
    for d, day in sorted(by_date.items()):
        if len(day) < MIN_UNIVERSE_FOR_DECILES:
            continue
        ranked = sorted(day, key=lambda r: -r[1])
        n_dec = max(1, round(len(ranked) * DECILE_FRACTION))
        for tk, _, ret in ranked[:n_dec]:
            obs.append((d.isoformat(), "top", tk, ret))
        for tk, _, ret in ranked[-n_dec:]:
            obs.append((d.isoformat(), "bottom", tk, ret))
    return obs


# ---------------------------------------------------------------- estimator
def spread_stat(obs, ticker_mult: dict | None = None):
    """Mean over dates of (top mean - bottom mean); ticker_mult = resample
    multiplicities (None = all once). Returns (stat, n_dates_used)."""
    per_date: dict = {}
    for d, side, tk, ret in obs:
        m = 1 if ticker_mult is None else ticker_mult.get(tk, 0)
        if m == 0:
            continue
        agg = per_date.setdefault(d, {"top": [0.0, 0], "bottom": [0.0, 0]})
        agg[side][0] += ret * m
        agg[side][1] += m
    spreads = []
    for d, agg in per_date.items():
        if agg["top"][1] and agg["bottom"][1]:
            spreads.append(agg["top"][0] / agg["top"][1]
                           - agg["bottom"][0] / agg["bottom"][1])
    if not spreads:
        return None, 0
    return sum(spreads) / len(spreads), len(spreads)


def decile_mean(obs, side, ticker_mult: dict | None = None):
    """Mean over dates of the side's per-date mean (same replicate rule)."""
    per_date: dict = {}
    for d, s, tk, ret in obs:
        if s != side:
            continue
        m = 1 if ticker_mult is None else ticker_mult.get(tk, 0)
        if m == 0:
            continue
        agg = per_date.setdefault(d, [0.0, 0])
        agg[0] += ret * m
        agg[1] += m
    vals = [a / b for a, b in per_date.values() if b]
    return (sum(vals) / len(vals)) if vals else None


def run_horizon(k: int):
    obs = load_decile_obs(k)
    tickers = sorted({tk for _, _, tk, _ in obs})
    dates = sorted({d for d, _, _, _ in obs})
    stat, n_dates = spread_stat(obs)

    rng_c = random.Random(f"{SEED}:cluster:k{k}")
    reps_c = []
    for _ in range(B):
        mult: dict = {}
        for _ in tickers:
            t = tickers[rng_c.randrange(len(tickers))]
            mult[t] = mult.get(t, 0) + 1
        s, _n = spread_stat(obs, mult)
        if s is not None:
            reps_c.append(s)
    reps_c.sort()
    cluster_ci = (reps_c[int(0.025 * len(reps_c))],
                  reps_c[int(0.975 * len(reps_c)) - 1])

    # wild-cluster: Rademacher signs on centered per-ticker contributions to
    # the overall spread statistic. Contribution of ticker t = stat(with t) -
    # stat(without t) is expensive; use the standard linearized form: cluster
    # score = sum over t's observations of signed influence (ret - side/date
    # mean) aggregated per date. v1 implementation: per-ticker delete-one
    # influence on the spread statistic.
    base = stat
    influence = {}
    for t in tickers:
        mult = {tk: 1 for tk in tickers if tk != t}
        s, _n = spread_stat(obs, mult)
        influence[t] = (base - s) if s is not None else 0.0
    rng_w = random.Random(f"{SEED}:wild:k{k}")
    reps_w = []
    for _ in range(B):
        tot = sum(inf if rng_w.random() < 0.5 else -inf
                  for inf in influence.values())
        reps_w.append(base + tot)
    reps_w.sort()
    wild_ci = (reps_w[int(0.025 * B)], reps_w[int(0.975 * B) - 1])

    # naive: i.i.d. date resample of the per-date spread series
    per_date: dict = {}
    for d, side, tk, ret in obs:
        agg = per_date.setdefault(d, {"top": [], "bottom": []})
        agg[side].append(ret)
    spread_series = [sum(a["top"]) / len(a["top"]) - sum(a["bottom"]) / len(a["bottom"])
                     for a in per_date.values() if a["top"] and a["bottom"]]
    rng_n = random.Random(f"{SEED}:naive:k{k}")
    reps_n = []
    for _ in range(B):
        sample = [spread_series[rng_n.randrange(len(spread_series))]
                  for _ in spread_series]
        reps_n.append(sum(sample) / len(sample))
    reps_n.sort()
    naive_ci = (reps_n[int(0.025 * B)], reps_n[int(0.975 * B) - 1])

    # per-decile clustered means (secondary)
    per_decile = {}
    for side in ("top", "bottom"):
        mean_side = decile_mean(obs, side)
        rng_s = random.Random(f"{SEED}:side:{side}:k{k}")
        reps_s = []
        for _ in range(B):
            mult: dict = {}
            for _ in tickers:
                t = tickers[rng_s.randrange(len(tickers))]
                mult[t] = mult.get(t, 0) + 1
            v = decile_mean(obs, side, mult)
            if v is not None:
                reps_s.append(v)
        reps_s.sort()
        per_decile[side] = {
            "mean": mean_side,
            "cluster_ci": (reps_s[int(0.025 * len(reps_s))],
                           reps_s[int(0.975 * len(reps_s)) - 1]),
        }

    G = len(tickers)
    badge = ("UNDERPOWERED" if G < 8 or n_dates < 10 else
             "DESCRIPTIVE" if cluster_ci[0] <= 0.0 <= cluster_ci[1] else
             "PRELIMINARY")
    return {
        "k": k, "spread_mean": stat, "n_dates": n_dates, "n_obs": len(obs),
        "G_tickers": G, "cluster_ci": cluster_ci, "wild_ci": wild_ci,
        "naive_ci": naive_ci, "per_decile": per_decile, "badge": badge,
        "date_range": [dates[0], dates[-1]] if dates else None,
    }


# ---------------------------------------------------------------- render
def _pct(x):
    return f"{x*100:+.2f}%" if x is not None else "—"


def _ci(t):
    return f"({t[0]*100:+.2f}%, {t[1]*100:+.2f}%)"


def render(proto, results, run_line):
    built = utc_now()
    rows = []
    for k in HORIZONS:
        r = results[k]
        hl = " style='background:#1A2334'" if k == 5 else ""
        rows.append(
            f"<tr{hl}><td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace'>k={k}{' — PRIMARY' if k == 5 else ''}</td>"
            f"<td style='padding:7px 12px;color:#E2E8F0;font-family:JetBrains Mono,monospace;font-weight:700'>{_pct(r['spread_mean'])}</td>"
            f"<td style='padding:7px 12px;color:#4DD0E1;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['cluster_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['wild_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(r['naive_ci'])}</td>"
            f"<td style='padding:7px 12px;color:#718096;font-family:JetBrains Mono,monospace'>{r['n_dates']}d / {r['G_tickers']}t / {r['n_obs']}o</td>"
            f"<td style='padding:7px 12px;color:#A0AEC0;font-size:11px'>{escape(r['badge'])}</td></tr>")
        for side in ("top", "bottom"):
            pd = r["per_decile"][side]
            rows.append(
                f"<tr><td style='padding:5px 12px 5px 28px;color:#718096;font-size:11px'>{side} decile mean (secondary)</td>"
                f"<td style='padding:5px 12px;color:#A0AEC0;font-family:JetBrains Mono,monospace;font-size:11px'>{_pct(pd['mean'])}</td>"
                f"<td style='padding:5px 12px;color:#718096;font-family:JetBrains Mono,monospace;font-size:11px'>{_ci(pd['cluster_ci'])}</td>"
                f"<td colspan='4'></td></tr>")

    r5 = results[5]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PREVIEW — Lab clustered decile inference</title>
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
  </style>
</head>
<body>
  <div class="container">
    <div style="background:#2A1A1A;border:1px solid #FBA94B80;border-radius:8px;padding:12px 18px;margin-bottom:18px;font-size:12px;color:#FBA94B;font-weight:700">
      PREVIEW — real data, not yet part of the daily build. Unlinked staged page; public pages untouched.
    </div>
    <h1 style="font-size:24px;font-weight:800;color:#FFF;letter-spacing:-0.5px;margin-bottom:4px">Lab Decile Spread — Clustered Inference</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px">
      Registered protocol <code>{escape(proto['protocol_id'])}</code> ({escape(PROTOCOL_NAME)}) ·
      method <code>{escape(METHOD_HASH)}</code> · registry-first · built {escape(built)}
    </p>
    <div style="background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;color:#A0AEC0">
      <strong style="color:#FBA94B">Disclaimer —</strong> Hypothetical research illustration. Not investment
      advice, not performance advertising. Research classifications, not recommendations.
      Research &amp; education only.
    </div>

    <div class="panel">
      <div class="panel-title">Locked estimator-parameter decisions (D No.1)</div>
      <div class="panel-sub">versioned in this protocol's spec; methodology section staged for the v5.1 public flip</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.7">
        <strong style="color:#E2E8F0">1 · G&lt;8 UNDERPOWERED threshold retained.</strong> The wild-cluster
        (Rademacher) small-G remedy is computed beside every cluster CI; 8 matches the smallest live lens;
        changing thresholds after results exist is forbidden by our own discipline.<br>
        <strong style="color:#E2E8F0">2 · Percentile CIs retained for v1.</strong> Bootstrap-t is deferred —
        it needs studentization machinery not yet exercised in this codebase; revisit at v5.3 under its own registered spec.
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">Top-minus-bottom decile spread — forward-OOS · per-signal-date k-day returns</div>
      <div class="panel-sub">window {escape(r5['date_range'][0])} → {escape(r5['date_range'][1])} · deciles per the Lab's standing rule (10% of ≥40-ticker dates) · B={B}, seed {SEED} · reporting rule: cluster CI is primary; naive shown beside it labeled naive</div>
      <table>
        <thead><tr><th>Horizon</th><th>Mean spread</th><th>Ticker-cluster CI (primary)</th><th>Wild-cluster CI (small-G remedy)</th><th>Naive CI (comparison)</th><th>dates/tickers/obs</th><th>Badge</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:10px">
        Estimator note: the published Lab panel reports per-rebalance hold-to-next spreads; this preview uses
        per-signal-date k-day forward-return spreads because ticker identity is required for clustering —
        the two are stated side by side, never blended. Same tickers appear in deciles on many dates;
        the ticker-clustered CI absorbs that dependence, the naive date-resample CI does not.
        Percentile intervals; bootstrap-t deferred (decision 2 above).
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">Provenance</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.8">
        Protocol <code>{escape(proto['protocol_id'])}</code> locked {escape(proto['lock_date'])} ·
        primary endpoint: {escape(proto['primary_endpoint'])}<br>
        Run recorded: registry line <code>{escape(run_line)}</code> · chain verified at build time.
        Registered before computation on real data.
      </p>
    </div>
    <div style="text-align:center;padding:14px;color:#718096;font-size:11px">
      YUCLAW Lab clustered inference preview · built {escape(built)} · research &amp; education only
    </div>
  </div>
</body>
</html>
"""
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html)
    print(f"[preview] wrote {OUT_HTML} ({len(html)} bytes)")


def main() -> int:
    reg = Registry(REGISTRY_PATH)
    proto = register_first(reg)
    reg.assert_registered(proto["protocol_id"])

    results = {k: run_horizon(k) for k in HORIZONS}

    payload = {"protocol_id": proto["protocol_id"], "method_hash": METHOD_HASH,
               "built_utc": utc_now(), "results": results}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

    line = reg.record_run(Run(
        protocol_id=proto["protocol_id"],
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"forward-OOS {results[5]['date_range'][0]}.."
                     f"{results[5]['date_range'][1]}, "
                     f"{results[5]['n_dates']} dates, "
                     f"{results[5]['G_tickers']} clustered tickers"),
        n_primary_cells=1,
        n_secondary_cells=14,
        result_hash=result_hash,
        note=("ORDER v5.1 Part A activation. Primary = k=5 spread cluster CI. "
              "Secondary = k=1/k=20 cluster (2) + wild x3 + naive x3 + "
              "per-decile top/bottom cluster x3 horizons (6). Preview: "
              "docs/preview/lab_clustered.html (unlinked)."),
    ))
    reg.verify_chain()
    print(f"[registry] run recorded, line {line[:16]}…, chain OK")

    render(proto, results, line[:16])
    for k in HORIZONS:
        r = results[k]
        print(f"[k={k:>2}] spread={r['spread_mean']*100:+.2f}%  "
              f"cluster({r['cluster_ci'][0]*100:+.2f},{r['cluster_ci'][1]*100:+.2f})  "
              f"wild({r['wild_ci'][0]*100:+.2f},{r['wild_ci'][1]*100:+.2f})  "
              f"naive({r['naive_ci'][0]*100:+.2f},{r['naive_ci'][1]*100:+.2f})  "
              f"[{r['badge']}]  {r['n_dates']}d/{r['G_tickers']}t/{r['n_obs']}o")
    return 0


if __name__ == "__main__":
    sys.exit(main())
