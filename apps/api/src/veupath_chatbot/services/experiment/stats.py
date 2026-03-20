"""Shared statistical utilities for experiment analysis."""

import math


def hypergeometric_log_sf(x: int, n: int, k: int, m: int) -> float:
    """Approximate log survival function for hypergeometric distribution.

    Uses a normal approximation of P(X >= x) for speed.  Returns 0.0
    (i.e. p=1.0) when the observed count is at or below the mean.

    Parameters
    ----------
    x:
        Number of observed successes.
    n:
        Population size (background).
    k:
        Number of success states in the population (result set size).
    m:
        Number of draws (gene set size).
    """
    mean = k * m / n
    var = k * m * (n - k) * (n - m) / (n * n * max(n - 1, 1))
    std = max(math.sqrt(var), 1e-12)
    z = (x - mean) / std
    if z <= 0:
        return 0.0  # no enrichment -> p = 1.0
    return math.log(max(math.erfc(z / math.sqrt(2)) / 2, 1e-300))
