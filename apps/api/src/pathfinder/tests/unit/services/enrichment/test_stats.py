"""The hypergeometric upper tail is exact in log space.

Every expected value is rebuilt from ``math.comb`` inside the test, so the
assertions state the distribution itself and not a recorded output.
"""

from __future__ import annotations

import math

import pytest

from pathfinder.services.enrichment.stats import hypergeometric_log_sf


def _exact_sf(x: int, n: int, k: int, m: int) -> float:
    """Upper tail P(X >= x) as a ratio of integer binomial coefficients."""
    lo = max(0, m + k - n)
    hi = min(k, m)
    favourable = sum(
        math.comb(k, i) * math.comb(n - k, m - i) for i in range(max(x, lo), hi + 1)
    )
    return favourable / math.comb(n, m)


def _normal_approx_log_sf(x: int, n: int, k: int, m: int) -> float:
    """Normal approximation of the same tail, for the accuracy comparison."""
    mean = k * m / n
    var = k * m * (n - k) * (n - m) / (n * n * max(n - 1, 1))
    std = max(math.sqrt(var), 1e-12)
    z = (x - mean) / std
    if z <= 0:
        return 0.0
    return math.log(max(math.erfc(z / math.sqrt(2)) / 2, 1e-300))


def test_the_small_tail_matches_the_integer_binomial_sum() -> None:
    p_value = math.exp(hypergeometric_log_sf(3, 20, 5, 6))

    assert p_value == pytest.approx(_exact_sf(3, 20, 5, 6), rel=1e-12)
    assert p_value == pytest.approx(0.13132094943240455, rel=1e-12)


def test_a_count_at_or_below_the_support_floor_is_certain() -> None:
    assert hypergeometric_log_sf(0, 20, 5, 6) == 0.0
    # 8 successes and 7 draws from 10 always overlap in at least 5.
    assert hypergeometric_log_sf(5, 10, 8, 7) == 0.0
    assert hypergeometric_log_sf(4, 10, 8, 7) == 0.0


def test_the_top_of_the_support_is_the_single_top_term() -> None:
    top_term = math.comb(5, 5) * math.comb(15, 1) / math.comb(20, 6)

    assert math.exp(hypergeometric_log_sf(5, 20, 5, 6)) == pytest.approx(
        top_term, rel=1e-12
    )


def test_a_count_above_the_support_is_impossible() -> None:
    assert hypergeometric_log_sf(6, 20, 5, 6) == -math.inf


def test_the_gene_set_scale_tail_matches_the_exact_value() -> None:
    log_sf = hypergeometric_log_sf(15, 5000, 200, 50)

    assert log_sf == pytest.approx(math.log(_exact_sf(15, 5000, 200, 50)), rel=1e-9)
    assert math.exp(log_sf) == pytest.approx(4.1687880222280645e-10, rel=1e-9)


def test_the_normal_approximation_is_orders_of_magnitude_smaller() -> None:
    exact = math.exp(hypergeometric_log_sf(15, 5000, 200, 50))
    approximate = math.exp(_normal_approx_log_sf(15, 5000, 200, 50))

    assert math.log10(exact / approximate) > 3


def test_the_normal_approximation_crosses_the_significance_line() -> None:
    exact = math.exp(hypergeometric_log_sf(3, 20, 5, 6))
    approximate = math.exp(_normal_approx_log_sf(3, 20, 5, 6))

    assert exact > 0.05
    assert approximate < 0.05


def test_the_tail_shrinks_as_the_observed_count_grows() -> None:
    tail = [hypergeometric_log_sf(x, 5000, 200, 50) for x in range(1, 12)]

    assert tail == sorted(tail, reverse=True)
    assert len(set(tail)) == len(tail)


def test_the_tail_is_symmetric_in_successes_and_draws() -> None:
    assert hypergeometric_log_sf(15, 5000, 200, 50) == pytest.approx(
        hypergeometric_log_sf(15, 5000, 50, 200), rel=1e-12
    )
    assert hypergeometric_log_sf(3, 20, 5, 6) == pytest.approx(
        hypergeometric_log_sf(3, 20, 6, 5), rel=1e-12
    )


@pytest.mark.parametrize(("n", "k", "m"), [(10, 5, 11), (10, 11, 5), (0, 1, 1)])
def test_parameters_that_are_not_a_distribution_are_rejected(
    n: int, k: int, m: int
) -> None:
    with pytest.raises(ValueError, match="hypergeometric"):
        hypergeometric_log_sf(1, n, k, m)
