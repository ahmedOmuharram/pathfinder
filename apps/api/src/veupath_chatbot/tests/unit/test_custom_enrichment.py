"""Tests for custom gene set enrichment analysis."""

import math

from veupath_chatbot.services.experiment.custom_enrichment import run_custom_enrichment
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    GeneInfo,
)


def _cfg() -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmo",
        record_type="gene",
        search_name="GenesByText",
        parameters={},
        positive_controls=[],
        negative_controls=[],
        controls_search_name="",
        controls_param_name="",
    )


def _make_experiment(
    tp: list[str],
    fp: list[str],
    fn: list[str],
    tn: list[str],
) -> Experiment:
    e = Experiment(id="exp1", config=_cfg())
    e.true_positive_genes = [GeneInfo(id=g) for g in tp]
    e.false_positive_genes = [GeneInfo(id=g) for g in fp]
    e.false_negative_genes = [GeneInfo(id=g) for g in fn]
    e.true_negative_genes = [GeneInfo(id=g) for g in tn]
    return e


class TestRunCustomEnrichment:
    def test_basic_overlap(self) -> None:
        exp = _make_experiment(
            tp=["g1", "g2", "g3"],
            fp=["g4", "g5"],
            fn=["g6"],
            tn=["g7", "g8", "g9"],
        )
        result = run_custom_enrichment(exp, ["g1", "g2", "g10"], "MySet")

        assert result["geneSetName"] == "MySet"
        assert result["geneSetSize"] == 3
        # Result IDs = TP + FP = {g1, g2, g3, g4, g5}
        # Overlap with gene set = {g1, g2}
        assert result["overlapCount"] == 2
        assert sorted(result["overlapGenes"]) == ["g1", "g2"]
        # TP in overlap = {g1, g2} (both are TP)
        assert result["tpCount"] == 2

    def test_no_overlap(self) -> None:
        exp = _make_experiment(
            tp=["g1", "g2"],
            fp=["g3"],
            fn=["g4"],
            tn=["g5"],
        )
        result = run_custom_enrichment(exp, ["g10", "g11"], "Disjoint")

        assert result["overlapCount"] == 0
        assert result["overlapGenes"] == []
        assert result["foldEnrichment"] == 0.0
        assert result["tpCount"] == 0

    def test_full_overlap(self) -> None:
        exp = _make_experiment(
            tp=["g1", "g2"],
            fp=["g3"],
            fn=[],
            tn=[],
        )
        # Gene set is exactly the result set
        result = run_custom_enrichment(exp, ["g1", "g2", "g3"], "Full")

        assert result["overlapCount"] == 3
        assert result["geneSetSize"] == 3

    def test_fold_enrichment_calculation(self) -> None:
        exp = _make_experiment(
            tp=["g1", "g2"],
            fp=["g3", "g4", "g5"],
            fn=["g6", "g7", "g8"],
            tn=["g9", "g10"],
        )
        # Result set: {g1, g2, g3, g4, g5} = 5
        # Background is 5 + 3 + 2 = 10
        # Gene set: {g1, g2} size=2
        # Overlap is {g1, g2} = 2
        # Expected = 5 * 2 / 10 = 1.0
        # Fold = 2 / 1.0 = 2.0
        result = run_custom_enrichment(exp, ["g1", "g2"], "TP-only")
        assert result["foldEnrichment"] == 2.0

    def test_background_includes_all_classes(self) -> None:
        exp = _make_experiment(
            tp=["g1"],
            fp=["g2"],
            fn=["g3"],
            tn=["g4"],
        )
        result = run_custom_enrichment(exp, ["g1"], "Small")
        # background = |result| + |fn| + |tn| = 2 + 1 + 1 = 4
        assert result["backgroundSize"] == 4

    def test_p_value_bounded(self) -> None:
        exp = _make_experiment(
            tp=[f"g{i}" for i in range(20)],
            fp=[f"f{i}" for i in range(30)],
            fn=[f"n{i}" for i in range(10)],
            tn=[f"t{i}" for i in range(40)],
        )
        result = run_custom_enrichment(exp, [f"g{i}" for i in range(15)], "Enriched")
        assert 0.0 <= result["pValue"] <= 1.0
        assert math.isfinite(result["pValue"])

    def test_odds_ratio_positive(self) -> None:
        exp = _make_experiment(
            tp=["g1", "g2", "g3"],
            fp=["g4"],
            fn=["g5"],
            tn=["g6", "g7", "g8"],
        )
        result = run_custom_enrichment(exp, ["g1", "g2", "g3"], "AllTP")
        assert result["oddsRatio"] > 0

    def test_empty_gene_set(self) -> None:
        exp = _make_experiment(tp=["g1"], fp=[], fn=[], tn=[])
        result = run_custom_enrichment(exp, [], "Empty")
        assert result["geneSetSize"] == 0
        assert result["overlapCount"] == 0

    def test_overlap_genes_sorted(self) -> None:
        exp = _make_experiment(
            tp=["g3", "g1", "g2"],
            fp=[],
            fn=[],
            tn=[],
        )
        result = run_custom_enrichment(exp, ["g2", "g3", "g1"], "Sorted")
        assert result["overlapGenes"] == ["g1", "g2", "g3"]
