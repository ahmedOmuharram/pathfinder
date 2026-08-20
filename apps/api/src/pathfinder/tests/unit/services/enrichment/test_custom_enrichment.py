"""A custom gene set is scored against the experiment with the exact tail."""

from __future__ import annotations

import math

import pytest

from pathfinder.services.enrichment.custom import run_custom_enrichment
from pathfinder.services.experiment.types.experiment import (
    Experiment,
    ExperimentConfig,
)
from pathfinder.services.experiment.types.metrics import GeneInfo

_TRUE_POSITIVES = [f"PF3D7_{i:04d}" for i in range(1, 11)]
_FALSE_POSITIVES = [f"PF3D7_{i:04d}" for i in range(11, 21)]
_FALSE_NEGATIVES = [f"PF3D7_{i:04d}" for i in range(21, 31)]
_TRUE_NEGATIVES = [f"PF3D7_{i:04d}" for i in range(1000, 1170)]


def _experiment() -> Experiment:
    return Experiment(
        id="exp-custom",
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="transcript",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
        ),
        status="completed",
        true_positive_genes=[GeneInfo(id=g) for g in _TRUE_POSITIVES],
        false_positive_genes=[GeneInfo(id=g) for g in _FALSE_POSITIVES],
        false_negative_genes=[GeneInfo(id=g) for g in _FALSE_NEGATIVES],
        true_negative_genes=[GeneInfo(id=g) for g in _TRUE_NEGATIVES],
    )


def _outside(count: int) -> list[str]:
    """Ids the experiment never classified, so they are not in its background."""
    return [f"PF3D7_{i:04d}" for i in range(5000, 5000 + count)]


def _exact_sf(x: int, n: int, k: int, m: int) -> float:
    lo = max(0, m + k - n)
    hi = min(k, m)
    favourable = sum(
        math.comb(k, i) * math.comb(n - k, m - i) for i in range(max(x, lo), hi + 1)
    )
    return favourable / math.comb(n, m)


def test_an_enriched_gene_set_reports_the_exact_tail() -> None:
    gene_ids = [*_TRUE_POSITIVES[:8], *_FALSE_NEGATIVES[:4]]

    result = run_custom_enrichment(_experiment(), gene_ids, "kinase panel")

    assert result["backgroundSize"] == 200
    assert result["geneSetSize"] == 12
    assert result["geneSetInBackground"] == 12
    assert result["overlapCount"] == 8
    assert result["tpCount"] == 8
    assert result["foldEnrichment"] == 6.6667
    assert result["pValue"] == pytest.approx(_exact_sf(8, 200, 20, 12), rel=1e-12)
    assert result["pValue"] == pytest.approx(8.991416145071992e-07, rel=1e-12)


def test_an_unenriched_gene_set_keeps_its_probability_mass() -> None:
    gene_ids = [_TRUE_POSITIVES[0], *_TRUE_NEGATIVES[:11]]

    result = run_custom_enrichment(_experiment(), gene_ids, "background panel")

    assert result["overlapCount"] == 1
    assert result["pValue"] == pytest.approx(_exact_sf(1, 200, 20, 12), rel=1e-12)
    assert result["pValue"] == pytest.approx(0.7281615753471774, rel=1e-12)


def test_ids_outside_the_background_take_no_part_in_the_statistics() -> None:
    gene_ids = [*_TRUE_POSITIVES[:8], *_FALSE_NEGATIVES[:4], *_outside(6)]

    result = run_custom_enrichment(_experiment(), gene_ids, "panel with strays")

    assert result["geneSetSize"] == 18
    assert result["geneSetInBackground"] == 12
    assert result["overlapCount"] == 8
    assert result["foldEnrichment"] == 6.6667
    assert result["oddsRatio"] == 29.3333
    assert result["pValue"] == pytest.approx(_exact_sf(8, 200, 20, 12), rel=1e-12)
    assert result["pValue"] == pytest.approx(8.991416145071992e-07, rel=1e-12)


def test_a_gene_set_larger_than_the_background_is_scored() -> None:
    gene_ids = [*_TRUE_POSITIVES[:3], *_TRUE_NEGATIVES[:2], *_outside(245)]

    result = run_custom_enrichment(_experiment(), gene_ids, "genome wide paste")

    assert result["geneSetSize"] == 250
    assert result["geneSetInBackground"] == 5
    assert result["overlapCount"] == 3
    assert result["foldEnrichment"] == 6.0
    assert result["oddsRatio"] == 15.7059
    assert result["pValue"] == pytest.approx(_exact_sf(3, 200, 20, 5), rel=1e-12)
    assert result["pValue"] == pytest.approx(0.0075929263487795814, rel=1e-12)


def test_a_set_that_is_exactly_the_result_has_an_unbounded_odds_ratio() -> None:
    gene_ids = [*_TRUE_POSITIVES, *_FALSE_POSITIVES]

    result = run_custom_enrichment(_experiment(), gene_ids, "the result itself")

    assert result["geneSetInBackground"] == 20
    assert result["overlapCount"] == 20
    assert result["oddsRatio"] is None


@pytest.mark.parametrize(
    "gene_ids",
    [
        _TRUE_POSITIVES,
        [*_TRUE_POSITIVES, *_FALSE_POSITIVES, *_FALSE_NEGATIVES[:4]],
    ],
    ids=["set inside the result", "set covering the result"],
)
def test_an_empty_margin_makes_the_odds_ratio_unbounded(gene_ids: list[str]) -> None:
    result = run_custom_enrichment(_experiment(), gene_ids, "empty margin panel")

    assert result["oddsRatio"] is None


def test_a_set_that_never_meets_the_result_has_a_zero_odds_ratio() -> None:
    gene_ids = _TRUE_NEGATIVES[:12]

    result = run_custom_enrichment(_experiment(), gene_ids, "no overlap panel")

    assert result["geneSetInBackground"] == 12
    assert result["overlapCount"] == 0
    assert result["oddsRatio"] == 0.0


@pytest.mark.parametrize("size", [3, 250])
def test_a_gene_set_outside_the_universe_is_certain(size: int) -> None:
    gene_ids = _outside(size)

    result = run_custom_enrichment(_experiment(), gene_ids, "unrelated panel")

    assert result["geneSetSize"] == size
    assert result["geneSetInBackground"] == 0
    assert result["overlapCount"] == 0
    assert result["foldEnrichment"] == 0.0
    assert result["oddsRatio"] == 0.0
    assert result["pValue"] == 1.0
