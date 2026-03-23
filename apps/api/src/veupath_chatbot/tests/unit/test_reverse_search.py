"""Tests for reverse search — rank gene sets by recall of positive genes.

Covers:
- Ranking gene sets by recall, then f1
- Perfect gene set ranks first
- Empty input returns empty list
- Zero-overlap gene sets handled
- Metrics (recall, precision, f1) present in results
"""

import pytest

from veupath_chatbot.services.gene_sets.reverse_search import (
    GeneSetCandidate,
    rank_gene_sets_by_recall,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POSITIVES = ["G1", "G2", "G3", "G4", "G5"]
NEGATIVES = ["N1", "N2", "N3"]


def _candidate(
    candidate_id: str,
    name: str,
    gene_ids: list[str],
    search_name: str | None = None,
) -> GeneSetCandidate:
    return GeneSetCandidate(
        id=candidate_id,
        name=name,
        gene_ids=gene_ids,
        search_name=search_name,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRankGeneSetsByRecall:
    """Pure-function ranking of gene sets against positive controls."""

    def test_ranks_by_recall_descending(self) -> None:
        """Gene set with higher recall ranks first."""
        candidates = [
            _candidate("low", "Low recall", ["G1"]),
            _candidate("high", "High recall", ["G1", "G2", "G3", "G4"]),
            _candidate("mid", "Mid recall", ["G1", "G2"]),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES)
        assert [r.gene_set_id for r in results] == ["high", "mid", "low"]

    def test_perfect_gene_set_ranks_first(self) -> None:
        """A gene set containing all positives and no negatives ranks first."""
        candidates = [
            _candidate("partial", "Partial", ["G1", "G2"]),
            _candidate("perfect", "Perfect", list(POSITIVES)),
            _candidate("noisy", "Noisy", list(POSITIVES) + list(NEGATIVES)),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES, NEGATIVES)
        assert results[0].gene_set_id == "perfect"
        assert results[0].recall == 1.0
        assert results[0].precision == 1.0

    def test_empty_gene_sets_returns_empty(self) -> None:
        """No candidates → no results."""
        results = rank_gene_sets_by_recall([], POSITIVES)
        assert results == []

    def test_zero_overlap_gene_set(self) -> None:
        """A gene set sharing no genes with positives gets zero recall."""
        candidates = [_candidate("none", "No overlap", ["X1", "X2"])]
        results = rank_gene_sets_by_recall(candidates, POSITIVES)
        assert len(results) == 1
        assert results[0].recall == 0.0
        assert results[0].overlap_count == 0

    def test_includes_metrics(self) -> None:
        """Each result includes recall, precision, f1, estimated_size, overlap_count."""
        candidates = [
            _candidate("gs1", "Test Set", ["G1", "G2", "G3", "N1"]),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES, NEGATIVES)
        assert len(results) == 1
        r = results[0]
        assert r.recall == pytest.approx(3 / 5)  # 3 of 5 positives found
        assert r.precision == pytest.approx(3 / 4)  # 3 of 4 total are positives
        assert r.f1 > 0.0
        assert r.estimated_size == 4
        assert r.overlap_count == 3

    def test_ties_broken_by_f1(self) -> None:
        """When recall is tied, higher f1 (better precision) ranks first."""
        # Both have recall 2/5 = 0.4, but different sizes → different precision
        candidates = [
            _candidate("bloated", "Bloated", ["G1", "G2", "X1", "X2", "X3"]),
            _candidate("tight", "Tight", ["G1", "G2"]),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES)
        # tight: precision = 2/2 = 1.0, f1 higher
        # bloated: precision = 2/5 = 0.4, f1 lower
        assert results[0].gene_set_id == "tight"
        assert results[1].gene_set_id == "bloated"

    def test_search_name_propagated(self) -> None:
        """search_name from the candidate appears in the result."""
        candidates = [
            _candidate("gs1", "Test", ["G1"], search_name="GenesByTaxon"),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES)
        assert results[0].search_name == "GenesByTaxon"
        assert results[0].name == "Test"

    def test_no_negatives_still_computes_metrics(self) -> None:
        """When negatives are not provided, precision treats all results as TP."""
        candidates = [
            _candidate("gs1", "Test", ["G1", "G2", "X1"]),
        ]
        results = rank_gene_sets_by_recall(candidates, POSITIVES)
        r = results[0]
        assert r.recall == pytest.approx(2 / 5)
        # Without negatives, precision = overlap / estimated_size
        assert r.precision == pytest.approx(2 / 3)
        assert r.f1 > 0.0
