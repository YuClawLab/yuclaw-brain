"""Small, auditable statistical primitives (adapted verbatim in substance from the preview; V8-005).

Sequential evidence is a fixed mixture of Hoeffding test supermartingales,
not an implementation of any watermark or reasoning-stopping algorithm.
"""
from __future__ import annotations

import math

LAMBDAS = (0.0625, 0.125, 0.25, 0.5, 1.0)


def finite(value, name="value", low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"{name} outside permitted finite range [{low}, {high}]")
    return value


def log_e_value(n: int, total: float, null_mean: float = 0.0) -> float:
    """For X in [-1,1], H0: E[X_t | F_(t-1)] <= null_mean at every t.

    Hoeffding's lemma gives exp(lambda*(X-mu)-lambda**2/2). Mixing
    fixed positive lambdas preserves the supermartingale property. Log space
    prevents overflow even after long runs. No data-dependent lambda tuning.
    """
    if type(n) is not int or n < 0:
        raise ValueError("n must be a nonnegative integer")
    total = finite(total, "total", -n, n)
    null_mean = finite(null_mean, "null_mean", -1, 1)
    terms = [lam * (total - n * null_mean) - n * lam * lam / 2 for lam in LAMBDAS]
    peak = max(terms)
    return peak + math.log(math.fsum(math.exp(v - peak) for v in terms) / len(terms))


def brier_improvement(baseline: float, candidate: float, outcome: int) -> float:
    baseline = finite(baseline, "baseline_probability", 0, 1)
    candidate = finite(candidate, "candidate_probability", 0, 1)
    if type(outcome) is not int or outcome not in (0, 1):
        raise ValueError("outcome must be integer 0 or 1")
    return (baseline - outcome) ** 2 - (candidate - outcome) ** 2


def by_adjust(p_values):
    """Benjamini–Yekutieli adjusted p-values for a FIXED complete family.

    Arbitrary dependence is permitted; each input still must be a valid
    p-value. Cannot repair optional stopping, cherry-picking, or missing tests.
    """
    values = [finite(p, "p-value", 0, 1) for p in p_values]
    m = len(values)
    correction = math.fsum(1 / j for j in range(1, m + 1))
    order = sorted(range(m), key=lambda i: (values[i], i))
    adjusted, running = [1.0] * m, 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, m * correction * values[i] / rank)
        adjusted[i] = running
    return adjusted
