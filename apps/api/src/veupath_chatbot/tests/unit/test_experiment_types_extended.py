"""Tests for custom serialization logic in experiment types.

Covers: experiment_summary_to_json (custom function), RoundedFloat fields
(fold_enrichment, odds_ratio), and total_time_seconds rounding.
"""

from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    experiment_summary_to_json,
    experiment_to_json,
)


def _minimal_config() -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmodb",
        record_type="gene",
        search_name="GenesByTaxon",
        parameters={},
        positive_controls=[],
        negative_controls=[],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


# ---------------------------------------------------------------------------
# experiment_summary_to_json (custom function, not just model_dump)
# ---------------------------------------------------------------------------


class TestExperimentSummary:
    def test_summary_without_metrics(self) -> None:
        exp = Experiment(id="exp_sum_1", config=_minimal_config())
        j = experiment_summary_to_json(exp)
        assert j["id"] == "exp_sum_1"
        assert j["f1Score"] is None
        assert j["sensitivity"] is None
        assert j["specificity"] is None

    def test_summary_with_metrics(self) -> None:
        cm = ConfusionMatrix(
            true_positives=5,
            false_positives=1,
            true_negatives=90,
            false_negatives=4,
        )
        metrics = ExperimentMetrics(
            confusion_matrix=cm,
            sensitivity=0.5556,
            specificity=0.9890,
            precision=0.8333,
            f1_score=0.6667,
            mcc=0.6500,
            balanced_accuracy=0.7723,
        )
        exp = Experiment(id="exp_sum_2", config=_minimal_config(), metrics=metrics)
        j = experiment_summary_to_json(exp)
        assert j["f1Score"] == 0.6667
        assert j["sensitivity"] == 0.5556

    def test_summary_includes_control_counts(self) -> None:
        cfg = _minimal_config()
        cfg.positive_controls = ["G1", "G2", "G3"]
        cfg.negative_controls = ["N1", "N2"]
        exp = Experiment(id="exp_sum_3", config=cfg)
        j = experiment_summary_to_json(exp)
        assert j["totalPositives"] == 3
        assert j["totalNegatives"] == 2


# ---------------------------------------------------------------------------
# EnrichmentTerm: RoundedFloat custom type
# ---------------------------------------------------------------------------


class TestEnrichmentTermRounding:
    def test_p_value_not_rounded(self) -> None:
        """p_value, fdr, bonferroni are plain floats — no rounding."""
        term = EnrichmentTerm(
            term_id="GO:0001",
            term_name="kinase",
            gene_count=5,
            background_count=100,
            fold_enrichment=2.5,
            odds_ratio=3.0,
            p_value=1.23456789e-15,
            fdr=2.34567890e-12,
            bonferroni=3.45678901e-10,
        )
        j = term.model_dump(by_alias=True)
        assert j["pValue"] == 1.23456789e-15
        assert j["fdr"] == 2.34567890e-12
        assert j["bonferroni"] == 3.45678901e-10

    def test_fold_enrichment_rounded_to_4_decimals(self) -> None:
        """fold_enrichment and odds_ratio use RoundedFloat (4 decimals)."""
        term = EnrichmentTerm(
            term_id="GO:0001",
            term_name="kinase",
            gene_count=5,
            background_count=100,
            fold_enrichment=2.123456789,
            odds_ratio=3.987654321,
            p_value=0.001,
            fdr=0.01,
            bonferroni=0.05,
        )
        j = term.model_dump(by_alias=True)
        assert j["foldEnrichment"] == 2.1235
        assert j["oddsRatio"] == 3.9877


# ---------------------------------------------------------------------------
# Experiment: total_time_seconds rounding
# ---------------------------------------------------------------------------


class TestExperimentTimeRounding:
    def test_total_time_rounded_to_2_decimals(self) -> None:
        exp = Experiment(
            id="exp_time",
            config=_minimal_config(),
            total_time_seconds=12.345678,
        )
        j = experiment_to_json(exp)
        assert j["totalTimeSeconds"] == 12.35

    def test_total_time_none(self) -> None:
        exp = Experiment(id="exp_time_none", config=_minimal_config())
        j = experiment_to_json(exp)
        assert j["totalTimeSeconds"] is None
