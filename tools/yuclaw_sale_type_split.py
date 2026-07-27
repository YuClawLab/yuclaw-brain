#!/usr/bin/env python3
"""
SMH discretionary-split CAR v1 (ORDER sharper-hypothesis Part A) — REGISTRY-FIRST.

Question left behind by the taxonomy: MU's insider-sale mass is almost entirely
Rule 10b5-1 plan selling, while the sleeve's discretionary dollar mass lives
elsewhere. Does DISCRETIONARY selling behave differently from PLAN selling?

Class assignment (pre-committed, deterministic): each deduped INSIDER_SELL
event day (ticker, day) aggregates the S-transaction dollar mass of its
ingested filings that day (non-derivative S rows only; filing-level 10b5-1
checkbox; source = the Form-4 XML cache built by yuclaw_form4_taxonomy.py).
DISCRETIONARY if the non-plan share of that S mass exceeds 50%; PLAN
otherwise; days with zero parseable S mass are UNCLASSIFIED — excluded and
disclosed. The F/M-mechanical-only class is STRUCTURALLY EMPTY at the event
level: ingestion keeps P/S transaction codes only, so filings containing only
F/M/A rows never became events — reported as n=0 with this reason, not
silently dropped.

Estimator: E4 capped-ETF-weighted mean direction-aligned peer-model CAR at
tau=+20 per class (weights renormalized within class), backfill era primary
(matching the parent estimand, protocol 15052741ba2a); all-era sensitivity
disclosed. Inference per class via the registered multi-estimand machinery
(issuer- and date-cluster bootstrap CIs, conservative envelope, locked
badges). Discretionary-minus-plan difference: cluster bootstrap on the
difference (issuer and date resamples over the union event set; a replicate
missing either class is dropped and counted). Date-shuffle null per class
(N=1000, per-class observed day0 support, machinery of Falsification Battery
v1). B=4000, seed 20260727. Expect UNDERPOWERED at these n — reported plainly;
thin-but-honest beats pooled-but-confounded.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2

from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
from yuclaw_etf_lens import WeightedClusteredCAR
from yuclaw_falsification import TargetGrid

from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.etf_evidence import event_study, overlap_summary

SEED = 20260727
B = 4000
N_NULL = 1000
REGISTRY_PATH = str(_REPO / "registry" / "protocols.jsonl")
OUT_JSON = _REPO / "output" / "oie" / "sale_type_split.json"
CACHE = _REPO / "output" / "oie" / "form4_xml_cache.json"

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "SMH discretionary-split CAR v1"
PROTOCOL_PARAMS = {"lens": "SMH", "classes": ["discretionary", "plan", "fm_mechanical"],
                   "estimand": "E4 capped", "horizon_tau": 20, "B": B,
                   "n_null": N_NULL, "seed": SEED, "primary_era": "backfill"}


def register_first(reg):
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if (p := reg.get_protocol(pid)):
        print(f"[registry] protocol {pid} already LOCKED (idempotent rerun)")
        return p
    reg.register(Protocol(
        protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
        spec_summary=("E4 capped-ETF-weighted CAR at +20d for INSIDER_SELL "
                      "event days split discretionary vs Rule-10b5-1-plan by "
                      "S-transaction dollar-mass majority (filing-level "
                      "checkbox, XML-parsed); cluster envelopes; per-class "
                      "date-shuffle nulls; F/M-only class structurally empty "
                      "(P/S-only ingestion) — disclosed."),
        primary_endpoint=("E4 capped-ETF-weighted mean CAR at tau=+20d, "
                          "DISCRETIONARY-sale event days only, backfill era, "
                          "conservative envelope"),
        secondary_endpoints=[
            "plan-sale-only E4 (envelope)",
            "discretionary-minus-plan difference (issuer+date cluster CIs, envelope)",
            "date-shuffle null percentile per class (2 cells)",
            "F/M-mechanical-only class: structurally empty at event level (n=0, disclosed)",
            "all-era sensitivity rerun per class (2 cells)",
        ],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    ))
    reg.verify_chain()
    print(f"[registry] LOCKED protocol {pid} ({PROTOCOL_NAME}) "
          f"method_hash={METHOD_HASH} — registered BEFORE computation")
    return reg.get_protocol(pid)


def class_map(covered):
    """(ticker, day_iso) -> class, from ingested filings' S dollar mass."""
    cache = json.loads(CACHE.read_text())
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT ticker, event_time::date, source_url
                   FROM events WHERE event_status='accepted'
                     AND event_type='INSIDER_SELL' AND ticker = ANY(%s)""",
                (covered,))
            rows = cur.fetchall()
    urls_by_day: dict = {}
    for tk, d, u in rows:
        if u:
            urls_by_day.setdefault((tk, d.isoformat()), set()).add(u)
    out, unclassified = {}, 0
    for key, urls in urls_by_day.items():
        m_disc = m_plan = 0.0
        for u in urls:
            f = cache.get(u) or {}
            if "rows" not in f:
                continue
            s_mass = sum(abs(r["shares"] * r["price"]) for r in f["rows"]
                         if r["code"] == "S" and r["table"] == "nonDeriv")
            if f["plan_10b5_1"]:
                m_plan += s_mass
            else:
                m_disc += s_mass
        if m_disc + m_plan == 0:
            out[key] = "unclassified"
            unclassified += 1
        else:
            out[key] = ("discretionary"
                        if m_disc / (m_disc + m_plan) > 0.5 else "plan")
    return out, unclassified


def e4_stat(events, fund_w):
    """events: [(tk, date, car)] -> capped weighted mean."""
    wc = WeightedClusteredCAR(events, fund_w, B=1, seed=SEED)
    w = wc._weights(events, "capped")
    sw = sum(w)
    return sum(wi * c for wi, (_, _, c) in zip(w, events)) / sw if sw else None


def diff_boot(ev_d, ev_p, fund_w, cluster_idx, tag):
    """Cluster bootstrap on E4(disc) - E4(plan). cluster_idx: 0=ticker, 1=date."""
    union = ev_d + ev_p
    keys = sorted({e[cluster_idx] for e in union})
    byk_d, byk_p = {}, {}
    for e in ev_d:
        byk_d.setdefault(e[cluster_idx], []).append(e)
    for e in ev_p:
        byk_p.setdefault(e[cluster_idx], []).append(e)
    rng = random.Random(f"{SEED}:diff:{tag}")
    reps, dropped = [], 0
    for _ in range(B):
        sd, sp = [], []
        for _ in keys:
            k = keys[rng.randrange(len(keys))]
            sd += byk_d.get(k, [])
            sp += byk_p.get(k, [])
        if not sd or not sp:
            dropped += 1
            continue
        a, b = e4_stat(sd, fund_w), e4_stat(sp, fund_w)
        if a is not None and b is not None:
            reps.append(a - b)
    reps.sort()
    return ((reps[int(0.025 * len(reps))], reps[int(0.975 * len(reps)) - 1]),
            dropped)


def shuffle_null(events, grid, fund_w, tag):
    lo = min(i for _t, i, _d, _s in events)
    hi = max(i for _t, i, _d, _s in events)
    elig = {tk: grid.eligible(tk, lo, hi)
            for tk in sorted({t for t, *_ in events})}
    ev_real = [(t, str(i), s) for t, i, _d, s in events]
    real = e4_stat(ev_real, fund_w)
    rng = random.Random(f"{SEED}:classshuffle:{tag}")
    nulls = []
    for _ in range(N_NULL):
        ev = []
        for tk, _i, d, _s in events:
            pool = elig[tk]
            ev.append((tk, "x", grid.car20(tk, pool[rng.randrange(len(pool))]) * d))
        nulls.append(e4_stat(ev, fund_w))
    pct = sum(1 for v in nulls if v < real) / N_NULL
    m = sum(nulls) / len(nulls)
    sd = (sum((x - m) ** 2 for x in nulls) / (len(nulls) - 1)) ** 0.5
    return {"percentile_in_null": round(pct, 3),
            "null": {"mean": round(m, 3), "sd": round(sd, 3)}}


def main() -> int:
    reg = Registry(REGISTRY_PATH)
    proto = register_first(reg)
    reg.assert_registered(proto["protocol_id"])

    ov = overlap_summary()
    covered, fund_w = ov["covered"], ov["weights_covered"]
    cmap, n_uncls_days = class_map(covered)

    es = event_study()
    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    grid = TargetGrid(covered, prices, trade_dates)

    def build(era_filter):
        by_class = {"discretionary": [], "plan": [], "unclassified": []}
        for r in es["per_event_rows"]:
            if r["type"] != "INSIDER_SELL":
                continue
            if era_filter and r["era"] != era_filter:
                continue
            cls = cmap.get((r["ticker"], r["date"]), "unclassified")
            ev_date = date.fromisoformat(r["date"])
            day0 = next((d for d in trade_dates if d >= ev_date), None)
            if day0 is None:
                continue
            by_class[cls].append((r["ticker"], idx[day0], r["direction"],
                                  r["car20_peer_aligned_pct"]))
        return by_class

    def run_class(events, tag):
        if not events:
            return None
        ev = [(t, str(i), s) for t, i, _d, s in events]
        res = WeightedClusteredCAR(ev, fund_w, B=B, seed=SEED).run("capped")
        out = vars(res)
        out["shuffle"] = shuffle_null(events, grid, fund_w, tag)
        return out

    results = {}
    for era, tag in (("backfill", "bf"), (None, "all")):
        bc = build(era)
        era_res = {
            "n_discretionary": len(bc["discretionary"]),
            "n_plan": len(bc["plan"]),
            "n_unclassified": len(bc["unclassified"]),
            "discretionary": run_class(bc["discretionary"], f"disc:{tag}"),
            "plan": run_class(bc["plan"], f"plan:{tag}"),
        }
        if bc["discretionary"] and bc["plan"]:
            d_real = e4_stat([(t, str(i), s) for t, i, _d, s in bc["discretionary"]], fund_w)
            p_real = e4_stat([(t, str(i), s) for t, i, _d, s in bc["plan"]], fund_w)
            ci_i, drop_i = diff_boot(
                [(t, str(i), s) for t, i, _d, s in bc["discretionary"]],
                [(t, str(i), s) for t, i, _d, s in bc["plan"]],
                fund_w, 0, f"iss:{tag}")
            ci_d, drop_d = diff_boot(
                [(t, str(i), s) for t, i, _d, s in bc["discretionary"]],
                [(t, str(i), s) for t, i, _d, s in bc["plan"]],
                fund_w, 1, f"date:{tag}")
            era_res["difference"] = {
                "value": round(d_real - p_real, 3),
                "issuer_ci": [round(x, 2) for x in ci_i],
                "date_ci": [round(x, 2) for x in ci_d],
                "envelope": [round(min(ci_i[0], ci_d[0]), 2),
                             round(max(ci_i[1], ci_d[1]), 2)],
                "replicates_dropped": {"issuer": drop_i, "date": drop_d},
            }
        results["backfill" if era else "all_era"] = era_res

    payload = {
        "protocol_id": proto["protocol_id"], "method_hash": METHOD_HASH,
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "unclassified_event_days_total": n_uncls_days,
        "fm_mechanical": {"n": 0, "reason": ("structurally empty at event "
                          "level: ingestion keeps P/S codes only, so F/M/A-"
                          "only filings never became events")},
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]

    line = reg.record_run(Run(
        protocol_id=proto["protocol_id"],
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window=(f"backfill era primary (disc n="
                     f"{results['backfill']['n_discretionary']}, plan n="
                     f"{results['backfill']['n_plan']}); all-era sensitivity"),
        n_primary_cells=1, n_secondary_cells=7, result_hash=result_hash,
        note=("Sharper-hypothesis Part A. Primary = discretionary E4 envelope "
              "(backfill). Secondary = plan E4 + diff + 2 class shuffles + "
              "F/M empty cell + 2 all-era sensitivities."),
    ))
    reg.verify_chain()
    print(f"[registry] run recorded, line {line[:16]}…, chain OK")

    for era, r in results.items():
        print(f"--- {era}: disc n={r['n_discretionary']} plan n={r['n_plan']} "
              f"uncls n={r['n_unclassified']}")
        for cls in ("discretionary", "plan"):
            c = r[cls]
            if c:
                print(f"  {cls:>13}: E4={c['mean_pct']:+.2f}%  env{c['envelope']}  "
                      f"[{c['badge']}]  shuffle-pct={c['shuffle']['percentile_in_null']:.3f} "
                      f"(null {c['shuffle']['null']['mean']:+.2f}±{c['shuffle']['null']['sd']:.2f})")
        if "difference" in r:
            d = r["difference"]
            print(f"     disc-plan: {d['value']:+.2f}pp  env({d['envelope'][0]:+.2f},{d['envelope'][1]:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
