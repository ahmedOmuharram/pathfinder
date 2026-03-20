"""Tests for bootstrap robustness and uncertainty estimation."""

import random
from collections import defaultdict

from veupath_chatbot.services.experiment.robustness import (
    BootstrapOptions,
    _ci_from_samples,
    _collect_classification_metrics,
    _mean_jaccard,
    _resample,
    compute_robustness,
)
from veupath_chatbot.services.experiment.types import ConfidenceInterval


class TestResample:
    def test_same_length(self) -> None:
        rng = random.Random(42)
        items = ["a", "b", "c", "d"]
        result = _resample(items, rng)
        assert len(result) == len(items)

    def test_empty_list(self) -> None:
        rng = random.Random(42)
        assert _resample([], rng) == []

    def test_deterministic_with_seed(self) -> None:
        items = ["a", "b", "c", "d", "e"]
        result1 = _resample(items, random.Random(0))
        result2 = _resample(items, random.Random(0))
        assert result1 == result2

    def test_samples_from_original(self) -> None:
        rng = random.Random(99)
        items = ["x", "y", "z"]
        result = _resample(items, rng)
        assert all(item in items for item in result)


class TestCollectClassificationMetrics:
    def test_perfect_classification(self) -> None:
        result_ids = ["g1", "g2", "g3"]
        pos_set = {"g1", "g2"}
        neg_set = {"n1", "n2"}
        samples: dict[str, list[float]] = defaultdict(list)
        _collect_classification_metrics(result_ids, pos_set, neg_set, samples)

        assert samples["sensitivity"] == [1.0]  # all pos found
        assert samples["specificity"] == [1.0]  # no neg found
        assert samples["precision"] == [1.0]  # tp / (tp + fp) = 2/2

    def test_no_positives_found(self) -> None:
        result_ids = ["n1", "n2"]
        pos_set = {"g1", "g2"}
        neg_set = {"n1", "n2"}
        samples: dict[str, list[float]] = defaultdict(list)
        _collect_classification_metrics(result_ids, pos_set, neg_set, samples)

        assert samples["sensitivity"] == [0.0]
        assert samples["specificity"] == [0.0]  # all neg found
        assert samples["precision"] == [0.0]

    def test_accumulates_samples(self) -> None:
        result_ids = ["g1", "n1"]
        pos_set = {"g1"}
        neg_set = {"n1"}
        samples: dict[str, list[float]] = defaultdict(list, {"sensitivity": [0.5]})
        _collect_classification_metrics(result_ids, pos_set, neg_set, samples)

        # Should append, not replace
        assert len(samples["sensitivity"]) == 2

    def test_empty_sets(self) -> None:
        samples: dict[str, list[float]] = defaultdict(list)
        _collect_classification_metrics([], set(), set(), samples)
        assert samples["sensitivity"] == [0.0]
        assert samples["f1_score"] == [0.0]


class TestCiFromSamples:
    def test_empty_samples(self) -> None:
        ci = _ci_from_samples([])
        assert ci == ConfidenceInterval(lower=0.0, mean=0.0, upper=0.0, std=0.0)

    def test_single_value(self) -> None:
        ci = _ci_from_samples([0.5])
        assert ci.mean == 0.5
        assert ci.lower == 0.5
        assert ci.upper == 0.5
        assert ci.std == 0.0

    def test_uniform_values(self) -> None:
        ci = _ci_from_samples([0.8] * 100)
        assert ci.mean == 0.8
        assert ci.std == 0.0
        assert ci.lower == 0.8
        assert ci.upper == 0.8

    def test_spread_values(self) -> None:
        samples = list(range(100))
        ci = _ci_from_samples([float(x) for x in samples])
        assert ci.mean == 49.5
        assert ci.lower < ci.mean
        assert ci.upper > ci.mean
        assert ci.std > 0


class TestMeanJaccard:
    def test_single_set(self) -> None:
        assert _mean_jaccard([{"a", "b"}]) == 1.0

    def test_empty_list(self) -> None:
        assert _mean_jaccard([]) == 1.0

    def test_identical_sets(self) -> None:
        sets = [{"a", "b", "c"} for _ in range(10)]
        assert _mean_jaccard(sets) == 1.0

    def test_disjoint_sets(self) -> None:
        sets = [{f"g{i}"} for i in range(50)]
        result = _mean_jaccard(sets)
        assert result == 0.0

    def test_partial_overlap(self) -> None:
        # Two sets: {a, b, c} and {b, c, d} -> J = 2/4 = 0.5
        sets = [{"a", "b", "c"}, {"b", "c", "d"}]
        result = _mean_jaccard(sets)
        assert result == 0.5


class TestComputeRobustness:
    def test_basic_output_structure(self) -> None:
        result_ids = ["g1", "g2", "g3", "n1", "n2"]
        positive_ids = ["g1", "g2", "g3"]
        negative_ids = ["n1", "n2"]
        br = compute_robustness(
            result_ids,
            positive_ids,
            negative_ids,
            BootstrapOptions(n_bootstrap=10, seed=42),
        )
        assert br.n_iterations == 10
        assert "sensitivity" in br.metric_cis
        assert "specificity" in br.metric_cis
        assert "precision" in br.metric_cis
        assert "f1_score" in br.metric_cis

    def test_rank_metric_cis_present(self) -> None:
        result_ids = [f"g{i}" for i in range(20)]
        positive_ids = ["g0", "g1", "g2"]
        negative_ids = ["g10", "g11", "g12"]
        br = compute_robustness(
            result_ids,
            positive_ids,
            negative_ids,
            BootstrapOptions(n_bootstrap=10, k_values=[10], seed=42),
        )
        assert "precision_at_10" in br.rank_metric_cis
        assert "recall_at_10" in br.rank_metric_cis
        assert "enrichment_at_10" in br.rank_metric_cis

    def test_top_k_stability_range(self) -> None:
        result_ids = [f"g{i}" for i in range(100)]
        positive_ids = [f"g{i}" for i in range(10)]
        negative_ids = [f"g{i}" for i in range(50, 60)]
        br = compute_robustness(
            result_ids,
            positive_ids,
            negative_ids,
            BootstrapOptions(n_bootstrap=20, seed=42),
        )
        assert 0.0 <= br.top_k_stability <= 1.0

    def test_deterministic_with_seed(self) -> None:
        args = (
            ["g1", "g2", "n1"],
            ["g1", "g2"],
            ["n1"],
        )
        br1 = compute_robustness(
            *args, options=BootstrapOptions(n_bootstrap=50, seed=123)
        )
        br2 = compute_robustness(
            *args, options=BootstrapOptions(n_bootstrap=50, seed=123)
        )
        assert br1.metric_cis["sensitivity"].mean == br2.metric_cis["sensitivity"].mean

    def test_skip_rank_metrics(self) -> None:
        result_ids = ["g1", "g2", "n1"]
        br = compute_robustness(
            result_ids,
            ["g1"],
            ["n1"],
            BootstrapOptions(n_bootstrap=10, include_rank_metrics=False, seed=42),
        )
        assert br.rank_metric_cis == {}
        assert br.top_k_stability == 0.0
        assert "sensitivity" in br.metric_cis

    def test_alternative_negatives(self) -> None:
        result_ids = [f"g{i}" for i in range(20)]
        positive_ids = ["g0", "g1"]
        negative_ids = ["g10", "g11"]
        alt_negs = {"random": ["g12", "g13", "g14"]}
        br = compute_robustness(
            result_ids,
            positive_ids,
            negative_ids,
            BootstrapOptions(n_bootstrap=10, seed=42, alternative_negatives=alt_negs),
        )
        assert len(br.negative_set_sensitivity) == 1
        assert br.negative_set_sensitivity[0].label == "random"
        assert br.negative_set_sensitivity[0].negative_count == 3
