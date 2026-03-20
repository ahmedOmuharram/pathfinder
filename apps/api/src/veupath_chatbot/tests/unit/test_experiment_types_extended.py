"""Extended tests for experiment types: serialization round-trips, edge cases."""

import math
from dataclasses import dataclass

import pytest

from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    CrossValidationResult,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    FoldMetrics,
    RankMetrics,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
    TreeOptimizationResult,
    TreeOptimizationTrial,
    experiment_summary_to_json,
    experiment_to_json,
    from_json,
    to_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ZERO_CM = ConfusionMatrix(
    true_positives=0,
    false_positives=0,
    true_negatives=0,
    false_negatives=0,
)

_ZERO_METRICS = ExperimentMetrics(
    confusion_matrix=_ZERO_CM,
    sensitivity=0.0,
    specificity=0.0,
    precision=0.0,
    f1_score=0.0,
    mcc=0.0,
    balanced_accuracy=0.0,
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
# Serialization round-trip tests
# ---------------------------------------------------------------------------


class TestExperimentRoundTrip:
    def test_minimal_experiment_to_json(self):
        exp = Experiment(id="exp_001", config=_minimal_config())
        j = experiment_to_json(exp)
        assert j["id"] == "exp_001"
        assert j["status"] == "pending"
        assert j["metrics"] is None
        assert j["crossValidation"] is None
        assert j["enrichmentResults"] == []
        assert j["config"]["siteId"] == "plasmodb"

    def test_experiment_with_metrics_round_trips(self):
        cm = ConfusionMatrix(
            true_positives=10,
            false_positives=2,
            true_negatives=88,
            false_negatives=0,
        )
        metrics = ExperimentMetrics(
            confusion_matrix=cm,
            sensitivity=1.0,
            specificity=0.9778,
            precision=0.8333,
            f1_score=0.9091,
            mcc=0.8944,
            balanced_accuracy=0.9889,
            total_results=100,
        )
        exp = Experiment(id="exp_002", config=_minimal_config(), metrics=metrics)
        j = experiment_to_json(exp)
        assert j["metrics"]["sensitivity"] == 1.0
        assert j["metrics"]["confusionMatrix"]["truePositives"] == 10

    def test_experiment_with_enrichment_results(self):
        term = EnrichmentTerm(
            term_id="GO:0004672",
            term_name="protein kinase activity",
            gene_count=15,
            background_count=200,
            fold_enrichment=3.5,
            odds_ratio=4.2,
            p_value=1e-10,
            fdr=1e-8,
            bonferroni=1e-7,
            genes=["G1", "G2"],
        )
        er = EnrichmentResult(
            analysis_type="go_function",
            terms=[term],
            total_genes_analyzed=100,
            background_size=5000,
        )
        exp = Experiment(
            id="exp_003",
            config=_minimal_config(),
            enrichment_results=[er],
        )
        j = experiment_to_json(exp)
        assert len(j["enrichmentResults"]) == 1
        assert j["enrichmentResults"][0]["analysisType"] == "go_function"
        terms = j["enrichmentResults"][0]["terms"]
        assert len(terms) == 1
        assert terms[0]["termId"] == "GO:0004672"
        assert terms[0]["genes"] == ["G1", "G2"]

    def test_experiment_with_step_tree(self):
        cfg = _minimal_config()
        cfg.mode = "multi-step"
        cfg.step_tree = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "Search1"},
            "secondaryInput": {"id": "s2", "searchName": "Search2"},
        }
        exp = Experiment(id="exp_004", config=cfg)
        j = experiment_to_json(exp)
        assert j["config"]["mode"] == "multi-step"
        assert j["config"]["stepTree"]["operator"] == "INTERSECT"


# ---------------------------------------------------------------------------
# experiment_summary_to_json
# ---------------------------------------------------------------------------


class TestExperimentSummary:
    def test_summary_without_metrics(self):
        exp = Experiment(id="exp_sum_1", config=_minimal_config())
        j = experiment_summary_to_json(exp)
        assert j["id"] == "exp_sum_1"
        assert j["f1Score"] is None
        assert j["sensitivity"] is None
        assert j["specificity"] is None

    def test_summary_with_metrics(self):
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

    def test_summary_includes_control_counts(self):
        cfg = _minimal_config()
        cfg.positive_controls = ["G1", "G2", "G3"]
        cfg.negative_controls = ["N1", "N2"]
        exp = Experiment(id="exp_sum_3", config=cfg)
        j = experiment_summary_to_json(exp)
        assert j["totalPositives"] == 3
        assert j["totalNegatives"] == 2


# ---------------------------------------------------------------------------
# to_json / from_json edge cases
# ---------------------------------------------------------------------------


class TestJsonCodecEdgeCases:
    def test_to_json_empty_list(self):
        assert to_json([]) == []

    def test_to_json_empty_dict(self):
        assert to_json({}) == {}

    def test_to_json_nested_none(self):
        assert to_json([None, None]) == [None, None]

    def test_to_json_bool_is_not_rounded(self):
        """Booleans are int subclass — make sure they aren't treated as float."""
        assert to_json(True) is True
        assert to_json(False) is False

    def test_from_json_extra_fields_ignored(self):
        """Extra fields in JSON should be silently ignored."""
        data = {"value": 5, "label": "test", "extraField": "ignored"}

        @dataclass
        class _Simple:
            value: int = 0
            label: str = ""

        obj = from_json(data, _Simple)
        assert obj.value == 5
        assert obj.label == "test"
        assert not hasattr(obj, "extra_field")

    def test_from_json_missing_required_field_raises(self):
        """Missing required field (no default) should raise TypeError."""

        @dataclass
        class _Required:
            name: str
            count: int

        with pytest.raises(TypeError):
            from_json({}, _Required)

    def test_float_nan_is_preserved(self):
        """NaN should survive serialization (it's a float)."""
        result = to_json(float("nan"), _round=4)
        assert math.isnan(result)

    def test_float_inf_is_preserved(self):
        result = to_json(float("inf"), _round=4)
        assert result == float("inf")

    def test_deeply_nested_list_of_dicts(self):
        data = [{"a": [{"b": [1, 2, 3]}]}]
        result = to_json(data)
        assert result == [{"a": [{"b": [1, 2, 3]}]}]

    def test_dict_with_int_keys_are_stringified(self):
        result = to_json({10: 0.5, 50: 0.3})
        assert result == {"10": 0.5, "50": 0.3}


# ---------------------------------------------------------------------------
# RankMetrics round-trip with int dict keys
# ---------------------------------------------------------------------------


class TestRankMetricsRoundTrip:
    def test_precision_at_k_int_keys_survive(self):
        """dict[int, float] keys must be stringified on serialize and
        coerced back to int on deserialize."""
        rm = RankMetrics(
            precision_at_k={10: 0.5, 50: 0.3, 100: 0.1},
            total_results=200,
        )
        j = to_json(rm)
        # Keys are stringified
        assert "10" in j["precisionAtK"]
        assert "50" in j["precisionAtK"]
        # Round-trip
        restored = from_json(j, RankMetrics)
        assert restored.precision_at_k[10] == 0.5
        assert restored.precision_at_k[50] == 0.3
        assert restored.precision_at_k[100] == 0.1

    def test_pr_curve_tuples_survive(self):
        rm = RankMetrics(
            pr_curve=[(0.1, 0.9), (0.5, 0.6), (1.0, 0.3)],
        )
        j = to_json(rm)
        assert j["prCurve"] == [[0.1, 0.9], [0.5, 0.6], [1.0, 0.3]]
        restored = from_json(j, RankMetrics)
        # Tuples serialized as lists, deserialized back as tuples
        assert restored.pr_curve == [(0.1, 0.9), (0.5, 0.6), (1.0, 0.3)]


# ---------------------------------------------------------------------------
# CrossValidation round-trip
# ---------------------------------------------------------------------------


class TestCrossValidationRoundTrip:
    def test_full_cv_result(self):
        cm = ConfusionMatrix(
            true_positives=5,
            false_positives=1,
            true_negatives=14,
            false_negatives=0,
        )
        fold_metrics = ExperimentMetrics(
            confusion_matrix=cm,
            sensitivity=1.0,
            specificity=0.9333,
            precision=0.8333,
            f1_score=0.9091,
            mcc=0.8944,
            balanced_accuracy=0.9667,
        )
        fold = FoldMetrics(
            fold_index=0,
            metrics=fold_metrics,
            positive_control_ids=["G1", "G2"],
            negative_control_ids=["N1", "N2"],
        )
        cv = CrossValidationResult(
            k=5,
            folds=[fold],
            mean_metrics=fold_metrics,
            std_metrics={"f1_score": 0.02},
            overfitting_score=0.1,
            overfitting_level="low",
        )
        j = to_json(cv)
        assert j["k"] == 5
        assert len(j["folds"]) == 1
        assert j["folds"][0]["foldIndex"] == 0
        assert j["folds"][0]["metrics"]["sensitivity"] == 1.0

        restored = from_json(j, CrossValidationResult)
        assert restored.k == 5
        assert restored.overfitting_level == "low"


# ---------------------------------------------------------------------------
# TreeOptimization round-trip
# ---------------------------------------------------------------------------


class TestTreeOptimizationRoundTrip:
    def test_tree_opt_result(self):
        trial = TreeOptimizationTrial(
            trial_number=1,
            parameters={"evalue": 1e-5, "operator_c1": "INTERSECT"},
            score=0.85,
            list_size=50,
        )
        result = TreeOptimizationResult(
            best_trial=trial,
            all_trials=[trial],
            total_time_seconds=12.345,
            objective="precision_at_50",
        )
        j = to_json(result)
        assert j["bestTrial"]["trialNumber"] == 1
        assert j["totalTimeSeconds"] == 12.35  # rounded to 2

        restored = from_json(j, TreeOptimizationResult)
        assert restored.objective == "precision_at_50"
        assert restored.best_trial is not None
        assert restored.best_trial.trial_number == 1


# ---------------------------------------------------------------------------
# StepAnalysisResult round-trip
# ---------------------------------------------------------------------------


class TestStepAnalysisRoundTrip:
    def test_step_analysis_with_evaluations_and_contributions(self):
        se = StepEvaluation(
            step_id="s1",
            search_name="GenesByTaxon",
            display_name="Taxon Search",
            result_count=500,
            positive_hits=8,
            positive_total=10,
            negative_hits=3,
            negative_total=20,
            recall=0.8,
            false_positive_rate=0.15,
        )
        sc = StepContribution(
            step_id="s1",
            search_name="GenesByTaxon",
            baseline_recall=0.8,
            ablated_recall=0.0,
            recall_delta=-0.8,
            baseline_fpr=0.15,
            ablated_fpr=0.0,
            fpr_delta=-0.15,
            verdict="essential",
            narrative="Removing this step eliminates all recall.",
        )
        sar = StepAnalysisResult(
            step_evaluations=[se],
            step_contributions=[sc],
        )
        j = to_json(sar)
        assert len(j["stepEvaluations"]) == 1
        assert len(j["stepContributions"]) == 1

        restored = from_json(j, StepAnalysisResult)
        assert len(restored.step_evaluations) == 1
        assert restored.step_evaluations[0].step_id == "s1"
        assert len(restored.step_contributions) == 1
        assert restored.step_contributions[0].verdict == "essential"


# ---------------------------------------------------------------------------
# EnrichmentTerm p-value rounding
# ---------------------------------------------------------------------------


class TestEnrichmentTermPValueRounding:
    def test_p_value_not_rounded_in_to_json(self):
        """p_value, fdr, bonferroni have metadata round=None, so they
        should NOT be rounded during serialization."""
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
        j = to_json(term)
        assert j["pValue"] == 1.23456789e-15
        assert j["fdr"] == 2.34567890e-12
        assert j["bonferroni"] == 3.45678901e-10

    def test_fold_enrichment_is_rounded(self):
        """fold_enrichment and odds_ratio use default rounding (4 decimals)."""
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
        j = to_json(term)
        assert j["foldEnrichment"] == 2.1235
        assert j["oddsRatio"] == 3.9877


# ---------------------------------------------------------------------------
# Experiment total_time_seconds rounding
# ---------------------------------------------------------------------------


class TestExperimentTimeRounding:
    def test_total_time_rounded_to_2_decimals(self):
        exp = Experiment(
            id="exp_time",
            config=_minimal_config(),
            total_time_seconds=12.345678,
        )
        j = experiment_to_json(exp)
        assert j["totalTimeSeconds"] == 12.35

    def test_total_time_none(self):
        exp = Experiment(id="exp_time_none", config=_minimal_config())
        j = experiment_to_json(exp)
        assert j["totalTimeSeconds"] is None


# ---------------------------------------------------------------------------
# ExperimentConfig conditional serialization
# ---------------------------------------------------------------------------


class TestConfigConditionalSerialization:
    def test_step_tree_only_included_when_set(self):
        cfg = _minimal_config()
        exp = Experiment(id="exp_no_tree", config=cfg)
        j = experiment_to_json(exp)
        assert "stepTree" not in j["config"]

    def test_step_tree_included_when_set(self):
        cfg = _minimal_config()
        cfg.step_tree = {"id": "root"}
        exp = Experiment(id="exp_tree", config=cfg)
        j = experiment_to_json(exp)
        assert "stepTree" in j["config"]
        assert j["config"]["stepTree"]["id"] == "root"

    def test_source_strategy_id_only_when_set(self):
        cfg = _minimal_config()
        exp = Experiment(id="exp_no_src", config=cfg)
        j = experiment_to_json(exp)
        assert "sourceStrategyId" not in j["config"]

    def test_optimization_specs_only_when_set(self):
        cfg = _minimal_config()
        exp = Experiment(id="exp_no_opt", config=cfg)
        j = experiment_to_json(exp)
        assert "optimizationSpecs" not in j["config"]

    def test_step_analysis_config_when_enabled(self):
        cfg = _minimal_config()
        cfg.enable_step_analysis = True
        exp = Experiment(id="exp_sa", config=cfg)
        j = experiment_to_json(exp)
        assert j["config"]["enableStepAnalysis"] is True
        assert "stepAnalysisPhases" in j["config"]

    def test_sort_attribute_only_when_set(self):
        cfg = _minimal_config()
        exp = Experiment(id="exp_no_sort", config=cfg)
        j = experiment_to_json(exp)
        assert "sortAttribute" not in j["config"]

        cfg2 = _minimal_config()
        cfg2.sort_attribute = "gene_product"
        cfg2.sort_direction = "DESC"
        exp2 = Experiment(id="exp_sort", config=cfg2)
        j2 = experiment_to_json(exp2)
        assert j2["config"]["sortAttribute"] == "gene_product"
        assert j2["config"]["sortDirection"] == "DESC"

    def test_parent_experiment_id_only_when_set(self):
        cfg = _minimal_config()
        exp = Experiment(id="exp_no_parent", config=cfg)
        j = experiment_to_json(exp)
        assert "parentExperimentId" not in j["config"]

        cfg2 = _minimal_config()
        cfg2.parent_experiment_id = "exp_parent"
        exp2 = Experiment(id="exp_child", config=cfg2)
        j2 = experiment_to_json(exp2)
        assert j2["config"]["parentExperimentId"] == "exp_parent"
