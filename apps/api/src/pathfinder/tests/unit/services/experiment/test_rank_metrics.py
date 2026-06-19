"""Correctness tests for the pure rank-metric engine — hand-computed
expected values, not shape checks.

Worked base example (used across cases): a 10-item ranked list with
relevant items at positions 1, 3, 5 (zero-based 0, 2, 4)::

    ranked = [r1, x1, r2, x2, r3, x6, x7, x8, x9, x10]
    positives = {r1, r2, r3}      total_pos = 3   total = 10
    random_precision = total_pos / total = 3 / 10 = 0.3

Cumulative hits / metrics by k::

    k=1  hits=1  P=1/1=1.0      R=1/3       E=1.0/0.3 = 10/3
    k=3  hits=2  P=2/3          R=2/3       E=(2/3)/0.3 = 20/9
    k=5  hits=3  P=3/5=0.6      R=3/3=1.0   E=0.6/0.3 = 2.0
    k=10 hits=3  P=3/10=0.3     R=1.0       E=0.3/0.3 = 1.0
"""

from __future__ import annotations

import math

from pathfinder.services.experiment.rank_metrics import compute_rank_metrics

RANKED = ["r1", "x1", "r2", "x2", "r3", "x6", "x7", "x8", "x9", "x10"]
POSITIVES = {"r1", "r2", "r3"}
NEGATIVES: set[str] = set()


def test_precision_at_k_matches_hand_computed_fractions() -> None:
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[1, 3, 5, 10])
    assert m.precision_at_k[1] == 1.0
    assert math.isclose(m.precision_at_k[3], 2 / 3)
    assert m.precision_at_k[5] == 0.6
    assert m.precision_at_k[10] == 0.3


def test_recall_at_k_matches_hand_computed_fractions() -> None:
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[1, 3, 5, 10])
    assert math.isclose(m.recall_at_k[1], 1 / 3)
    assert math.isclose(m.recall_at_k[3], 2 / 3)
    assert m.recall_at_k[5] == 1.0
    assert m.recall_at_k[10] == 1.0


def test_enrichment_at_k_is_precision_over_random_precision() -> None:
    # random_precision = 3/10 = 0.3
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[1, 3, 5, 10])
    assert math.isclose(m.enrichment_at_k[1], 10 / 3)
    assert math.isclose(m.enrichment_at_k[3], 20 / 9)
    assert math.isclose(m.enrichment_at_k[5], 2.0)
    assert math.isclose(m.enrichment_at_k[10], 1.0)


def test_total_results_reflects_list_length() -> None:
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[5])
    assert m.total_results == 10


def test_all_relevant_in_top_k_gives_recall_one() -> None:
    ranked = ["r1", "r2", "r3", "x1", "x2"]
    m = compute_rank_metrics(ranked, {"r1", "r2", "r3"}, NEGATIVES, k_values=[3])
    # top 3 are all relevant: P@3 = 3/3 = 1.0, R@3 = 3/3 = 1.0
    assert m.precision_at_k[3] == 1.0
    assert m.recall_at_k[3] == 1.0
    # random_precision = 3/5 = 0.6, E@3 = 1.0 / 0.6 = 5/3
    assert math.isclose(m.enrichment_at_k[3], 5 / 3)


def test_no_relevant_found_yields_zeros() -> None:
    ranked = ["x1", "x2", "x3", "x4", "x5"]
    m = compute_rank_metrics(ranked, {"r1", "r2"}, NEGATIVES, k_values=[3])
    assert m.precision_at_k[3] == 0.0
    assert m.recall_at_k[3] == 0.0
    assert m.enrichment_at_k[3] == 0.0
    assert m.total_results == 5


def test_empty_result_list_returns_empty_metrics_no_divide_by_zero() -> None:
    m = compute_rank_metrics([], POSITIVES, NEGATIVES, k_values=[5])
    assert m.total_results == 0
    assert m.precision_at_k == {}
    assert m.recall_at_k == {}
    assert m.enrichment_at_k == {}


def test_empty_positive_set_returns_empty_metrics_no_divide_by_zero() -> None:
    m = compute_rank_metrics(RANKED, set(), NEGATIVES, k_values=[5])
    assert m.total_results == 10
    assert m.precision_at_k == {}
    assert m.recall_at_k == {}
    assert m.enrichment_at_k == {}


def test_duplicate_ids_are_deduplicated_before_scoring() -> None:
    # r1 appears twice; dedup keeps first occurrence, so total = 5 not 6
    # and recall cannot exceed 1.0.
    ranked = ["r1", "r1", "r2", "x1", "x2", "r3"]
    m = compute_rank_metrics(ranked, {"r1", "r2", "r3"}, NEGATIVES, k_values=[10])
    assert m.total_results == 5
    # all 3 positives present once each: R = 3/3 = 1.0
    assert m.recall_at_k[10] == 1.0


def test_k_larger_than_list_divides_by_requested_k() -> None:
    # K=20 > total=10. Standard Precision@K divides by the REQUESTED K, treating
    # the unfilled ranks 11..20 as non-relevant padding:
    #   hits in top 10 = 3  ->  P@20 = 3/20 = 0.15
    # Recall still divides by total positives (3), all 3 found -> 1.0.
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[20])
    assert m.precision_at_k[20] == 0.15
    assert m.recall_at_k[20] == 1.0
    # E@20 = P@20 / random_precision = 0.15 / 0.3 = 0.5
    assert math.isclose(m.enrichment_at_k[20], 0.5)


def test_precision_at_k_keeps_decaying_past_end_of_list() -> None:
    # 10-item list, 5 positives all in the top 10. Standard Precision@K must
    # keep falling as K grows past the list length, NOT plateau at hits/total.
    #   P@10 = 5/10 = 0.5   P@25 = 5/25 = 0.2   P@50 = 5/50 = 0.1
    # The buggy implementation reported P@25 = P@50 = 0.5 (divide by total).
    ranked = [f"r{i}" for i in range(1, 6)] + [f"x{i}" for i in range(1, 6)]
    pos = {f"r{i}" for i in range(1, 6)}
    m = compute_rank_metrics(ranked, pos, NEGATIVES, k_values=[10, 25, 50])
    assert m.precision_at_k[10] == 0.5
    assert m.precision_at_k[25] == 0.2
    assert m.precision_at_k[50] == 0.1
    # recall plateaus at 1.0 once all positives are recovered (correct)
    assert m.recall_at_k[10] == 1.0
    assert m.recall_at_k[25] == 1.0
    assert m.recall_at_k[50] == 1.0
    # random_precision = 5/10 = 0.5
    # E@25 = (5/25) / 0.5 = 0.4 ; E@50 = (5/50) / 0.5 = 0.2
    assert math.isclose(m.enrichment_at_k[25], 0.4)
    assert math.isclose(m.enrichment_at_k[50], 0.2)


def test_pr_curve_ends_at_full_list_recall() -> None:
    m = compute_rank_metrics(RANKED, POSITIVES, NEGATIVES, k_values=[5])
    # final sampled point is k == total: precision 0.3, recall 1.0
    assert m.pr_curve[-1] == (0.3, 1.0)
    assert m.list_size_vs_recall[-1] == (10, 1.0)


def test_single_relevant_at_top_precision_decays() -> None:
    ranked = ["r1", "x1", "x2", "x3"]
    m = compute_rank_metrics(ranked, {"r1"}, NEGATIVES, k_values=[1, 2, 4])
    # one positive, total=4, random_precision = 1/4 = 0.25
    assert m.precision_at_k[1] == 1.0
    assert m.precision_at_k[2] == 0.5
    assert m.precision_at_k[4] == 0.25
    assert m.recall_at_k[1] == 1.0
    assert m.recall_at_k[4] == 1.0
    # E@1 = 1.0 / 0.25 = 4.0
    assert math.isclose(m.enrichment_at_k[1], 4.0)
