#!/usr/bin/env python3
"""
YUCLAW Evidence Decision Canvas — inference + synthesis layer (v1 reference)
============================================================================
Companion to research_brief.py. Implements the statistical core of the
external review (Priorities 3, 4; sections 7, 8, 9, 10, 22) with YUCLAW
amendments. Stdlib-only. Deterministic (seeded RNG). Locked vocabulary.

PRE-REGISTRATION NOTE (methodology discipline):
  This module is written and hash-stamped BEFORE being run on any real
  YUCLAW event data. The sha256 of METHOD_SPEC below is the pre-commitment:
  when v5.2 computes clustered results, the estimator provably predates them.

CONTENTS
  1. ClusteredCAR — naive CI, issuer-cluster bootstrap CI, wild cluster
     bootstrap CI (Rademacher), effective cluster count, MDE at 80% power.
  2. badge() — statistical-status assignment from locked rules.
  3. TensionEngine — deterministic contradiction detection (review §7).
  4. conclusion_change() — "what would change this conclusion" (review §8).
  5. C6Explainer — the §9 block, locked vocabulary.
  6. DecisionCanvas — assembles everything into the §22 canvas (HTML+text).
"""
from __future__ import annotations
import hashlib, html, json, math, os, random, tempfile
from dataclasses import dataclass, field
from typing import Optional

METHOD_SPEC = """
CLUSTERED CAR INFERENCE — pre-committed specification (v1)
Population: direction-aligned pooled event CARs (percent units) for one lens
and one horizon. Cluster unit: issuer (primary); date-cluster diagnostic
reported separately. Estimand: mean pooled CAR.
(1) Naive CI: mean ± z0.975 · sd/√n. Reported for comparison only.
(2) Cluster bootstrap CI: resample ISSUERS with replacement (all events of a
    sampled issuer enter together); B=4000; percentile 2.5/97.5. Seed=20260717.
(3) Wild cluster bootstrap CI: cluster-level Rademacher weights on centered
    cluster contributions; mean* = mean + Σ w_c·S_c/n where S_c = Σ(e_ij) over
    cluster c, e_ij = x_ij − mean; B=4000; percentile CI; same seed stream.
(4) Effective clusters: G = number of distinct issuers with ≥1 event.
(5) Cluster-robust SE: sd of cluster bootstrap replicate means.
(6) MDE at 80% power (two-sided 5%): (1.959964+0.841621) · SE_cluster.
Reporting rule: cluster CI is primary; naive shown beside it labeled naive.
If G < 8, all intervals carry UNDERPOWERED regardless of width.
"""
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps({}, sort_keys=True)).encode()).hexdigest()[:12]

Z975, Z80 = 1.959964, 0.841621
SEED = 20260717


def _registry_guard(pid: str) -> None:
    """REGISTRY-FIRST: refuse to compute unless the protocol is LOCKED in
    registry/protocols.jsonl (chain-verified on load). Fails closed when the
    registry file is absent."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)

# ------------------------------------------------------------ 1. inference
@dataclass
class CarInference:
    horizon_day: int
    mean_pct: float
    n_events: int
    n_clusters: int
    naive_ci: tuple
    cluster_ci: tuple
    wild_ci: tuple
    se_cluster: float
    mde80_pct: float
    events_per_cluster_median: float
    top3_cluster_share_pct: int

class ClusteredCAR:
    """events: list of (issuer, car_pct). All math per METHOD_SPEC."""
    def __init__(self, events, horizon_day, B=4000, seed=SEED):
        self.ev = list(events); self.day = horizon_day
        self.B, self.rng = B, random.Random(seed)

    def run(self) -> CarInference:
        _registry_guard(PROTOCOL_ID)
        xs = [c for _, c in self.ev]; n = len(xs)
        mean = sum(xs) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
        naive = (mean - Z975 * sd / math.sqrt(n), mean + Z975 * sd / math.sqrt(n))

        clusters = {}
        for iss, c in self.ev:
            clusters.setdefault(iss, []).append(c)
        names = sorted(clusters)                    # determinism
        G = len(names)

        # (2) cluster (issuer) bootstrap — percentile
        reps = []
        for _ in range(self.B):
            pick = [names[self.rng.randrange(G)] for _ in range(G)]
            pool = [c for nm in pick for c in clusters[nm]]
            reps.append(sum(pool) / len(pool))
        reps.sort()
        cci = (reps[int(0.025 * self.B)], reps[int(0.975 * self.B) - 1])
        se_c = _sd(reps)

        # (3) wild cluster bootstrap — Rademacher on centered contributions
        S = {nm: sum(c - mean for c in clusters[nm]) for nm in names}
        wreps = []
        for _ in range(self.B):
            tot = sum(S[nm] if self.rng.random() < 0.5 else -S[nm]
                      for nm in names)
            wreps.append(mean + tot / n)
        wreps.sort()
        wci = (wreps[int(0.025 * self.B)], wreps[int(0.975 * self.B) - 1])

        sizes = sorted((len(v) for v in clusters.values()), reverse=True)
        med = _median(sizes)
        top3 = round(100 * sum(sizes[:3]) / n)
        return CarInference(self.day, round(mean, 2), n, G,
                            _r2(naive), _r2(cci), _r2(wci),
                            round(se_c, 3),
                            round((Z975 + Z80) * se_c, 2), med, top3)

def _sd(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
def _median(v): s = sorted(v); k = len(s) // 2; return (s[k] if len(s) % 2 else (s[k-1]+s[k])/2)
def _r2(t): return (round(t[0], 2), round(t[1], 2))

# ------------------------------------------------------------ 2. badges
def badge(inf: CarInference) -> str:
    if inf.n_clusters < 8: return "UNDERPOWERED"
    lo, hi = inf.cluster_ci
    if lo <= 0.0 <= hi: return "DESCRIPTIVE"
    return "PRELIMINARY"   # excluded zero, but single-lens, pre-decomposition

# ------------------------------------------------------------ 3. tensions
POSITIVE_TYPES = {"DIVIDEND", "BUYBACK", "GUIDANCE_RAISE"}
RISK_MARKERS = {"REGULATORY", "LITIGATION", "GUIDANCE_CUT"}

@dataclass
class Tension:
    issuer: str; positive: list; offsetting: list; missing: list; conclusion: str

class TensionEngine:
    """Deterministic contradiction detection. Rules, not models."""
    def detect(self, issuer_rows) -> list:
        out = []
        for r in issuer_rows:
            types = set(r.get("recent_event_types", []))
            pos = sorted(types & POSITIVE_TYPES)
            off = []
            if r.get("c6_state") == "elevated":
                off.append("C6 posture elevated (evidence-rarity gate)")
            off += [f"{t} event present" for t in sorted(types & RISK_MARKERS)]
            missing = ([] if r.get("form4_eligible")
                       else ["Canadian insider substrate (SEDI — not ingested)"])
            if pos and off:
                out.append(Tension(
                    r["ticker"], [f"{t} event" for t in pos], off, missing,
                    "Capital-return / positive evidence is present, but the "
                    "offsetting posture means risk-side interpretation is "
                    "incomplete — review both before drawing any view."))
        return sorted(out, key=lambda t: t.issuer)

# ------------------------------------ 4. what would change the conclusion
def conclusion_change(inf: CarInference) -> list:
    """Deterministic statements of what future evidence moves this reading.
    Approximation for cluster growth: SE ∝ 1/√G at current cluster sizes —
    stated as an approximation in output."""
    out = []
    lo, hi = inf.cluster_ci
    if lo <= 0.0 <= hi:
        if abs(inf.mean_pct) > 1e-9:
            need_se = abs(inf.mean_pct) / Z975
            G_needed = math.ceil(inf.n_clusters * (inf.se_cluster / need_se) ** 2)
            add = max(0, G_needed - inf.n_clusters)
            out.append(f"If the effect stays near {inf.mean_pct:+.1f}%, roughly "
                       f"{add} additional distinct issuers with events (~{G_needed} "
                       f"total clusters) would be needed before the clustered CI "
                       f"could exclude zero (1/√G approximation).")
        out.append(f"A true effect smaller than the current MDE "
                   f"({inf.mde80_pct:.1f}% at 80% power) cannot be detected at "
                   f"this sample size — absence of significance is not evidence "
                   f"of absence.")
    else:
        out.append("The clustered CI currently excludes zero; this reading "
                   "weakens if new matured events pull the interval back "
                   "across zero, or if event-type decomposition shows the "
                   "pooled effect is driven by a single type.")
    out.append("SEDI ingestion could reveal an insider pattern not visible in "
               "the current Form 4 scope, changing the risk-side reading for "
               "MJDS issuers.")
    out.append("If naive and clustered intervals diverge further as events "
               "accrue, issuer clustering — not the event effect — is doing "
               "the work; per-issuer decomposition becomes the priority.")
    return out

# ------------------------------------------------------------ 5. C6 block
def c6_explainer(ticker, state, rarity_pctile, freshness_days,
                 form4_eligible) -> dict:
    """§9 block, locked vocabulary (no 'validated'; direction = accruing)."""
    return {
        "title": f"C6 POSTURE — {ticker}",
        "rows": [
            ("Rarity", f"{rarity_pctile}th percentile vs historical issuer "
                       f"baseline" if rarity_pctile else "not computed"),
            ("State", state.capitalize() if state else "Not run"),
            ("Direction", "not established — sign confirmation accruing"),
            ("Freshness", f"{freshness_days} day{'s'*(freshness_days!=1)}"),
            ("Inputs", "filing prose, event mix, source timing"),
            ("Excluded", "SEDI insider data" if not form4_eligible
                         else "none for this issuer"),
            ("Research meaning", "unusual evidence configuration that merits "
                                 "review"),
            ("Investment meaning", "none established"),
        ]}

# ------------------------------------------------------------ 6. canvas
class DecisionCanvas:
    def __init__(self, lens, build_id, data_through, inferences,
                 tensions, issuer_rows):
        self.lens, self.build, self.through = lens, build_id, data_through
        self.inf = inferences          # list[CarInference]
        self.tensions = tensions
        self.rows = issuer_rows

    def to_text(self) -> str:
        L = [f"EVIDENCE DECISION CANVAS — {self.lens} · build {self.build} · "
             f"data through {self.through}",
             f"method {METHOD_HASH} (pre-committed clustered-inference spec)"]
        L.append("\nEVENT PERFORMANCE (peer-adjusted, pooled)")
        for i in self.inf:
            L.append(f"  +{i.horizon_day}d  {i.mean_pct:+.1f}%   "
                     f"clustered CI [{i.cluster_ci[0]:+.1f}, {i.cluster_ci[1]:+.1f}]  "
                     f"(naive [{i.naive_ci[0]:+.1f}, {i.naive_ci[1]:+.1f}])  "
                     f"n={i.n_events}/{i.n_clusters} issuers  "
                     f"MDE80={i.mde80_pct:.1f}%   {badge(i)}")
            L.append(f"        wild-cluster CI [{i.wild_ci[0]:+.1f}, "
                     f"{i.wild_ci[1]:+.1f}] · median {i.events_per_cluster_median:g} "
                     f"events/issuer · top-3 issuers {i.top3_cluster_share_pct}% "
                     f"of sample")
        if self.tensions:
            L.append("\nEVIDENCE TENSIONS (rule-detected, not model opinions)")
            for t in self.tensions:
                L.append(f"  {t.issuer}: positive [{', '.join(t.positive)}] vs "
                         f"offsetting [{', '.join(t.offsetting)}]"
                         + (f"; missing [{', '.join(t.missing)}]" if t.missing else ""))
                L.append(f"      → {t.conclusion}")
        i20 = next((x for x in self.inf if x.horizon_day == 20), self.inf[-1])
        L.append("\nWHAT WOULD CHANGE THIS CONCLUSION")
        for s in conclusion_change(i20):
            L.append(f"  · {s}")
        L.append("\nInvestment implication: none established — no buy, sell, "
                 "or alpha conclusion is supported by this page.")
        return "\n".join(L)

    def to_html(self) -> str:
        e = html.escape
        css = """
        .yc{background:#11161d;border:1px solid #232b36;border-radius:10px;
          padding:18px 20px;color:#c9d4e0;font:14px/1.5 -apple-system,Segoe UI,sans-serif;
          margin-top:14px}
        .yc h3{margin:0;color:#e8eef5;font-size:16px}
        .yc .m{font-family:ui-monospace,monospace;font-size:11px;color:#7d8b99}
        .yc table{border-collapse:collapse;width:100%;margin-top:8px;font-size:13px}
        .yc th{font-size:10px;letter-spacing:.1em;color:#8fb996;text-align:left;
          padding:4px 8px;border-bottom:1px solid #232b36}
        .yc td{padding:5px 8px;border-bottom:1px solid #1a212b;
          font-family:ui-monospace,monospace;font-size:12px}
        .yc .b{border:1px solid #3a4654;border-radius:3px;padding:1px 5px;
          font-size:10px;color:#9fb2c4}
        .yc .tens{border-left:3px solid #c9a25f;padding-left:10px;margin:8px 0}
        .yc .tens b{color:#e8eef5}
        .yc ul{margin:6px 0 0 16px}.yc li{margin:3px 0}
        .yc .frozen{margin-top:12px;color:#c9a25f;border-left:3px solid #c9a25f;
          padding-left:9px;font-size:12.5px}
        """
        P = [f"<style>{css}</style><div class='yc'>",
             f"<h3>Evidence Decision Canvas — {e(self.lens)}</h3>",
             f"<div class='m'>build {e(self.build)} · data through "
             f"{e(self.through)} · method {METHOD_HASH} (pre-committed "
             f"clustered-inference spec)</div>",
             "<table><tr><th>HORIZON</th><th>MEAN</th><th>CLUSTERED CI</th>"
             "<th>NAIVE CI</th><th>WILD CI</th><th>N / ISSUERS</th>"
             "<th>MDE 80%</th><th>STATUS</th></tr>"]
        for i in self.inf:
            P.append(f"<tr><td>+{i.horizon_day}d</td><td>{i.mean_pct:+.1f}%</td>"
                     f"<td>[{i.cluster_ci[0]:+.1f}, {i.cluster_ci[1]:+.1f}]</td>"
                     f"<td>[{i.naive_ci[0]:+.1f}, {i.naive_ci[1]:+.1f}]</td>"
                     f"<td>[{i.wild_ci[0]:+.1f}, {i.wild_ci[1]:+.1f}]</td>"
                     f"<td>{i.n_events} / {i.n_clusters}</td>"
                     f"<td>{i.mde80_pct:.1f}%</td>"
                     f"<td><span class='b'>{badge(i)}</span></td></tr>")
        P.append("</table>")
        i0 = self.inf[-1]
        P.append(f"<div class='m' style='margin-top:6px'>median "
                 f"{i0.events_per_cluster_median:g} events/issuer · top-3 "
                 f"issuers {i0.top3_cluster_share_pct}% of sample · clustered "
                 f"CI is primary; naive shown for comparison</div>")
        if self.tensions:
            P.append("<h3 style='font-size:13px;margin-top:14px'>Evidence "
                     "tensions <span class='m'>(rule-detected)</span></h3>")
            for t in self.tensions:
                P.append(f"<div class='tens'><b>{e(t.issuer)}</b> — positive: "
                         f"{e(', '.join(t.positive))}; offsetting: "
                         f"{e(', '.join(t.offsetting))}"
                         + (f"; missing: {e(', '.join(t.missing))}" if t.missing else "")
                         + f"<br><span class='m'>{e(t.conclusion)}</span></div>")
        P.append("<h3 style='font-size:13px;margin-top:14px'>What would change "
                 "this conclusion</h3><ul>")
        for s in conclusion_change(i0):
            P.append(f"<li>{e(s)}</li>")
        P.append("</ul>")
        P.append("<div class='frozen'>Investment implication: none established "
                 "— no buy, sell, or alpha conclusion is supported by this "
                 "page.</div></div>")
        return "".join(P)

# ---------------------------------------------------------------- self-test
def _selftest():
    rng = random.Random(7)
    # T1: independent events -> clustered CI ~ naive CI (widths within 25%)
    ev = [(f"I{i%20}", rng.gauss(0.5, 3)) for i in range(300)]
    a = ClusteredCAR(ev, 20).run()
    wN = a.naive_ci[1] - a.naive_ci[0]; wC = a.cluster_ci[1] - a.cluster_ci[0]
    assert abs(wC - wN) / wN < 0.25, f"T1 widths diverged: {wN} vs {wC}"
    # T2: strong within-issuer correlation -> clustered wider than naive
    ev2 = []
    for i in range(12):
        base = rng.gauss(0, 4)
        ev2 += [(f"J{i}", base + rng.gauss(0, 0.3)) for _ in range(25)]
    b = ClusteredCAR(ev2, 20).run()
    wN2 = b.naive_ci[1] - b.naive_ci[0]; wC2 = b.cluster_ci[1] - b.cluster_ci[0]
    assert wC2 > 1.8 * wN2, f"T2 clustering not detected: {wN2} vs {wC2}"
    # T3: determinism
    c1 = ClusteredCAR(ev2, 20).run(); c2 = ClusteredCAR(ev2, 20).run()
    assert c1 == c2, "T3 determinism violated"
    # T4: few clusters -> UNDERPOWERED
    d = ClusteredCAR([("A", 1.0), ("A", 2.0), ("B", -1.0), ("C", 0.5),
                      ("C", 0.7)], 5).run()
    assert badge(d) == "UNDERPOWERED", "T4 badge rule failed"
    return a, b

if __name__ == "__main__":
    a, b = _selftest()
    print(f"[OK] T1 independent-data sanity · T2 clustering widens CI "
          f"({(b.cluster_ci[1]-b.cluster_ci[0])/(b.naive_ci[1]-b.naive_ci[0]):.1f}x) "
          f"· T3 determinism · T4 badge rule")
    print(f"[OK] METHOD_HASH={METHOD_HASH}  (pre-commitment stamp)\n")

    # ---- demo canvas with realistic XEG-shaped synthetic events (DEMO data)
    rng = random.Random(11)
    issuers = [("SU", 15), ("CNQ", 8), ("CVE", 6), ("IMO", 4), ("TRP", 5),
               ("PPL", 3), ("KEY", 2), ("ARX", 3)]
    ev = [(nm, rng.gauss(-1.2, 5.5)) for nm, k in issuers for _ in range(k)]
    inf5 = ClusteredCAR(ev, 5).run()
    inf20 = ClusteredCAR([(n, c * 1.3) for n, c in ev], 20).run()
    rows = [
        {"ticker": "CNQ", "c6_state": "elevated", "form4_eligible": False,
         "recent_event_types": ["DIVIDEND", "BUYBACK"]},
        {"ticker": "SU", "c6_state": "normal", "form4_eligible": False,
         "recent_event_types": ["GUIDANCE_RAISE"]},
        {"ticker": "TRP", "c6_state": "normal", "form4_eligible": False,
         "recent_event_types": ["REGULATORY"]},
    ]
    tens = TensionEngine().detect(rows)
    cv = DecisionCanvas("XEG", "9a4e99f3", "2026-07-16", [inf5, inf20],
                        tens, rows)
    print(cv.to_text())
    open(os.path.join(tempfile.gettempdir(), "canvas_demo.html"), "w").write(
        "<body style='background:#0b0f14;padding:30px;max-width:860px'>"
        + cv.to_html() + "</body>")
    print("\n[OK] canvas html written")
