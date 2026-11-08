"""Small, dependency-free statistics used for situation detection.

Wilson score interval for a binomial proportion, and an exact one-sided binomial
test of the observed dispute count against the baseline rate.
"""
from __future__ import annotations

import math


def wilson_ci(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95% Wilson interval for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _log_binom_pmf(i: int, n: int, p: float) -> float:
    return (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p))


def binomial_upper_p(k: int, n: int, p0: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p0). One-sided: is the rate elevated?"""
    if k <= 0:
        return 1.0
    if p0 <= 0:
        return 0.0
    logs = [_log_binom_pmf(i, n, p0) for i in range(k, n + 1)]
    m = max(logs)
    return min(1.0, math.exp(m) * sum(math.exp(x - m) for x in logs))


def fisher_upper_p(k: int, n: int, baseline_k: int, baseline_n: int) -> float:
    """One-sided Fisher exact test: is the first cohort's event rate higher?

    Unlike plugging an estimated baseline into a binomial test, this accounts
    for sampling uncertainty in both cohorts, including a zero-event baseline.
    """
    if not (0 <= k <= n and 0 <= baseline_k <= baseline_n):
        raise ValueError("Event counts must be between zero and cohort size.")
    if not n or not baseline_n or not k:
        return 1.0
    total, events = n + baseline_n, k + baseline_k

    def log_choose(a: int, b: int) -> float:
        return math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(a - b + 1)

    denominator = log_choose(total, n)
    logs = [log_choose(events, x) + log_choose(total - events, n - x) - denominator
            for x in range(k, min(n, events) + 1)]
    peak = max(logs)
    return min(1.0, math.exp(peak) * math.fsum(math.exp(x - peak) for x in logs))
