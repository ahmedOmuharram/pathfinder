"""Tests for shared statistical utilities."""

import math

from veupath_chatbot.services.enrichment.stats import hypergeometric_log_sf


class TestHypergeometricLogSf:
    def test_no_enrichment_returns_zero(self) -> None:
        """When observed is at or below the mean, log_sf = 0 (p=1)."""
        # mean = k*m/n = 50*100/1000 = 5
        # x = 3 < 5 -> no enrichment
        result = hypergeometric_log_sf(x=3, n=1000, k=50, m=100)
        assert result == 0.0

    def test_strong_enrichment_returns_negative(self) -> None:
        """Strong enrichment should give a very negative log_sf."""
        # mean = 50*100/1000 = 5, x = 30 >> 5
        result = hypergeometric_log_sf(x=30, n=1000, k=50, m=100)
        assert result < 0.0
        # p-value should be extremely small
        p = math.exp(result)
        assert p < 0.001

    def test_moderate_enrichment(self) -> None:
        """Moderate enrichment: x slightly above mean."""
        # mean = 10*100/1000 = 1
        result = hypergeometric_log_sf(x=3, n=1000, k=10, m=100)
        assert result < 0.0

    def test_exact_at_mean(self) -> None:
        """At exactly the mean, z <= 0, so log_sf = 0."""
        # mean = 100*100/1000 = 10
        result = hypergeometric_log_sf(x=10, n=1000, k=100, m=100)
        assert result == 0.0

    def test_below_mean(self) -> None:
        """Below mean, should return 0 (no enrichment)."""
        result = hypergeometric_log_sf(x=0, n=1000, k=100, m=100)
        assert result == 0.0

    def test_result_is_finite(self) -> None:
        """Even extreme values should produce finite results."""
        result = hypergeometric_log_sf(x=100, n=1000, k=100, m=100)
        assert math.isfinite(result)
        assert result < 0.0

    def test_small_population(self) -> None:
        """Works with small population size (n-1 clamp)."""
        result = hypergeometric_log_sf(x=1, n=1, k=1, m=1)
        # Population of 1: n=1, k=1, m=1, mean=1, x=1 -> at mean
        assert result == 0.0

    def test_p_value_bounded(self) -> None:
        """The exp of log_sf should produce a valid probability."""
        result = hypergeometric_log_sf(x=50, n=500, k=100, m=200)
        p = math.exp(result)
        assert 0.0 <= p <= 1.0
