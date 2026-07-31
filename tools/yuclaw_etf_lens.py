#!/usr/bin/env python3
"""
YUCLAW ETF Evidence Lens — admission standard + anatomy + multi-estimand
inference (v1 reference implementation)
========================================================================
From the OIE external review (§5, §6, §9, §18, §19, §29, §30) with YUCLAW
amendments. Stdlib-only, deterministic, locked vocabulary.

CONTENTS
  1. LensAdmission — the §9 admission standard as code: a lens publishes
     only if it passes; labels NOT_ADMITTED / EXPLORATORY / MEASURED
     (MATURE reserved: requires external replication — cannot self-award).
  2. CoverageAnatomy — §6: covered/uncovered weight decomposition,
     concentration (top-1/3/5, effective N via inverse-HHI), uncovered
     reason breakdown.
  3. Breadth — §18 core: share of covered weight per research state,
     evidence freshness split, per-state issuer counts.
  4. WeightedClusteredCAR — §5 multi-estimand inference, PRE-REGISTERED:
     event- / issuer- / ETF- / capped-ETF-weighted mean CAR, each with
     issuer-cluster and date-cluster bootstrap CIs and the conservative
     envelope (wider of the two; formal two-way pending — stated, not
     faked). Extends the registered ClusteredCAR discipline.
All ETF-level outputs are coverage/evidence classifications — never
recommendations; the frozen implication line applies at render time.
"""
from __future__ import annotations
import hashlib, json, math, random
from dataclasses import dataclass, field
from typing import Optional

METHOD_SPEC = """
ETF LENS MULTI-ESTIMAND CAR — pre-committed specification (v1)
Events: (issuer, event_date, car_pct) direction-aligned pooled CARs for one
lens/horizon, covered sleeve only, point-in-time.
Estimands (all reported; none privileged post hoc):
 E1 event-weighted: w_e = 1.
 E2 issuer-weighted: w_e = 1 / n_events(issuer(e)).
 E3 ETF-weighted: w_e = fund_weight(issuer(e)) / n_events(issuer(e)),
    fund weights renormalized to 1 over the covered sleeve.
 E4 capped-ETF-weighted: as E3 with issuer fund weights capped at 20%
    of covered sleeve then renormalized (concentration control).
Statistic: weighted mean CAR = sum(w_e * car_e) / sum(w_e).
Inference per estimand:
 (a) issuer-cluster bootstrap: resample issuers with replacement
     (all events + weights of a sampled issuer enter; ETF weights follow
     the sampled issuer set and are renormalized per replicate);
 (b) date-cluster bootstrap: resample distinct event dates likewise;
 (c) conservative envelope: the wider of (a),(b) percentile CIs,
     labeled 'conservative envelope — formal two-way clustering pending'.
B=4000, seed=20260723, percentile 2.5/97.5. Naive CI reported beside,
labeled naive. Badges (locked): UNDERPOWERED if issuers<8 or dates<10 or
events<10; DESCRIPTIVE if envelope includes 0; else PRELIMINARY.
Registered before computation on any real lens data; edits => supersession.
"""
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
SEED = 20260723

# ------------------------------------------------------------- admission §9
@dataclass
class AdmissionThresholds:
    """v1 defaults per the external review §9; supersede via registry only."""
    min_covered_weight_pct: float = 50.0
    min_covered_issuers: int = 8
    min_effective_issuers: float = 5.0
    min_price_coverage_pct: float = 95.0
    measured_covered_weight_pct: float = 65.0   # + live protocol registered
    measured_covered_issuers: int = 10
    concentration_floor: float = 3.5   # N_eff in [floor, min) => admitted
                                       # as CONCENTRATION-LIMITED, capped
                                       # estimand mandatory as headline

@dataclass
class LensFacts:
    ticker: str
    holdings_source: str            # e.g. "issuer daily holdings file"
    holdings_date: str
    covered_issuers: int
    covered_weight_pct: float
    covered_weights: list           # per covered issuer, % of full fund
    price_coverage_pct: float
    substrate_disclosed: bool
    reproduction_bundle: bool
    live_protocol_registered: bool = False
    external_replications: int = 0

def effective_n(weights_pct: list) -> float:
    """Inverse-HHI over renormalized covered weights."""
    tot = sum(weights_pct)
    if tot <= 0: return 0.0
    shares = [w / tot for w in weights_pct]
    return round(1.0 / sum(s * s for s in shares), 2)

def admit(f: LensFacts, t: AdmissionThresholds = AdmissionThresholds()):
    n_eff = effective_n(f.covered_weights)
    reasons = []
    if not f.holdings_source: reasons.append("no verified holdings source")
    if not f.holdings_date: reasons.append("holdings date undisclosed")
    if f.covered_weight_pct < t.min_covered_weight_pct:
        reasons.append(f"covered weight {f.covered_weight_pct:.1f}% < "
                       f"{t.min_covered_weight_pct:.0f}%")
    if f.covered_issuers < t.min_covered_issuers:
        reasons.append(f"covered issuers {f.covered_issuers} < "
                       f"{t.min_covered_issuers}")
    conc_limited = False
    if n_eff < t.min_effective_issuers:
        if n_eff >= t.concentration_floor:
            conc_limited = True   # admitted, but concentration-flagged
        else:
            reasons.append(f"effective issuers {n_eff} < concentration floor "
                           f"{t.concentration_floor}")
    if f.price_coverage_pct < t.min_price_coverage_pct:
        reasons.append(f"price coverage {f.price_coverage_pct:.1f}% < "
                       f"{t.min_price_coverage_pct:.0f}%")
    if not f.substrate_disclosed: reasons.append("filing substrate undisclosed")
    if not f.reproduction_bundle: reasons.append("no reproduction bundle")
    if reasons:
        return {"label": "NOT_ADMITTED", "effective_issuers": n_eff,
                "reasons": reasons}
    label = "EXPLORATORY"
    if (f.covered_weight_pct >= t.measured_covered_weight_pct
            and f.covered_issuers >= t.measured_covered_issuers
            and f.live_protocol_registered and not conc_limited):
        label = "MEASURED"
    if conc_limited:
        label = "EXPLORATORY (CONCENTRATION-LIMITED)"
    # MATURE is never self-awarded: requires >=1 external replication AND
    # MEASURED criteria; even then rendered as "MEASURED + externally
    # replicated" until a versioned standard defines MATURE.
    out = {"label": label, "effective_issuers": n_eff, "reasons": [],
           "external_replications": f.external_replications,
           "note": "MATURE reserved — requires externally replicated "
                   "results under a versioned standard"}
    if conc_limited:
        out["requirement"] = ("capped-weight estimand (E4) mandatory as the "
                              "headline inference; top-issuer share disclosed "
                              "beside every lens statistic")
    return out

CLIENT_STANDARD_SPEC = """
CLIENT-LENS ADMISSION STANDARD — v1 (locked; supersede via registry only)
Ruling: user_defined (client-namespace) lenses CAP at EXPLORATORY (CLIENT).
MEASURED and above are reserved for canonical public lenses. Rationale:
client baskets self-select full coverage — every submitted name is 'covered'
by construction — so coverage thresholds designed for partial-coverage
public lenses (where covered weight is a measured, adversarial quantity)
overstate maturity when applied to user-defined input. A client lens can
earn higher standing only through a future versioned client-standard
requiring sustained live accrual and an executed (not merely shipped)
reproduction. NOT_ADMITTED reasons apply unchanged; concentration flags and
the capped-estimand requirement carry through. Standard entry — no runs are
ever recorded against it (uncomputed class, like the thresholds themselves).
"""
CLIENT_STANDARD_HASH = hashlib.sha256(CLIENT_STANDARD_SPEC.encode()).hexdigest()[:16]


def admit_client(f: LensFacts, t: AdmissionThresholds = AdmissionThresholds()):
    """Client-namespace ruling: same gates as admit(), but any admitted
    verdict is capped at EXPLORATORY (CLIENT) per CLIENT_STANDARD_SPEC."""
    out = admit(f, t)
    if out["label"] == "NOT_ADMITTED":
        return out
    capped = dict(out)
    capped["canonical_label_would_be"] = out["label"]
    capped["label"] = ("EXPLORATORY (CLIENT, CONCENTRATION-LIMITED)"
                       if "CONCENTRATION-LIMITED" in out["label"]
                       else "EXPLORATORY (CLIENT)")
    capped["note"] = ("user_defined lens: capped at EXPLORATORY (CLIENT) — "
                      "MEASURED and above reserved for canonical public "
                      "lenses (Client-lens admission standard v1). "
                      + out.get("note", ""))
    return capped


# ------------------------------------------------------- anatomy §6 / §19
@dataclass
class UncoveredSlice:
    reason: str        # e.g. "foreign private issuer (20-F/6-K substrate)"
    weight_pct: float
    names: int

def coverage_anatomy(f: LensFacts, uncovered: list, top_names: list):
    """top_names: [(issuer, covered_weight_pct)] sorted desc."""
    ws = sorted(f.covered_weights, reverse=True)
    cum = lambda k: round(sum(ws[:k]), 2)
    unc_total = round(sum(u.weight_pct for u in uncovered), 2)
    return {
        "covered_weight_pct": f.covered_weight_pct,
        "uncovered_weight_pct": unc_total,
        "identity_check_pct": round(f.covered_weight_pct + unc_total, 2),
        "top1_covered_pct": cum(1), "top3_covered_pct": cum(3),
        "top5_covered_pct": cum(5),
        "effective_covered_issuers": effective_n(f.covered_weights),
        "largest_covered": top_names[0] if top_names else None,
        "uncovered_by_reason": [
            {"reason": u.reason, "weight_pct": u.weight_pct, "names": u.names}
            for u in sorted(uncovered, key=lambda u: -u.weight_pct)],
    }

def breadth(issuer_states: list):
    """issuer_states: [(issuer, weight_pct, state, evidence_age_days)]."""
    tot = sum(w for _, w, _, _ in issuer_states) or 1.0
    by = {}
    for _, w, s, _ in issuer_states:
        by[s] = by.get(s, 0.0) + w
    fresh = sum(w for _, w, _, a in issuer_states if a is not None and a <= 7)
    stale = sum(w for _, w, _, a in issuer_states if a is not None and a > 30)
    return {"state_share_pct": {s: round(100 * w / tot, 1)
                                for s, w in sorted(by.items())},
            "fresh_7d_weight_pct": round(100 * fresh / tot, 1),
            "stale_30d_weight_pct": round(100 * stale / tot, 1)}

# ------------------------------------------- §5 multi-estimand inference
@dataclass
class EstimandResult:
    estimand: str; mean_pct: float
    naive_ci: tuple; issuer_ci: tuple; date_ci: tuple; envelope: tuple
    n_events: int; n_issuers: int; n_dates: int; badge: str

class WeightedClusteredCAR:
    """events: [(issuer, date, car_pct)]; fund_w: {issuer: pct of full fund}."""
    def __init__(self, events, fund_w, B=4000, seed=SEED):
        self.ev, self.fw, self.B, self.seed = list(events), dict(fund_w), B, seed

    def _weights(self, events, kind):
        n_by = {}
        for i, _, _ in events: n_by[i] = n_by.get(i, 0) + 1
        if kind == "event":
            return [1.0] * len(events)
        if kind == "issuer":
            return [1.0 / n_by[i] for i, _, _ in events]
        fw = {i: self.fw.get(i, 0.0) for i in n_by}
        if kind == "capped":
            tot = sum(fw.values()) or 1.0
            capped = {i: min(w, 0.20 * tot) for i, w in fw.items()}
            fw = capped
        tot = sum(fw.values()) or 1.0
        return [fw[i] / tot / n_by[i] for i, _, _ in events]

    def _wmean(self, events, kind):
        w = self._weights(events, kind)
        sw = sum(w)
        return sum(wi * c for wi, (_, _, c) in zip(w, events)) / sw if sw else 0.0

    def _boot(self, kind, cluster_key, tag):
        rng = random.Random(f"{self.seed}:{kind}:{tag}")
        keys = sorted({cluster_key(e) for e in self.ev})
        by = {}
        for e in self.ev: by.setdefault(cluster_key(e), []).append(e)
        reps = []
        for _ in range(self.B):
            sample = []
            for _ in keys:
                sample += by[keys[rng.randrange(len(keys))]]
            reps.append(self._wmean(sample, kind))
        reps.sort()
        return (round(reps[int(0.025 * self.B)], 2),
                round(reps[int(0.975 * self.B) - 1], 2))

    def run(self, kind) -> EstimandResult:
        xs = [c for _, _, c in self.ev]; n = len(xs)
        w = self._weights(self.ev, kind); sw = sum(w)
        mean = self._wmean(self.ev, kind)
        # naive: weighted, independence-assuming
        var = sum(wi * (c - mean) ** 2 for wi, c in zip(w, xs)) / sw
        neff = sw ** 2 / sum(wi * wi for wi in w)
        se = math.sqrt(var / neff) if neff > 0 else 0.0
        naive = (round(mean - 1.959964 * se, 2), round(mean + 1.959964 * se, 2))
        ic = self._boot(kind, lambda e: e[0], "iss")
        dc = self._boot(kind, lambda e: e[1], "date")
        env = (min(ic[0], dc[0]), max(ic[1], dc[1]))
        issuers = len({i for i, _, _ in self.ev})
        dates = len({d for _, d, _ in self.ev})
        badge = ("UNDERPOWERED" if issuers < 8 or dates < 10 or n < 10 else
                 "DESCRIPTIVE" if env[0] <= 0.0 <= env[1] else "PRELIMINARY")
        return EstimandResult(kind, round(mean, 2), naive, ic, dc, env,
                              n, issuers, dates, badge)

    def run_all(self):
        return {k: self.run(k) for k in ("event", "issuer", "etf", "capped")}

# -------------------------------------------- formal two-way (CGM) — v2
V2_AMENDMENT = """
AMENDMENT (v2, 2026-07-31): beside the conservative envelope (which is
retained unchanged), each estimand reports the FORMAL TWO-WAY
cluster-robust interval: CGM variance V = V_issuer + V_date -
V_intersection computed by the score-sum sandwich on the weighted mean;
CI = mean +/- 1.959964 * sqrt(V). Small-G guard: min(G_issuer, G_date) < 8
=> the two-way interval carries UNDERPOWERED regardless of width. If the
CGM variance is non-positive (a known small-sample degeneracy) the wider
single-way variance is substituted and the cell is labeled DEGENERATE —
disclosed, never silent. The envelope remains the headline interval; the
formal two-way is reported beside it, labeled. All other clauses of v1
inherited verbatim."""
METHOD_SPEC_V2 = METHOD_SPEC + V2_AMENDMENT
METHOD_HASH_V2 = hashlib.sha256(METHOD_SPEC_V2.encode()).hexdigest()[:16]


def cgm_two_way(events, fund_w, kind, z=1.959964):
    """events: [(issuer, date, car_pct)]. Returns the formal two-way cell."""
    wc = WeightedClusteredCAR(events, fund_w, B=1)
    w = wc._weights(events, kind)
    sw = sum(w)
    if not sw:
        return None
    mean = sum(wi * c for wi, (_i, _d, c) in zip(w, events)) / sw

    def V(keyfn):
        sums: dict = {}
        for wi, e in zip(w, events):
            k = keyfn(e)
            sums[k] = sums.get(k, 0.0) + wi * (e[2] - mean)
        return sum(s * s for s in sums.values()) / (sw * sw)

    vi, vd = V(lambda e: e[0]), V(lambda e: e[1])
    vint = V(lambda e: (e[0], e[1]))
    var = vi + vd - vint
    degenerate = var <= 0
    if degenerate:
        var = max(vi, vd)
    se = math.sqrt(var)
    g = min(len({e[0] for e in events}), len({e[1] for e in events}))
    return {"mean_pct": round(mean, 2),
            "ci": (round(mean - z * se, 2), round(mean + z * se, 2)),
            "se": round(se, 3), "G_min": g,
            "degenerate": degenerate,
            "badge": "UNDERPOWERED" if g < 8 else
                     ("DESCRIPTIVE" if mean - z * se <= 0 <= mean + z * se
                      else "PRELIMINARY")}


# ---------------------------------------------------------------- selftest
def _selftest():
    # T1 effective-N math
    assert effective_n([50, 50]) == 2.0 and effective_n([100]) == 1.0
    assert abs(effective_n([12.5] * 8) - 8.0) < 1e-9
    # T2 admission boundaries
    base = dict(ticker="SMH", holdings_source="issuer file",
                holdings_date="2026-07-20", covered_issuers=8,
                covered_weight_pct=50.24,
                covered_weights=[19.01, 8.2, 6.5, 5.0, 4.2, 3.1, 2.4, 1.83],
                price_coverage_pct=100.0, substrate_disclosed=True,
                reproduction_bundle=True)
    a = admit(LensFacts(**base))
    assert a["label"] == "EXPLORATORY (CONCENTRATION-LIMITED)", a
    assert "capped-weight" in a["requirement"]
    # a genuinely diversified lens passes clean:
    div = dict(base); div["covered_weights"] = [8, 7, 7, 7, 7, 6, 5, 3.24]
    assert admit(LensFacts(**div))["label"] == "EXPLORATORY"
    bad = dict(base); bad["covered_weight_pct"] = 49.9
    assert admit(LensFacts(**bad))["label"] == "NOT_ADMITTED"
    meas = dict(base); meas.update(covered_weight_pct=70, covered_issuers=12,
        covered_weights=[10, 9, 8, 8, 7, 6, 6, 5, 4, 3, 2, 2],
        live_protocol_registered=True)
    assert admit(LensFacts(**meas))["label"] == "MEASURED"
    # T3 anatomy identity
    an = coverage_anatomy(LensFacts(**base),
        [UncoveredSlice("foreign private issuer (20-F/6-K substrate)", 39.7, 12),
         UncoveredSlice("outside 79-ticker universe", 10.06, 5)],
        [("NVDA", 19.01)])
    assert abs(an["identity_check_pct"] - 100.0) < 0.01
    assert an["largest_covered"] == ("NVDA", 19.01)
    # T4 estimands: equal weights + one event/issuer -> all four agree
    rng = random.Random(5)
    ev_eq = [(f"I{i}", f"d{i%12}", rng.gauss(0.5, 2)) for i in range(24)]
    fw_eq = {f"I{i}": 4.0 for i in range(24)}
    wc = WeightedClusteredCAR(ev_eq, fw_eq, B=400)
    r = wc.run_all()
    means = [r[k].mean_pct for k in r]
    assert max(means) - min(means) < 1e-9, "T4 equal-case estimands diverge"
    # T5 concentration sensitivity: NVDA-heavy weights move E3 toward NVDA
    ev = [("NVDA", f"d{k}", 3.0) for k in range(5)] + \
         [(f"O{i}", f"e{i}", -1.0) for i in range(10)]
    fw = {"NVDA": 19.0, **{f"O{i}": 2.0 for i in range(10)}}
    wc2 = WeightedClusteredCAR(ev, fw, B=400)
    r2 = wc2.run_all()
    assert r2["etf"].mean_pct > r2["issuer"].mean_pct, "T5 ETF-weight not sensitive"
    assert r2["capped"].mean_pct < r2["etf"].mean_pct, "T5 cap did not bind"
    # T6 dependence: clustered envelope wider than naive under within-issuer corr
    rng = random.Random(9)
    ev3 = []
    for i in range(9):
        b = rng.gauss(0, 3)
        ev3 += [(f"C{i}", f"g{k}", b + rng.gauss(0, 0.3)) for k in range(12)]
    wc3 = WeightedClusteredCAR(ev3, {f"C{i}": 11.1 for i in range(9)}, B=400)
    e3 = wc3.run("event")
    assert (e3.envelope[1] - e3.envelope[0]) > 1.5 * (e3.naive_ci[1] - e3.naive_ci[0])
    # T7 determinism
    assert wc3.run("event") == WeightedClusteredCAR(
        ev3, {f"C{i}": 11.1 for i in range(9)}, B=400).run("event")
    # T8 client cap: facts that would earn MEASURED can NEVER emit MEASURED
    # through the client ruling — EXPLORATORY (CLIENT) is the ceiling.
    meas2 = dict(base); meas2.update(covered_weight_pct=70, covered_issuers=12,
        covered_weights=[10, 9, 8, 8, 7, 6, 6, 5, 4, 3, 2, 2],
        live_protocol_registered=True)
    assert admit(LensFacts(**meas2))["label"] == "MEASURED"
    ac = admit_client(LensFacts(**meas2))
    assert ac["label"] == "EXPLORATORY (CLIENT)", ac
    assert ac["canonical_label_would_be"] == "MEASURED"
    assert "MEASURED" not in admit_client(LensFacts(**base))["label"]
    bad2 = dict(base); bad2["covered_weight_pct"] = 49.9
    assert admit_client(LensFacts(**bad2))["label"] == "NOT_ADMITTED"
    # T9 formal two-way (CGM): three synthetic regimes
    rng9 = random.Random(11)
    fw9 = {f"I{i}": 5.0 for i in range(20)}
    # (a) independent: unique issuer AND unique date per event -> ~naive width
    ev_a = [(f"I{i}", f"d{i}", rng9.gauss(0, 2)) for i in range(20)]
    tw_a = cgm_two_way(ev_a, fw9, "event")
    mean_a = sum(c for *_x, c in ev_a) / 20
    naive_se = (sum((c - mean_a) ** 2 for *_x, c in ev_a) / 20 / 20) ** 0.5
    assert 0.6 <= tw_a["se"] / naive_se <= 1.5, (tw_a["se"], naive_se)
    # (b) issuer-correlated: strong within-issuer shock -> two-way tracks the
    #     issuer-cluster width, far above naive
    ev_b = []
    for i in range(10):
        shock = rng9.gauss(0, 3)
        ev_b += [(f"I{i}", f"e{i}{k}", shock + rng9.gauss(0, 0.1))
                 for k in range(4)]
    tw_b = cgm_two_way(ev_b, fw9, "event")
    mean_b = sum(c for *_x, c in ev_b) / len(ev_b)
    naive_b = (sum((c - mean_b) ** 2 for *_x, c in ev_b)
               / len(ev_b) / len(ev_b)) ** 0.5
    # theoretical inflation cap is sqrt(4)=2 with 4 events/cluster; require
    # near-cap inflation AND agreement with the issuer-only sandwich
    assert tw_b["se"] > 1.7 * naive_b, (tw_b["se"], naive_b)
    wcb = WeightedClusteredCAR(ev_b, fw9, B=1)
    wb = wcb._weights(ev_b, "event")
    swb = sum(wb)
    sums_b: dict = {}
    for wi, e in zip(wb, ev_b):
        sums_b[e[0]] = sums_b.get(e[0], 0.0) + wi * (e[2] - mean_b)
    se_iss_only = (sum(x * x for x in sums_b.values()) / (swb * swb)) ** 0.5
    assert 0.9 <= tw_b["se"] / se_iss_only <= 1.1, (tw_b["se"], se_iss_only)
    # (c) both-way shocks -> wider than either single-way sandwich
    ev_c = []
    row = {i: rng9.gauss(0, 2) for i in range(6)}
    col = {j: rng9.gauss(0, 2) for j in range(6)}
    for i in range(6):
        for j in range(6):
            ev_c.append((f"R{i}", f"C{j}", row[i] + col[j] + rng9.gauss(0, 0.1)))
    wc9 = WeightedClusteredCAR(ev_c, {f"R{i}": 5 for i in range(6)}, B=1)
    w9 = wc9._weights(ev_c, "event")
    sw9 = sum(w9)
    m9 = sum(wi * c for wi, (_a, _b, c) in zip(w9, ev_c)) / sw9

    def _v(keyfn):
        s: dict = {}
        for wi, e in zip(w9, ev_c):
            s[keyfn(e)] = s.get(keyfn(e), 0.0) + wi * (e[2] - m9)
        return sum(x * x for x in s.values()) / (sw9 * sw9)
    tw_c = cgm_two_way(ev_c, {f"R{i}": 5 for i in range(6)}, "event")
    assert tw_c["se"] ** 2 > _v(lambda e: e[0]) and \
           tw_c["se"] ** 2 > _v(lambda e: e[1]), "two-way not wider than singles"
    assert tw_c["badge"] == "UNDERPOWERED"   # G_min = 6 < 8
    return r2

if __name__ == "__main__":
    r = _selftest()
    print("[OK] T1 effective-N · T2 admission boundaries · T3 anatomy identity "
          "· T4 equal-case agreement · T5 concentration sensitivity · "
          "T6 dependence widens envelope · T7 determinism · "
          "T8 client cap (user_defined never MEASURED) · "
          "T9 formal two-way CGM (independent/issuer/both-way)")
    print(f"[OK] METHOD_HASH={METHOD_HASH}  (register before real lens data)\n")
    for k, res in r.items():
        print(f"{k:>7}: mean={res.mean_pct:+.2f}%  naive{res.naive_ci}  "
              f"issuer{res.issuer_ci}  date{res.date_ci}  env{res.envelope}  "
              f"[{res.badge}]")
