"""YUCLAW Validation Lab — statistical utilities (stdlib + numpy only, no scipy).

Everything here is deterministic and documented so results are reproducible:
bootstrap uses a fixed seed; the Student-t CDF is computed via the regularized
incomplete beta function (continued fraction, Numerical Recipes style), exact
to ~1e-10 — not a normal approximation.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

BOOTSTRAP_ITERS = 10_000
BOOTSTRAP_SEED = 20260518  # forward Day 0, fixed for reproducibility


# ---- distributions ----------------------------------------------------------
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the regularized incomplete beta (NR 6.4)."""
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """One-sided survival P(T > t) for Student-t with df degrees of freedom."""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    p = 0.5 * _betai(df / 2.0, 0.5, x)
    return p if t >= 0 else 1.0 - p


def t_pvalue_two_sided(t: float, df: float) -> float:
    return min(1.0, 2.0 * t_sf(abs(t), df))


# ---- moments / one-sample tests ---------------------------------------------
def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def stdev(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def one_sample_t(xs: Sequence[float]) -> dict:
    """H0: mean == 0. Returns mean, t, df, two-sided p, n."""
    n = len(xs)
    if n < 2:
        return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n}
    m, s = mean(xs), stdev(xs)
    if s == 0:
        return {"mean": m, "t": None, "p": None, "n": n}
    t = m / (s / math.sqrt(n))
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(t, n - 1), "n": n}


def bootstrap_ci_mean(xs: Sequence[float], iters: int = BOOTSTRAP_ITERS,
                      alpha: float = 0.05, seed: int = BOOTSTRAP_SEED) -> tuple[float, float] | None:
    """Percentile bootstrap CI for the mean; resamples the observations
    (i.i.d. resampling of periods/events) with a fixed seed."""
    n = len(xs)
    if n < 3:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(rng.choice(xs) for _ in range(n)) / n)
    means.sort()
    lo = means[int((alpha / 2) * iters)]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return (lo, hi)


def newey_west_t(xs: Sequence[float], lag: int) -> dict:
    """t-stat for H0: mean == 0 with Newey-West (Bartlett) HAC standard errors —
    required when observations overlap (e.g. daily ICs at multi-day horizons).
    Returns mean, t, p (two-sided, df = n-1), n, lag."""
    n = len(xs)
    if n < 3:
        return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n, "lag": lag}
    lag = max(0, min(lag, n - 2))
    m = mean(xs)
    e = [x - m for x in xs]
    gamma0 = sum(v * v for v in e) / n
    s = gamma0
    for l in range(1, lag + 1):
        gl = sum(e[i] * e[i - l] for i in range(l, n)) / n
        s += 2.0 * (1.0 - l / (lag + 1.0)) * gl
    if s <= 0:
        return {"mean": m, "t": None, "p": None, "n": n, "lag": lag}
    se = math.sqrt(s / n)
    t = m / se
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(t, n - 1), "n": n, "lag": lag}


# ---- rank statistics ---------------------------------------------------------
def _ranks(xs: Sequence[float]) -> list[float]:
    """Average (fractional) ranks, ties shared."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation (tie-corrected via average ranks)."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return pearson(_ranks(xs), _ranks(ys))


def spearman_pvalue(rho: float, n: int) -> float | None:
    """Two-sided p for Spearman rho via the t approximation
    t = rho*sqrt((n-2)/(1-rho^2)), df = n-2 (standard for n >= ~10)."""
    if rho is None or n < 4 or abs(rho) >= 1.0:
        return None
    t = rho * math.sqrt((n - 2) / (1.0 - rho * rho))
    return t_pvalue_two_sided(t, n - 2)


# ---- OLS (single regressor) --------------------------------------------------
def ols(y: Sequence[float], x: Sequence[float]) -> dict | None:
    """y = alpha + beta*x + eps. Classical (homoskedastic) SEs.
    Returns alpha, beta, se_alpha, se_beta, t_alpha, p_alpha, r2, n, resid_std."""
    n = len(y)
    if n < 3 or len(x) != n:
        return None
    mx, my = mean(x), mean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return None
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    beta = sxy / sxx
    alpha = my - beta * mx
    resid = [y[i] - alpha - beta * x[i] for i in range(n)]
    sse = sum(r * r for r in resid)
    sst = sum((yi - my) ** 2 for yi in y)
    df = n - 2
    s2 = sse / df if df > 0 else float("nan")
    se_beta = math.sqrt(s2 / sxx)
    se_alpha = math.sqrt(s2 * (1.0 / n + mx * mx / sxx))
    t_alpha = alpha / se_alpha if se_alpha > 0 else None
    return {
        "alpha": alpha, "beta": beta,
        "se_alpha": se_alpha, "se_beta": se_beta,
        "t_alpha": t_alpha,
        "p_alpha": t_pvalue_two_sided(t_alpha, df) if t_alpha is not None else None,
        "r2": 1.0 - sse / sst if sst > 0 else None,
        "n": n, "resid_std": math.sqrt(s2),
    }


def mde_alpha_daily(se_alpha: float, df: int, power: float = 0.80,
                    alpha_level: float = 0.05) -> float | None:
    """Minimum detectable daily alpha at the given power/level for the observed
    SE(alpha): |alpha| >= (t_crit + z_power) * SE. Uses z for the power term."""
    if se_alpha is None or se_alpha <= 0 or df < 3:
        return None
    # invert t two-sided critical value by bisection
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_pvalue_two_sided(mid, df) > alpha_level:
            lo = mid
        else:
            hi = mid
    t_crit = (lo + hi) / 2
    z_power = {0.80: 0.8416, 0.90: 1.2816}.get(power, 0.8416)
    return (t_crit + z_power) * se_alpha
