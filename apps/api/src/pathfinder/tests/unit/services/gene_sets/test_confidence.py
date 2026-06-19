from __future__ import annotations

import pytest

from pathfinder.services.gene_sets.confidence import (
    GeneClassification,
    compute_gene_confidence,
)


def test_classification_weights_and_sort_order() -> None:
    result = compute_gene_confidence(
        GeneClassification(tp_ids=["tp"], fp_ids=["fp"], fn_ids=["fn"], tn_ids=["tn"])
    )
    assert [s.gene_id for s in result] == ["tp", "tn", "fn", "fp"]
    by_id = {s.gene_id: s for s in result}
    assert by_id["tp"].composite_score == pytest.approx(1.0 / 3.0)
    assert by_id["tn"].composite_score == 0.0
    assert by_id["fn"].composite_score == pytest.approx(-0.5 / 3.0)
    assert by_id["fp"].composite_score == pytest.approx(-1.0 / 3.0)


def test_composite_blends_all_three_signals() -> None:
    result = compute_gene_confidence(
        GeneClassification(tp_ids=["g1"], fp_ids=[], fn_ids=[], tn_ids=[]),
        ensemble_scores={"g1": 0.6},
        enrichment_gene_counts={"g1": 2},
        max_enrichment_terms=4,
    )
    assert len(result) == 1
    g1 = result[0]
    assert g1.classification_score == 1.0
    assert g1.ensemble_score == 0.6
    assert g1.enrichment_score == pytest.approx(0.5)
    assert g1.composite_score == pytest.approx(0.7)


def test_enrichment_score_caps_at_one() -> None:
    result = compute_gene_confidence(
        GeneClassification(tp_ids=["g1"], fp_ids=[], fn_ids=[], tn_ids=[]),
        enrichment_gene_counts={"g1": 10},
        max_enrichment_terms=2,
    )
    assert result[0].enrichment_score == 1.0
    assert result[0].composite_score == pytest.approx(2.0 / 3.0)


def test_gene_appearing_in_two_labels_is_counted_once_as_first() -> None:
    result = compute_gene_confidence(
        GeneClassification(tp_ids=["g1"], fp_ids=["g1"], fn_ids=[], tn_ids=[])
    )
    assert len(result) == 1
    assert result[0].gene_id == "g1"
    assert result[0].classification_score == 1.0
