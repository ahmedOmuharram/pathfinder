"""Unit tests for rank-based evaluation metrics."""

from __future__ import annotations

from veupath_chatbot.services.experiment.rank_metrics import compute_rank_metrics


class TestComputeRankMetrics:
    def test_perfect_ranking(self) -> None:
        """All positives at the top of the list."""
        result_ids = ["g1", "g2", "g3", "g4", "g5"]
        positive_ids = {"g1", "g2", "g3"}
        negative_ids = {"g4", "g5"}

        rm = compute_rank_metrics(
            result_ids,
            positive_ids,
            negative_ids,
            k_values=[3, 5],
        )

        # P@3 should be 1.0 (all 3 positives in top 3)
        assert rm.precision_at_k[3] == 1.0
        # R@5 should be 1.0 (all positives found)
        assert rm.recall_at_k[5] == 1.0
        assert rm.total_results == 5

    def test_worst_ranking(self) -> None:
        """All positives at the bottom of the list."""
        result_ids = ["n1", "n2", "n3", "g1", "g2"]
        positive_ids = {"g1", "g2"}
        negative_ids = {"n1", "n2", "n3"}

        rm = compute_rank_metrics(
            result_ids,
            positive_ids,
            negative_ids,
            k_values=[3, 5],
        )

        assert rm.precision_at_k[3] == 0.0
        assert rm.recall_at_k[5] == 1.0

    def test_empty_result_list(self) -> None:
        rm = compute_rank_metrics([], {"g1"}, {"n1"})
        assert rm.total_results == 0
        assert rm.precision_at_k == {}

    def test_no_positives(self) -> None:
        rm = compute_rank_metrics(["g1", "g2"], set(), {"n1"})
        assert rm.total_results == 2
        assert rm.precision_at_k == {}

    def test_enrichment_at_k(self) -> None:
        """Enrichment = P@K / random_precision."""
        result_ids = ["g1", "g2", "n1", "n2", "n3"]
        positive_ids = {"g1", "g2"}
        negative_ids = {"n1", "n2", "n3"}

        rm = compute_rank_metrics(result_ids, positive_ids, negative_ids, k_values=[2])

        # P@2 = 2/2 = 1.0, random = 2/5 = 0.4
        # enrichment = 1.0 / 0.4 = 2.5
        assert rm.enrichment_at_k[2] == 2.5

    def test_pr_curve_generated(self) -> None:
        result_ids = [f"g{i}" for i in range(100)]
        positive_ids = {f"g{i}" for i in range(10)}
        negative_ids = set()

        rm = compute_rank_metrics(result_ids, positive_ids, negative_ids)
        assert len(rm.pr_curve) > 0
        assert len(rm.list_size_vs_recall) > 0

    def test_custom_k_values(self) -> None:
        result_ids = [f"g{i}" for i in range(20)]
        positive_ids = {"g0", "g1", "g2"}
        negative_ids = set()

        rm = compute_rank_metrics(
            result_ids,
            positive_ids,
            negative_ids,
            k_values=[5, 10],
        )
        assert 5 in rm.precision_at_k
        assert 10 in rm.precision_at_k

    def test_k_larger_than_total(self) -> None:
        """K values larger than the result list use effective_k = len."""
        result_ids = ["g1", "g2"]
        positive_ids = {"g1"}
        negative_ids = set()

        rm = compute_rank_metrics(
            result_ids,
            positive_ids,
            negative_ids,
            k_values=[100],
        )
        # effective_k = min(100, 2) = 2, hits = 1, P@100 = 0.5
        assert rm.precision_at_k[100] == 0.5
        assert rm.recall_at_k[100] == 1.0
