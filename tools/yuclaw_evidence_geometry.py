#!/usr/bin/env python3
"""
Evidence Geometry v1 (Fields-review build Part 2) — REGISTRY-FIRST.
Question: how much independent information does an event population contain?

METHOD_SPEC (locked; the linkage rule below is the pre-committed rule,
stated verbatim):

  STORY CLUSTERING. Two events LINK if:
    (a) same issuer AND their day-0 indices are within 5 trading days, OR
    (b) same event-type AND same lens AND within 3 trading days.
  Stories = connected components of the link graph. Within a single-lens
  population, rule (b) reduces to same-type-within-3-trading-days (the lens
  clause is trivially satisfied) — stated, not hidden.
  Population per lens: deduped accepted events (ticker, type, direction,
  day) restricted to events whose direction-aligned peer-model CAR at
  tau=+20 computes (complete window) — the same population as the lens's
  pooled statistic. Raw filing counts reported beside.

  EFFECTIVE EVIDENCE COUNT. Statistic: event-weighted mean of the aligned
  CAR at +20. Design effect DEFF = Var_story(mean) / Var_iid(mean), where
  Var_story is the story-cluster bootstrap variance (resample stories with
  replacement; B=2000, seed 20260730) and Var_iid is the i.i.d. event
  bootstrap variance (same B). N_eff = N / DEFF. Issuer-level N_eff
  computed identically with issuers as the cluster unit, reported beside.
  DEFF is reported as computed; values marginally below 1 are bootstrap
  noise and are not clamped.

  CONCENTRATION. Story mass = event count. Inverse-HHI over story masses;
  top-story share; top-5 stories with mass %, dominant issuer, dominant
  type, and date span.

Primary endpoint: effective evidence count (N_eff, story-level) for the
SMH covered-sleeve event population at k=20. Secondary: the same for
XEG/ZEO/GDX/URNM; issuer-level N_eff and concentration cells everywhere.
All cells ledger-counted. Edits => supersession.
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

SEED = 20260730
B = 2000

METHOD_SPEC = __doc__
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_NAME = "Evidence Geometry v1"
PROTOCOL_PARAMS = {"link_issuer_days": 5, "link_typelens_days": 3,
                   "B": B, "seed": SEED, "horizon_tau": 20,
                   "targets": ["SMH", "XEG", "ZEO", "GDX", "URNM"]}
OUT_JSON = _REPO / "output" / "oie" / "evidence_geometry.json"


# ------------------------------------------------------------ core engine
def cluster_stories(events):
    """events: [(issuer, i0, etype, car)] -> list[list[event_index]].
    Union-find over the pre-committed linkage rule (single-lens population)."""
    n = len(events)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        ti, ii, ei, _ = events[i]
        for j in range(i + 1, n):
            tj, ij, ej, _ = events[j]
            gap = abs(ii - ij)
            if (ti == tj and gap <= 5) or (ei == ej and gap <= 3):
                union(i, j)
    comps = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return sorted(comps.values(), key=len, reverse=True)


def _boot_var(events, clusters, tag):
    """Bootstrap variance of the event-weighted mean CAR, resampling the
    given clusters (list of index lists) with replacement."""
    rng = random.Random(f"{SEED}:{tag}")
    means = []
    for _ in range(B):
        vals = []
        for _ in clusters:
            c = clusters[rng.randrange(len(clusters))]
            vals += [events[i][3] for i in c]
        means.append(sum(vals) / len(vals))
    m = sum(means) / len(means)
    return sum((x - m) ** 2 for x in means) / (len(means) - 1)


def geometry(events, tag):
    """Full geometry read for one population. events: [(issuer,i0,etype,car)]."""
    n = len(events)
    stories = cluster_stories(events)
    iid = [[i] for i in range(n)]
    issuers = {}
    for i, (t, *_x) in enumerate(events):
        issuers.setdefault(t, []).append(i)
    v_iid = _boot_var(events, iid, f"{tag}:iid")

    def deff_of(clusters, subtag):
        """With <2 clusters, between-cluster variance is undefined; the
        honest N_eff is the cluster count itself (one story = at most one
        independent observation)."""
        if len(clusters) < 2:
            return None, float(len(clusters))
        v = _boot_var(events, clusters, subtag)
        d = v / v_iid if v_iid > 0 else float("inf")
        return d, (n / d if d > 0 else float(len(clusters)))

    deff_story, neff_story = deff_of(stories, f"{tag}:story")
    deff_iss, neff_iss = deff_of(list(issuers.values()), f"{tag}:iss")
    masses = [len(s) for s in stories]
    hhi = sum((m / n) ** 2 for m in masses)
    top5 = []
    for s in stories[:5]:
        evs = [events[i] for i in s]
        by_iss, by_type = {}, {}
        for t, _i, e, _c in evs:
            by_iss[t] = by_iss.get(t, 0) + 1
            by_type[e] = by_type.get(e, 0) + 1
        i0s = [i for _t, i, _e, _c in evs]
        top5.append({
            "size": len(s), "mass_pct": round(100 * len(s) / n, 1),
            "dominant_issuer": max(by_iss, key=by_iss.get),
            "dominant_type": max(by_type, key=by_type.get),
            "span_trading_days": max(i0s) - min(i0s),
        })
    return {
        "n_events": n, "n_stories": len(stories),
        "size_distribution": {"max": masses[0] if masses else 0,
                              "singletons": sum(1 for m in masses if m == 1)},
        "deff_story": round(deff_story, 3) if deff_story is not None else None,
        "n_eff_story": round(neff_story, 1),
        "deff_issuer": round(deff_iss, 3) if deff_iss is not None else None,
        "n_eff_issuer": round(neff_iss, 1),
        "inverse_hhi_stories": round(1 / hhi, 2) if hhi > 0 else None,
        "top_story_share_pct": round(100 * masses[0] / n, 1) if masses else None,
        "top5_stories": top5,
    }


# ------------------------------------------------------------ self-tests
def _selftest():
    rng = random.Random(7)
    # T1 independent events: unique issuer AND unique type, spread far apart
    ev1 = [(f"I{i}", i * 10, f"T{i}", rng.gauss(0, 2)) for i in range(40)]
    g1 = geometry(ev1, "t1")
    assert g1["n_stories"] == 40, g1["n_stories"]
    assert 0.6 <= g1["deff_story"] <= 1.5, g1["deff_story"]
    assert g1["n_eff_story"] >= 0.6 * 40
    # T2 single factor: one issuer, one week -> one story, N_eff collapses
    ev2 = [("A", 100 + (i % 3), "T", 3.0 + rng.gauss(0, 0.05)) for i in range(30)]
    g2 = geometry(ev2, "t2")
    assert g2["n_stories"] == 1, g2["n_stories"]
    assert g2["n_eff_story"] <= 3.0, g2["n_eff_story"]
    # T3 DEFF sanity: dependence inflates DEFF far above 1
    ev3 = []
    for s in range(6):
        base = rng.gauss(0, 3)
        ev3 += [(f"S{s}", s * 50 + k, f"Y{s}", base + rng.gauss(0, 0.1))
                for k in range(5)]
    g3 = geometry(ev3, "t3")
    assert g3["deff_story"] > 1.5, g3["deff_story"]
    # T4 determinism
    assert geometry(ev3, "t3") == g3
    # T5 linkage boundaries
    ev5a = [("A", 0, "X", 1.0), ("A", 5, "Y", 1.0)]     # issuer gap 5 -> link
    assert geometry(ev5a, "t5a")["n_stories"] == 1
    ev5b = [("A", 0, "X", 1.0), ("A", 6, "Y", 1.0)]     # issuer gap 6 -> no
    assert geometry(ev5b, "t5b")["n_stories"] == 2
    ev5c = [("A", 0, "X", 1.0), ("B", 3, "X", 1.0)]     # type gap 3 -> link
    assert geometry(ev5c, "t5c")["n_stories"] == 1
    ev5d = [("A", 0, "X", 1.0), ("B", 4, "X", 1.0)]     # type gap 4 -> no
    assert geometry(ev5d, "t5d")["n_stories"] == 2
    print("[OK] T1 independence · T2 single-factor collapse · T3 DEFF "
          "inflation · T4 determinism · T5 linkage boundaries (4 cases)")


# ------------------------------------------------------------ real run
def real_populations():
    import psycopg2
    from yuclaw_falsification import TargetGrid
    from v3.lab.cohort_engine import DSN, load_prices
    from v3.lab.etf_evidence import canada_lens_holdings, overlap_summary

    prices, trade_dates = load_prices()
    idx = {d: i for i, d in enumerate(trade_dates)}
    pops = {}
    lens_cov = {"SMH": overlap_summary()["covered"],
                **{k: sorted(v) for k, v in canada_lens_holdings().items()}}
    for lens, covered in lens_cov.items():
        grid = TargetGrid(covered, prices, trade_dates)
        with psycopg2.connect(DSN) as cn:
            cn.set_session(readonly=True)
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT DISTINCT ticker, event_type, direction,
                              event_time::date
                       FROM events WHERE event_status='accepted'
                         AND ticker = ANY(%s)""", (covered,))
                evs = cur.fetchall()
                cur.execute(
                    """SELECT count(*) FROM events
                       WHERE event_status='accepted' AND ticker = ANY(%s)""",
                    (covered,))
                n_filings = cur.fetchone()[0]
        rows = []
        for tk, et, dirn, ev_date in evs:
            day0 = next((d for d in trade_dates if d >= ev_date), None)
            if day0 is None:
                continue
            v = grid.car20(tk, idx[day0])
            if v is None:
                continue
            rows.append((tk, idx[day0], et, v * (int(dirn) if dirn else 1)))
        pops[lens] = {"events": rows, "n_raw_filings": n_filings}
    return pops


def main() -> int:
    _selftest()
    from yuclaw_protocol_registry import Protocol, Registry, Run, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC, PROTOCOL_PARAMS)
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name=PROTOCOL_NAME, method_hash=METHOD_HASH,
            spec_summary=("Story clustering (pre-committed linkage: same "
                          "issuer within 5 trading days OR same type+lens "
                          "within 3), effective evidence count via story-"
                          "cluster design effect, concentration; five lens "
                          "populations at k=20."),
            primary_endpoint=("effective evidence count (story-level N_eff) "
                              "for the SMH covered-sleeve event population "
                              "at k=20"),
            secondary_endpoints=[
                "N_eff for XEG/ZEO/GDX/URNM populations (4 cells)",
                "issuer-level N_eff, all populations (5 cells)",
                "concentration (inverse-HHI, top-story share), all populations",
            ],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ))
        reg.verify_chain()
        print(f"[registry] LOCKED {pid} ({PROTOCOL_NAME}) method={METHOD_HASH} "
              "— registered BEFORE computation")
    reg.assert_registered(pid)

    pops = real_populations()
    results = {}
    for lens, pop in pops.items():
        g = geometry(pop["events"], f"real:{lens}")
        g["n_raw_filings"] = pop["n_raw_filings"]
        results[lens] = g
        print(f"[{lens}] filings={g['n_raw_filings']} events={g['n_events']} "
              f"stories={g['n_stories']} N_eff(story)={g['n_eff_story']} "
              f"N_eff(issuer)={g['n_eff_issuer']} DEFF={g['deff_story']} "
              f"top-story {g['top_story_share_pct']}%")

    payload = {"protocol_id": pid, "method_hash": METHOD_HASH,
               "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "results": results}
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    rh = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    reg.record_run(Run(
        protocol_id=pid,
        run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        data_window="all-era deduped accepted events with complete +20 windows, 5 populations",
        n_primary_cells=1, n_secondary_cells=14, result_hash=rh,
        note=("Evidence Geometry activation: primary = SMH story-level "
              "N_eff; secondary = 4 lens N_eff + 5 issuer-level N_eff + "
              "5 concentration cells.")))
    reg.verify_chain()
    print("[registry] run recorded, chain OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
