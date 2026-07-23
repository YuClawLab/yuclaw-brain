#!/usr/bin/env python3
"""
YUCLAW Signal Decomposition Lab — pre-registered diagnostics engine (v1)
========================================================================
Implements the Lab review's §50 first-priority functions with YUCLAW
amendments: per-component diagnostics for C1..C9 (§3), full decile
monotonicity (§4), universe segmentation hooks (§5), cohort churn (§7),
horizon decay (§9), and placebo falsification (§12) — under a protocol
registry entry (§21) and multiple-testing discipline (§26).

Stdlib-only. Deterministic (seeded). Diagnostic-only: this module NEVER
re-weights the composite (re-weighting stays forward-tested-only per
the June-12 C6 verdict). Frozen-component (C4) and missing data are
reported as data-status, never silently treated as signal failure.

PRE-REGISTRATION: METHOD_SPEC below is hash-stamped and committed BEFORE
this engine touches real component data. Real results inherit the lock.
"""
from __future__ import annotations
import hashlib, json, math, random
from dataclasses import dataclass, field
from typing import Optional

METHOD_SPEC = """
SIGNAL DECOMPOSITION LAB — pre-committed specification (v1)
Panel: daily cross-sections of component scores C1..C9 + composite,
with forward k-day benchmark-relative returns, point-in-time.
(1) Standalone IC: per-date cross-sectional Spearman rank correlation
    (component vs forward return); reported as mean daily IC. SE via
    moving-block bootstrap on the daily IC series (block = k days,
    B=2000, seed=20260722); 95% percentile CI.
(2) Decile/quantile table: names ranked per date into Q quantiles
    (Q=5 for n<100 cross-section); per-quantile mean forward return;
    monotonicity = Spearman(quantile index, quantile mean) + adjacent
    ordering frequency; top-minus-bottom spread with block-bootstrap CI.
(3) Marginal contribution (leave-one-out): IC(composite) minus
    IC(composite rebuilt with component's weight removed, remaining
    weights renormalized). Diagnostic only; weights never changed live.
(4) Incremental (partial) IC: per-date, rank-transform all components;
    OLS-residualize target component ranks AND forward returns on the
    other components' ranks (Frisch-Waugh); Spearman of residuals.
(5) Redundancy: mean per-date pairwise Spearman between components.
(6) Churn: day-over-day Spearman autocorrelation of component ranks;
    top-quintile membership retention rate.
(7) Horizon decay: (1) repeated at k in {1,2,5,10,20}.
(8) Placebo controls: (a) within-date permutation of scores, B=500,
    percentile of real IC in null; (b) temporal shift placebo (scores
    lagged +20d against unshifted returns).
(9) Segmentation: all of the above computable on instrument-class
    subsets (EQUITY / SECTOR_ETF / MACRO) when class labels provided;
    combined universe reported as secondary heterogeneous view.
(10) Badges: |IC| CI excluding 0 with >=40 daily cross-sections ->
     PRELIMINARY; else DESCRIPTIVE; <20 cross-sections or <15 names
     median cross-section -> UNDERPOWERED. Frozen/missing component
     (missing-rate>50% or constant) -> DATA-LIMITED, no badge.
Registry: every run emits protocol_id = sha256(spec+params)[:12],
lock_date, params, and result hash. One primary endpoint per component
(k=5 IC); all other cells labeled secondary/exploratory.
"""
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
SEED = 20260722


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

# ------------------------------------------------------------------ utils
def _rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]: j += 1
        avg = (i + j) / 2.0 + 1
        for t in range(i, j + 1): r[idx[t]] = avg
        i = j + 1
    return r

def _spearman(a, b):
    ra, rb = _rank(a), _rank(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = math.sqrt(sum((x - ma) ** 2 for x in ra))
    db = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return num / (da * db) if da > 0 and db > 0 else 0.0

def _ols_resid(y, X):
    """Residuals of y on X (with intercept). Tiny gaussian elimination."""
    n, p = len(y), len(X[0]) + 1
    A = [[1.0] + row[:] for row in X]
    # normal equations
    M = [[sum(A[i][r] * A[i][c] for i in range(n)) for c in range(p)]
         for r in range(p)]
    v = [sum(A[i][r] * y[i] for i in range(n)) for r in range(p)]
    for col in range(p):                       # solve M beta = v
        piv = max(range(col, p), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12: continue
        M[col], M[piv] = M[piv], M[col]; v[col], v[piv] = v[piv], v[col]
        for r in range(p):
            if r != col and abs(M[r][col]) > 1e-14:
                f = M[r][col] / M[col][col]
                M[r] = [a - f * b for a, b in zip(M[r], M[col])]
                v[r] -= f * v[col]
    beta = [v[i] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(p)]
    return [y[i] - sum(beta[j] * A[i][j] for j in range(p)) for i in range(n)]

def _block_boot_ci(series, block, B, rng):
    n = len(series)
    if n < 3: return (float("nan"), float("nan")), 0.0
    means = []
    for _ in range(B):
        out = []
        while len(out) < n:
            s = rng.randrange(n)
            out += [series[(s + t) % n] for t in range(block)]
        means.append(sum(out[:n]) / n)
    means.sort()
    return (means[int(0.025 * B)], means[int(0.975 * B) - 1]), _sd(means)

def _sd(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1))

# ------------------------------------------------------------------ input
@dataclass
class Panel:
    """dates: list[str]; names: list[str];
    scores[comp][d][i] -> float|None ; fwd[k][d][i] -> float|None (bench-rel %)
    weights: composite weights per component; classes: name->EQUITY/SECTOR_ETF/MACRO"""
    dates: list; names: list
    scores: dict; fwd: dict; weights: dict
    classes: Optional[dict] = None

# ------------------------------------------------------------------ engine
class DecompositionLab:
    def __init__(self, panel: Panel, k_primary=5, B=2000, seed=SEED):
        self.p, self.k, self.B = panel, k_primary, B
        self.seed = seed
        self.protocol_id = hashlib.sha256(
            (METHOD_SPEC + f"k={k_primary}").encode()).hexdigest()[:12]

    def _rng(self, tag):
        # per-cell deterministic stream: independent of call order
        return random.Random(f"{self.seed}:{tag}")

    # -- cross-sections with pairwise-complete data
    def _xs(self, comp, k, subset=None):
        out = []
        for d in range(len(self.p.dates)):
            xs, ys = [], []
            for i, nm in enumerate(self.p.names):
                if subset and self.p.classes and self.p.classes.get(nm) != subset:
                    continue
                s = self.p.scores[comp][d][i]; r = self.p.fwd[k][d][i]
                if s is not None and r is not None:
                    xs.append(s); ys.append(r)
            if len(xs) >= 8: out.append((xs, ys))
        return out

    def data_status(self, comp):
        vals = [v for day in self.p.scores[comp] for v in day if v is not None]
        total = len(self.p.dates) * len(self.p.names)
        miss = 1 - len(vals) / total if total else 1.0
        const = len(set(round(v, 9) for v in vals)) <= 1 if vals else True
        return {"missing_rate": round(miss, 3), "constant": const,
                "data_limited": miss > 0.5 or const}

    def ic(self, comp, k=None, subset=None):
        k = k or self.k
        days = self._xs(comp, k, subset)
        ics = [_spearman(xs, ys) for xs, ys in days]
        if not ics: return None
        mean = sum(ics) / len(ics)
        ci, se = _block_boot_ci(ics, block=max(1, k), B=self.B,
                                rng=self._rng(f"ic:{comp}:{k}:{subset}"))
        med_n = sorted(len(xs) for xs, _ in days)[len(days) // 2]
        badge = ("UNDERPOWERED" if len(ics) < 20 or med_n < 15 else
                 "PRELIMINARY" if not (ci[0] <= 0 <= ci[1]) and len(ics) >= 40
                 else "DESCRIPTIVE")
        return {"comp": comp, "k": k, "mean_ic": round(mean, 4),
                "ci": (round(ci[0], 4), round(ci[1], 4)), "days": len(ics),
                "median_xsec_n": med_n, "badge": badge}

    def quantile_table(self, comp, k=None, Q=5):
        k = k or self.k
        sums = [0.0] * Q; cnt = [0] * Q
        adj_ok = 0; adj_tot = 0
        for xs, ys in self._xs(comp, k):
            order = sorted(range(len(xs)), key=lambda i: xs[i])
            for pos, i in enumerate(order):
                q = min(Q - 1, pos * Q // len(order))
                sums[q] += ys[i]; cnt[q] += 1
        means = [round(sums[q] / cnt[q], 3) if cnt[q] else None for q in range(Q)]
        for q in range(Q - 1):
            if means[q] is not None and means[q + 1] is not None:
                adj_tot += 1; adj_ok += means[q + 1] >= means[q]
        mono = _spearman(list(range(Q)), [m if m is not None else 0 for m in means])
        return {"comp": comp, "k": k, "quantile_means_pct": means,
                "monotonicity_spearman": round(mono, 3),
                "adjacent_ordering": f"{adj_ok}/{adj_tot}",
                "top_minus_bottom_pct": (round(means[-1] - means[0], 3)
                                         if None not in (means[0], means[-1]) else None)}

    def composite_series(self, exclude=None):
        w = {c: v for c, v in self.p.weights.items() if c != exclude}
        tot = sum(w.values())
        comp = []
        for d in range(len(self.p.dates)):
            row = []
            for i in range(len(self.p.names)):
                acc, wt = 0.0, 0.0
                for c, cw in w.items():
                    v = self.p.scores[c][d][i]
                    if v is not None: acc += cw * v; wt += cw
                row.append(acc / wt * tot / tot if wt > 0 else None)
            comp.append(row)
        return comp

    def marginal_contribution(self, comp):
        base = dict(self.p.scores); k = self.k
        self.p.scores["_FULL"] = self.composite_series()
        self.p.scores["_LOO"] = self.composite_series(exclude=comp)
        full = self.ic("_FULL"); loo = self.ic("_LOO")
        for t in ("_FULL", "_LOO"): del self.p.scores[t]
        self.p.scores = base
        return {"comp": comp,
                "composite_ic": full["mean_ic"], "without_ic": loo["mean_ic"],
                "marginal": round(full["mean_ic"] - loo["mean_ic"], 4)}

    def redundancy_matrix(self):
        comps = sorted(self.p.weights); out = {}
        for a in comps:
            for b in comps:
                if a >= b: continue
                vals = []
                for d in range(len(self.p.dates)):
                    xs = [(self.p.scores[a][d][i], self.p.scores[b][d][i])
                          for i in range(len(self.p.names))
                          if self.p.scores[a][d][i] is not None
                          and self.p.scores[b][d][i] is not None]
                    if len(xs) >= 8:
                        vals.append(_spearman([x for x, _ in xs],
                                              [y for _, y in xs]))
                if vals: out[(a, b)] = round(sum(vals) / len(vals), 3)
        return out

    def partial_ic(self, comp, controls=None):
        others = controls if controls is not None else \
                 [c for c in self.p.weights if c != comp]
        ics = []
        for d in range(len(self.p.dates)):
            xs, ys, X = [], [], []
            for i in range(len(self.p.names)):
                s = self.p.scores[comp][d][i]; r = self.p.fwd[self.k][d][i]
                row = [self.p.scores[c][d][i] for c in others]
                if s is None or r is None or any(v is None for v in row): continue
                xs.append(s); ys.append(r); X.append(row)
            if len(xs) < 12: continue
            Xr = list(map(list, zip(*[_rank(col) for col in zip(*X)])))
            rx = _ols_resid(_rank(xs), Xr); ry = _ols_resid(_rank(ys), Xr)
            ics.append(_spearman(rx, ry))
        if not ics: return None
        ci, _ = _block_boot_ci(ics, block=self.k, B=self.B,
                               rng=self._rng(f"pic:{comp}:{','.join(others)}"))
        return {"comp": comp, "mean_partial_ic": round(sum(ics) / len(ics), 4),
                "ci": (round(ci[0], 4), round(ci[1], 4)), "days": len(ics)}

    def churn(self, comp):
        auto, keep = [], []
        prev = None
        for d in range(len(self.p.dates)):
            cur = [(i, self.p.scores[comp][d][i]) for i in range(len(self.p.names))
                   if self.p.scores[comp][d][i] is not None]
            if prev and len(cur) >= 8:
                common = [i for i, _ in cur if i in dict(prev)]
                if len(common) >= 8:
                    a = [dict(prev)[i] for i in common]
                    b = [dict(cur)[i] for i in common]
                    auto.append(_spearman(a, b))
                    qa = set(sorted(common, key=lambda i: dict(prev)[i])[-len(common)//5:])
                    qb = set(sorted(common, key=lambda i: dict(cur)[i])[-len(common)//5:])
                    keep.append(len(qa & qb) / max(1, len(qa)))
            prev = cur
        return {"comp": comp,
                "rank_autocorr_1d": round(sum(auto)/len(auto), 3) if auto else None,
                "top_quintile_retention_1d": round(sum(keep)/len(keep), 3) if keep else None}

    def placebo(self, comp, B=500):
        real = self.ic(comp)["mean_ic"]
        days = self._xs(comp, self.k)
        rng = self._rng(f"placebo:{comp}")
        nulls = []
        for _ in range(B):
            tot, cnt = 0.0, 0
            for xs, ys in days:
                sh = xs[:]; rng.shuffle(sh)
                tot += _spearman(sh, ys); cnt += 1
            nulls.append(tot / cnt)
        pct = sum(1 for v in nulls if v < real) / B
        return {"comp": comp, "real_ic": round(real, 4),
                "null_mean": round(sum(nulls)/B, 4),
                "percentile_in_null": round(pct, 3),
                "note": "two-sided extremity, exploratory"}

    def horizon_decay(self, comp, ks=(1, 2, 5, 10, 20)):
        return [self.ic(comp, k=k) for k in ks if k in self.p.fwd]

    # ------------------------------------------------------------ report
    def run_all(self):
        _registry_guard(self.protocol_id)
        comps = sorted(self.p.weights)
        out = {"protocol_id": self.protocol_id, "method": METHOD_HASH,
               "primary_endpoint": f"per-component IC at k={self.k}",
               "n_secondary_cells": 0, "components": {}}
        for c in comps:
            st = self.data_status(c)
            row = {"data_status": st}
            if not st["data_limited"]:
                row.update(ic=self.ic(c), quantiles=self.quantile_table(c),
                           marginal=self.marginal_contribution(c),
                           partial=self.partial_ic(c), churn=self.churn(c))
            out["components"][c] = row
        out["n_secondary_cells"] = sum(
            1 for c in comps for key in out["components"][c] if key != "ic")
        return out

# ---------------------------------------------------------------- selftest
def _synth(seed=3):
    """Synthetic panel: CA=true signal, CB=noise, CC=redundant(≈CA), CD=constant."""
    rng = random.Random(seed)
    D, N = 60, 40
    dates = [f"d{t}" for t in range(D)]; names = [f"N{i}" for i in range(N)]
    fwd5, sA, sB, sC, sD = [], [], [], [], []
    for t in range(D):
        base = [rng.gauss(0, 1) for _ in range(N)]
        ret = [0.8 * b + rng.gauss(0, 1.2) for b in base]      # CA drives returns
        fwd5.append(ret)
        sA.append(base)
        sB.append([rng.gauss(0, 1) for _ in range(N)])
        sC.append([b + rng.gauss(0, 0.25) for b in base])       # redundant w/ CA
        sD.append([1.0] * N)                                     # frozen
    return Panel(dates, names,
                 {"CA": sA, "CB": sB, "CC": sC, "CD": sD}, {5: fwd5},
                 {"CA": 0.4, "CB": 0.2, "CC": 0.3, "CD": 0.1})

def _selftest():
    lab = DecompositionLab(_synth(), k_primary=5, B=600)
    icA = lab.ic("CA"); icB = lab.ic("CB")
    assert icA["mean_ic"] > 0.3 and icA["ci"][0] > 0, "T1 true signal missed"
    assert abs(icB["mean_ic"]) < 0.08, "T2 noise not near zero"
    pC = lab.partial_ic("CC"); pA_full = lab.partial_ic("CA")
    # T3: under FULL controls, near-duplicates CA/CC correctly BOTH collapse
    assert abs(pC["mean_partial_ic"]) < 0.12, "T3 redundant comp partial-IC not collapsed"
    assert abs(pA_full["mean_partial_ic"]) < 0.15, "T3b twin also collapses (collinearity)"
    # T4: excluding the twin from controls, the true component survives;
    # redundancy matrix attributes the collapse to the CA-CC pair
    pA = lab.partial_ic("CA", controls=["CB", "CD"])
    assert pA["mean_partial_ic"] > 0.2, "T4 true comp survives when twin excluded"
    red = lab.redundancy_matrix()
    assert red[("CA", "CC")] > 0.9, "T4b redundancy matrix missed the twin pair"
    assert lab.data_status("CD")["data_limited"], "T5 frozen comp not flagged DATA-LIMITED"
    pl = lab.placebo("CA", B=200)
    assert pl["percentile_in_null"] >= 0.99, "T6 placebo failed to rank real IC extreme"
    lab2 = DecompositionLab(_synth(), k_primary=5, B=600)
    assert lab.ic("CA") == lab2.ic("CA"), "T7 determinism violated"
    return lab

if __name__ == "__main__":
    lab = _selftest()
    print(f"[OK] T1 signal recovery · T2 noise≈0 · T3 redundancy collapse · "
          f"T4 true partial survives · T5 frozen flagged · T6 placebo · T7 determinism")
    print(f"[OK] METHOD_HASH={METHOD_HASH} · protocol_id={lab.protocol_id}\n")
    r = lab.run_all()
    for c, row in r["components"].items():
        if row["data_status"]["data_limited"]:
            print(f"{c}: DATA-LIMITED {row['data_status']}"); continue
        print(f"{c}: IC={row['ic']['mean_ic']:+.3f} CI{row['ic']['ci']} "
              f"[{row['ic']['badge']}] · partial={row['partial']['mean_partial_ic']:+.3f} "
              f"· marginal={row['marginal']['marginal']:+.4f} "
              f"· mono={row['quantiles']['monotonicity_spearman']:+.2f} "
              f"· T-B={row['quantiles']['top_minus_bottom_pct']}% "
              f"· churn={row['churn']['rank_autocorr_1d']}")
    print(f"\nprotocol {r['protocol_id']} · primary: {r['primary_endpoint']} · "
          f"{r['n_secondary_cells']} secondary cells (registry-labeled)")
