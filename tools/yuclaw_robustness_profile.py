#!/usr/bin/env python3
"""
Robustness Profile v1 (Fields-review build Part 3) — REGISTRY-FIRST.
Question: where does a registered result hold, and where does it break?

METHOD_SPEC (locked; the context grid below is pre-declared and enumerated
verbatim; own-data only):

  TARGET 1 (primary): the SMH E4 capped-ETF-weighted mean direction-aligned
  peer-model CAR (registered estimand of protocol 15052741ba2a). Base cell:
  backfill era, k=20. Grid cells:
    horizons   — k in {5, 10, 20} backfill era; k=60 backfill era only
    trend      — SPY trailing-120-trading-day cumulative return >= 0 / < 0
                 at the event's day 0 (backfill era, k=20)
    volatility — SPY trailing-20d realized vol above / at-or-below the
                 backfill-era median, FROZEN at registration:
                 median = 0.008570 daily (57 backfill-era days)
    era        — backfill k=20 (the base) / live k=20; live cells render
                 only where the arm meets the standing floors (>=10 events,
                 >=8 issuers), else UNDERPOWERED
  TARGET 2 (secondary): the Lab clustered decile spread (protocol
  36d019b175c8 estimator: per-signal-date k-day top-minus-bottom spread,
  forward-OOS). Cells: k in {1, 5, 20}; trend and volatility splits by
  signal date using the same definitions and the same frozen median.

  Per cell: estimate + cluster bootstrap percentile CI (issuer clusters for
  target 1, ticker clusters for target 2; B=2000, seed 20260730) + locked
  badge (UNDERPOWERED if < 8 clusters or < 10 observations; DESCRIPTIVE if
  the CI includes 0; else PRELIMINARY). Summary block per target,
  descriptive language only: "sign held in X/Y computed cells · CI excluded
  zero in Z/Y · breaks in: [cells with sign opposite the base] ·
  UNDERPOWERED cells: [list]". Every cell is ledger-counted; the rendered
  panel prints the registry's expected-false-positives line. Edits =>
  supersession.

Primary endpoint: sign-coherence fraction (share of computed cells whose
estimate has the base cell's sign) across the pre-declared grid for the
SMH E4 capped estimand.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

SEED = 20260730
B = 2000
VOL_MEDIAN_FROZEN = 0.008570
BACKFILL_LO, BACKFILL_HI = date(2026, 2, 18), date(2026, 5, 15)

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Robustness Profile v1"
PROTOCOL_PARAMS = {"vol_median_frozen": VOL_MEDIAN_FROZEN, "B": B,
                   "seed": SEED, "targets": ["SMH-E4", "Lab-spread"],
                   "horizons_t1": [5, 10, 20, 60], "horizons_t2": [1, 5, 20]}
OUT_JSON = _REPO / "output" / "oie" / "robustness_profile.json"


def pct_ci(reps):
    reps = sorted(reps)
    return (reps[int(0.025 * len(reps))], reps[int(0.975 * len(reps)) - 1])


def cell_eval(obs, stat_fn, cluster_of, tag):
    """obs: list of observations; stat_fn(list)->float|None;
    cluster_of(o)->cluster id. Returns cell dict or None if empty."""
    if not obs:
        return None
    est = stat_fn(obs)
    if est is None:
        return None
    by = {}
    for o in obs:
        by.setdefault(cluster_of(o), []).append(o)
    G = len(by)
    keys = sorted(by)
    rng = random.Random(f"{SEED}:{tag}")
    reps = []
    for _ in range(B):
        s = []
        for _ in keys:
            s += by[keys[rng.randrange(len(keys))]]
        v = stat_fn(s)
        if v is not None:
            reps.append(v)
    ci = pct_ci(reps)
    badge = ("UNDERPOWERED" if G < 8 or len(obs) < 10 else
             "DESCRIPTIVE" if ci[0] <= 0.0 <= ci[1] else "PRELIMINARY")
    return {"estimate": round(est, 3), "ci": [round(ci[0], 2), round(ci[1], 2)],
            "n": len(obs), "G": G, "badge": badge}


def summarize(cells, base_name):
    base = cells.get(base_name)
    base_sign = (base["estimate"] > 0) - (base["estimate"] < 0) if base else 0
    computed = {k: v for k, v in cells.items() if v is not None}
    held = [k for k, v in computed.items()
            if ((v["estimate"] > 0) - (v["estimate"] < 0)) == base_sign
            and base_sign != 0]
    excl = [k for k, v in computed.items()
            if not (v["ci"][0] <= 0.0 <= v["ci"][1])]
    breaks = [k for k, v in computed.items()
              if base_sign != 0 and v["estimate"] != 0
              and ((v["estimate"] > 0) - (v["estimate"] < 0)) != base_sign]
    under = [k for k, v in computed.items() if v["badge"] == "UNDERPOWERED"]
    empty = [k for k, v in cells.items() if v is None]
    return {"base_cell": base_name, "base_sign": base_sign,
            "n_computed": len(computed),
            "sign_held": len(held),
            "coherence_fraction": round(len(held) / len(computed), 3) if computed else None,
            "ci_excluded_zero": len(excl), "breaks": sorted(breaks),
            "underpowered": sorted(under), "empty": sorted(empty)}


# ------------------------------------------------------------ self-tests
def _selftest():
    rng = random.Random(3)
    # synthetic: 2 contexts x 30 obs, cluster ids spread
    def mk(mean_a, mean_b):
        a = [(f"C{i%10}", "ctxA", mean_a + rng.gauss(0, 0.5)) for i in range(30)]
        b = [(f"C{i%10}", "ctxB", mean_b + rng.gauss(0, 0.5)) for i in range(30)]
        return a + b
    stat = lambda obs: sum(v for _c, _x, v in obs) / len(obs)
    clus = lambda o: o[0]
    # T1 uniformly stable -> full coherence
    obs = mk(2.0, 2.0)
    cells = {"base": cell_eval(obs, stat, clus, "t1base"),
             "ctxA": cell_eval([o for o in obs if o[1] == "ctxA"], stat, clus, "t1a"),
             "ctxB": cell_eval([o for o in obs if o[1] == "ctxB"], stat, clus, "t1b")}
    s = summarize(cells, "base")
    assert s["coherence_fraction"] == 1.0 and not s["breaks"], s
    # T2 regime-flipped -> break detected in the correct cell. The flipped
    # arm is the minority so the pooled base keeps a determined (positive)
    # sign; the break must localize to ctxB and only ctxB.
    obs2 = [(f"C{i%10}", "ctxA", 2.0 + rng.gauss(0, 0.5)) for i in range(45)] \
         + [(f"C{i%10}", "ctxB", -2.0 + rng.gauss(0, 0.5)) for i in range(15)]
    cells2 = {"base": cell_eval(obs2, stat, clus, "t2base"),
              "ctxA": cell_eval([o for o in obs2 if o[1] == "ctxA"], stat, clus, "t2a"),
              "ctxB": cell_eval([o for o in obs2 if o[1] == "ctxB"], stat, clus, "t2b")}
    s2 = summarize(cells2, "base")
    assert "ctxB" in s2["breaks"] and "ctxA" not in s2["breaks"], s2
    # T3 empty-cell handling
    cells3 = dict(cells2, empty_ctx=None)
    s3 = summarize(cells3, "base")
    assert s3["empty"] == ["empty_ctx"]
    # T4 determinism
    assert cell_eval(obs2, stat, clus, "t2base") == cells2["base"]
    print("[OK] T1 stable->coherent · T2 flip->break located · T3 empty cell "
          "· T4 determinism")


# ------------------------------------------------------------ real targets
def spy_context(prices, td):
    spy = prices["SPY"]
    rets, prev = {}, None
    for d in td:
        p = spy.get(d)
        if p is not None and prev not in (None, 0):
            rets[d] = p / prev - 1
        if p is not None:
            prev = p
    idx = {d: i for i, d in enumerate(td)}

    def trend_pos(i0):
        if i0 < 121:
            return None
        p0, p1 = spy.get(td[i0 - 121]), spy.get(td[i0 - 1])
        if not p0 or not p1:
            return None
        return p1 / p0 - 1 >= 0

    def vol_high(i0):
        if i0 < 21:
            return None
        w = [rets.get(td[j]) for j in range(i0 - 20, i0)]
        w = [x for x in w if x is not None]
        if len(w) < 15:
            return None
        m = sum(w) / len(w)
        sd = math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))
        return sd > VOL_MEDIAN_FROZEN
    return idx, trend_pos, vol_high


def car_at(grid, tk, i0, tau_target):
    """Aligned unsigned CAR at arbitrary tau using the grid's returns."""
    from v3.lab.etf_evidence import CAR_PRE, EST_GAP, EST_MIN, EST_WIN
    from v3.lab.stats import ols
    if not (0 <= i0 and i0 + tau_target < len(grid.dates)):
        return None
    est = grid.dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
    pairs = [(grid.ret[tk].get(d), grid.peer[tk].get(d)) for d in est]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < EST_MIN:
        return None
    reg = ols([a for a, _ in pairs], [b for _, b in pairs])
    if reg is None:
        return None
    cum, printed = 0.0, False
    for tau in range(-CAR_PRE, tau_target + 1):
        j = i0 + tau
        if not (0 <= j < len(grid.dates)):
            break
        d = grid.dates[j]
        r, m = grid.ret[tk].get(d), grid.peer[tk].get(d)
        if r is None or m is None:
            continue
        cum += r - (reg["alpha"] + reg["beta"] * m)
        if tau == tau_target:
            printed = True
    return round(cum * 100.0, 4) if printed else None


def smh_cells():
    import psycopg2
    from yuclaw_falsification import TargetGrid
    from yuclaw_etf_lens import WeightedClusteredCAR
    from v3.lab.cohort_engine import DSN, load_prices
    from v3.lab.etf_evidence import overlap_summary

    prices, td = load_prices()
    idx, trend_pos, vol_high = spy_context(prices, td)
    ov = overlap_summary()
    covered, fund_w = ov["covered"], ov["weights_covered"]
    grid = TargetGrid(covered, prices, td)
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_type, direction,
                          event_time::date
                   FROM events WHERE event_status='accepted'
                     AND ticker = ANY(%s) AND direction <> 0""", (covered,))
            evs = cur.fetchall()
    base_events = []
    for tk, _et, dirn, ev_date in evs:
        day0 = next((d for d in td if d >= ev_date), None)
        if day0 is None:
            continue
        base_events.append((tk, idx[day0], int(dirn), ev_date))

    def e4(obs):
        """obs: [(tk, car)]"""
        ev = [(t, str(i), c) for i, (t, c) in enumerate(obs)]
        wc = WeightedClusteredCAR(ev, fund_w, B=1, seed=SEED)
        w = wc._weights(ev, "capped")
        sw = sum(w)
        return sum(wi * c for wi, (_t, _x, c) in zip(w, ev)) / sw if sw else None

    def subset(era, k, pred=None):
        out = []
        for tk, i0, dirn, ev_date in base_events:
            in_bf = BACKFILL_LO <= ev_date <= BACKFILL_HI
            if era == "backfill" and not in_bf:
                continue
            if era == "live" and in_bf:
                continue
            if pred is not None and pred(i0) is not True:
                continue
            v = car_at(grid, tk, i0, k)
            if v is not None:
                out.append((tk, v * dirn))
        return out

    stat = e4
    clus = lambda o: o[0]
    cells = {
        "k=5 (backfill)": cell_eval(subset("backfill", 5), stat, clus, "smh:k5"),
        "k=10 (backfill)": cell_eval(subset("backfill", 10), stat, clus, "smh:k10"),
        "k=20 backfill (base)": cell_eval(subset("backfill", 20), stat, clus, "smh:k20"),
        "k=60 (backfill only)": cell_eval(subset("backfill", 60), stat, clus, "smh:k60"),
        "trend>=0 (k=20 bf)": cell_eval(subset("backfill", 20, trend_pos), stat, clus, "smh:tr+"),
        "trend<0 (k=20 bf)": cell_eval(subset("backfill", 20, lambda i: trend_pos(i) is False), stat, clus, "smh:tr-"),
        "vol-high (k=20 bf)": cell_eval(subset("backfill", 20, vol_high), stat, clus, "smh:vh"),
        "vol-low (k=20 bf)": cell_eval(subset("backfill", 20, lambda i: vol_high(i) is False), stat, clus, "smh:vl"),
        "era: live (k=20)": cell_eval(subset("live", 20), stat, clus, "smh:live"),
    }
    return cells


def lab_cells():
    from yuclaw_lab_clustered import load_decile_obs, spread_stat
    from v3.lab.cohort_engine import load_prices
    prices, td = load_prices()
    idx, trend_pos, vol_high = spy_context(prices, td)
    didx = {d: i for i, d in enumerate(td)}

    def stat(obs):
        s, _n = spread_stat(obs)
        return s * 100 if s is not None else None   # percent

    clus = lambda o: o[2]   # ticker
    cells = {}
    for k in (1, 5, 20):
        obs = load_decile_obs(k)
        cells[f"k={k}" + (" (base)" if k == 5 else "")] = \
            cell_eval(obs, stat, clus, f"lab:k{k}")
        if k == 5:
            def datepred(pred):
                out = []
                for d, side, tk, ret in obs:
                    dd = date.fromisoformat(d)
                    day0 = next((x for x in td if x >= dd), None)
                    if day0 is not None and pred(didx[day0]) is True:
                        out.append((d, side, tk, ret))
                return out
            cells["trend>=0 (k=5)"] = cell_eval(datepred(trend_pos), stat, clus, "lab:tr+")
            cells["trend<0 (k=5)"] = cell_eval(
                datepred(lambda i: trend_pos(i) is False), stat, clus, "lab:tr-")
            cells["vol-high (k=5)"] = cell_eval(datepred(vol_high), stat, clus, "lab:vh")
            cells["vol-low (k=5)"] = cell_eval(
                datepred(lambda i: vol_high(i) is False), stat, clus, "lab:vl")
    return cells


def inject_lab_panel() -> int:
    """Insert the Lab 'Context robustness' panel into the existing
    docs/preview/lab_clustered.html (idempotent via HTML markers); render
    step only — no computation, no registry writes."""
    page = _REPO / "docs" / "preview" / "lab_clustered.html"
    data = json.loads(OUT_JSON.read_text())
    cells, summ = data["lab"]["cells"], data["lab"]["summary"]
    rows = []
    for k, v in cells.items():
        if v is None:
            rows.append(f"<tr><td style='padding:6px 12px;color:#718096;font-size:12px'>{k}</td>"
                        f"<td colspan='4' style='padding:6px 12px;color:#718096;font-size:11px'>empty — SPY history begins 2026-02-02; a trailing-120-trading-day window is not computable at these signal dates (own-data rule)</td></tr>")
            continue
        rows.append(
            f"<tr><td style='padding:6px 12px;color:#E2E8F0;font-size:12px'>{k}</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#E2E8F0'>{v['estimate']:+.2f}%</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#A0AEC0;font-size:11px'>({v['ci'][0]:+.2f}, {v['ci'][1]:+.2f})</td>"
            f"<td style='padding:6px 12px;font-family:JetBrains Mono,monospace;color:#718096'>{v['n']}/{v['G']}</td>"
            f"<td style='padding:6px 12px;color:#A0AEC0;font-size:11px'>{v['badge']}</td></tr>")
    panel = f"""<!-- ROBUSTNESS-PANEL-START -->
    <div class="panel">
      <div class="panel-title">Context robustness</div>
      <div class="panel-sub">protocol {data['protocol_id']} · pre-declared grid · registered before computation</div>
      <table>
        <thead><tr><th>Context cell</th><th>Spread estimate</th><th>Ticker-cluster CI</th><th>n/G</th><th>Badge</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#A0AEC0;margin-top:10px;line-height:1.6">
        Sign held in {summ['sign_held']}/{summ['n_computed']} computed cells · CI excluded zero in
        {summ['ci_excluded_zero']}/{summ['n_computed']} · breaks in: {', '.join(summ['breaks']) or 'none'} ·
        UNDERPOWERED cells: {', '.join(summ['underpowered']) or 'none'}.
        Every cell ledger-counted. {data['expected_fp_line']}.
        Investment implication: none established — no buy, sell, or alpha conclusion is supported by this page.
      </p>
    </div>
    <!-- ROBUSTNESS-PANEL-END -->"""
    html = page.read_text()
    import re as _re
    html = _re.sub(r"<!-- ROBUSTNESS-PANEL-START -->.*?<!-- ROBUSTNESS-PANEL-END -->",
                   "", html, flags=_re.S)
    anchor = '<div class="panel">\n      <div class="panel-title">Provenance</div>'
    assert anchor in html, "lab_clustered.html anchor not found"
    html = html.replace(anchor, panel + "\n\n    " + anchor, 1)
    page.write_text(html)
    print(f"[robustness] Lab panel injected into {page}")
    return 0


def main() -> int:
    if "--render-lab" in sys.argv[1:]:
        return inject_lab_panel()
    _selftest()
    from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Pre-declared context grid (horizons incl. k=60 "
                          "backfill-only, SPY trend/vol regimes with the vol "
                          "median frozen at 0.008570, era) profiling the SMH "
                          "E4 estimand (primary) and the Lab clustered "
                          "decile spread (secondary); per-cell cluster CIs, "
                          "locked badges, descriptive summary only."),
            primary_endpoint=("sign-coherence fraction across the "
                              "pre-declared grid for the SMH E4 capped "
                              "estimand"),
            secondary_endpoints=[
                "per-cell estimates+CIs for the SMH grid (9 cells)",
                "Lab clustered spread grid (7 cells)",
            ],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) method={METHOD_HASH} "
              "— registered BEFORE computation")
    reg.assert_registered(pid)

    smh = smh_cells()
    smh_sum = summarize(smh, "k=20 backfill (base)")
    lab = lab_cells()
    lab_sum = summarize(lab, "k=5 (base)")

    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "smh": {"cells": smh, "summary": smh_sum},
               "lab": {"cells": lab, "summary": lab_sum},
               "expected_fp_line": None}
    ledger = reg.test_ledger()
    payload["expected_fp_line"] = (
        f"{ledger['total_secondary_cells']} secondary cells ledgered "
        f"registry-wide; expected false positives at alpha=0.05: "
        f"{ledger['expected_false_positives_at_alpha']}")
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window="SMH backfill+live event sets; Lab forward-OOS window",
        n_primary_cells=1, n_secondary_cells=16, result_hash=rh,
        note=("Robustness Profile activation: primary = SMH grid "
              "sign-coherence; secondary = 9 SMH cells + 7 Lab cells.")))
    reg.verify_chain()
    print("[registry] run recorded, chain OK")

    for name, cells, summ in (("SMH-E4", smh, smh_sum), ("Lab", lab, lab_sum)):
        print(f"--- {name}: sign held {summ['sign_held']}/{summ['n_computed']} "
              f"(coherence {summ['coherence_fraction']}) · CI-excl-0 "
              f"{summ['ci_excluded_zero']}/{summ['n_computed']} · breaks "
              f"{summ['breaks']} · underpowered {summ['underpowered']}")
        for k, v in cells.items():
            if v:
                print(f"    {k:>24}: {v['estimate']:+.2f} CI({v['ci'][0]:+.2f},"
                      f"{v['ci'][1]:+.2f}) n={v['n']}/G={v['G']} [{v['badge']}]")
            else:
                print(f"    {k:>24}: empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
