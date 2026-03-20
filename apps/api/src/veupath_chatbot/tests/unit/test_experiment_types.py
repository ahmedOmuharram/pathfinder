"""Unit tests for experiment types/ dataclasses -- construction, defaults, frozen checks.

Ensures each dataclass can be instantiated with minimal and full arguments,
default values are correct, and frozen types reject mutation.
"""

import pytest

from veupath_chatbot.services.experiment.types import (
    DEFAULT_K_VALUES,
    BatchExperimentConfig,
    BatchOrganismTarget,
    BootstrapResult,
    ConfidenceInterval,
    ConfusionMatrix,
    CrossValidationResult,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    GeneInfo,
    NegativeSetVariant,
    OperatorComparison,
    OperatorKnob,
    OperatorVariant,
    OptimizationSpec,
    ParameterSensitivity,
    ParameterSweepPoint,
    RankMetrics,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
    ThresholdKnob,
    TreeOptimizationResult,
    TreeOptimizationTrial,
    from_json,
    to_json,
)

# ---------------------------------------------------------------------------
# Core type aliases (just smoke test that values are valid)
# ---------------------------------------------------------------------------


class TestCoreAliases:
    def test_default_k_values(self) -> None:
        assert DEFAULT_K_VALUES == [10, 25, 50, 100]


# ---------------------------------------------------------------------------
# Metrics types
# ---------------------------------------------------------------------------


class TestConfusionMatrix:
    def test_construction(self) -> None:
        cm = ConfusionMatrix(
            true_positives=8,
            false_positives=3,
            true_negatives=17,
            false_negatives=2,
        )
        assert cm.true_positives == 8
        assert cm.false_negatives == 2

    def test_frozen(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
        )
        with pytest.raises(AttributeError):
            cm.true_positives = 5  # type: ignore[misc]


class TestExperimentMetrics:
    def test_defaults(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
        )
        m = ExperimentMetrics(
            confusion_matrix=cm,
            sensitivity=0.0,
            specificity=0.0,
            precision=0.0,
            f1_score=0.0,
            mcc=0.0,
            balanced_accuracy=0.0,
        )
        assert m.negative_predictive_value == 0.0
        assert m.false_positive_rate == 0.0
        assert m.total_results == 0


class TestGeneInfo:
    def test_minimal(self) -> None:
        g = GeneInfo(id="PF3D7_0100100")
        assert g.name is None
        assert g.organism is None
        assert g.product is None

    def test_full(self) -> None:
        g = GeneInfo(
            id="PF3D7_0100100",
            name="Kinase",
            organism="P. falciparum",
            product="protein kinase",
        )
        assert g.product == "protein kinase"


class TestCrossValidationResult:
    def test_defaults(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
        )
        mean = ExperimentMetrics(
            confusion_matrix=cm,
            sensitivity=0.0,
            specificity=0.0,
            precision=0.0,
            f1_score=0.0,
            mcc=0.0,
            balanced_accuracy=0.0,
        )
        cv = CrossValidationResult(k=5, folds=[], mean_metrics=mean)
        assert cv.overfitting_score == 0.0
        assert cv.overfitting_level == "low"
        assert cv.std_metrics == {}


# ---------------------------------------------------------------------------
# Enrichment types
# ---------------------------------------------------------------------------


class TestEnrichmentTerm:
    def test_construction(self) -> None:
        t = EnrichmentTerm(
            term_id="GO:0001",
            term_name="kinase activity",
            gene_count=5,
            background_count=100,
            fold_enrichment=2.5,
            odds_ratio=3.0,
            p_value=0.001,
            fdr=0.01,
            bonferroni=0.05,
        )
        assert t.genes == []
        assert t.fold_enrichment == 2.5


class TestEnrichmentResult:
    def test_defaults(self) -> None:
        er = EnrichmentResult(analysis_type="go_function", terms=[])
        assert er.total_genes_analyzed == 0
        assert er.background_size == 0
        assert er.error is None


# ---------------------------------------------------------------------------
# Rank types
# ---------------------------------------------------------------------------


class TestRankMetrics:
    def test_defaults(self) -> None:
        rm = RankMetrics()
        assert rm.precision_at_k == {}
        assert rm.recall_at_k == {}
        assert rm.total_results == 0

    def test_roundtrip(self) -> None:
        rm = RankMetrics(
            precision_at_k={10: 0.5, 50: 0.3},
            recall_at_k={10: 0.25},
            pr_curve=[(0.5, 0.25)],
            list_size_vs_recall=[(10, 0.25)],
            total_results=100,
        )
        j = to_json(rm)
        restored = from_json(j, RankMetrics)
        assert restored.total_results == 100
        # Dict keys are stringified in JSON, coerced back to int
        assert restored.precision_at_k[10] == 0.5


class TestConfidenceInterval:
    def test_defaults(self) -> None:
        ci = ConfidenceInterval()
        assert ci.lower == 0.0
        assert ci.mean == 0.0
        assert ci.upper == 0.0
        assert ci.std == 0.0


class TestBootstrapResult:
    def test_defaults(self) -> None:
        br = BootstrapResult()
        assert br.n_iterations == 0
        assert br.metric_cis == {}
        assert br.top_k_stability == 0.0

    def test_roundtrip_with_nested_ci(self) -> None:
        br = BootstrapResult(
            n_iterations=1000,
            metric_cis={
                "sensitivity": ConfidenceInterval(
                    lower=0.7, mean=0.8, upper=0.9, std=0.05
                )
            },
            top_k_stability=0.95,
        )
        j = to_json(br)
        restored = from_json(j, BootstrapResult)
        assert restored.n_iterations == 1000
        assert restored.top_k_stability == 0.95
        # Nested ConfidenceInterval should be dict (from_json does not
        # coerce nested dicts inside dict[str, X] when X is a dataclass --
        # this is the expected behavior for the codec)


class TestNegativeSetVariant:
    def test_construction(self) -> None:
        nsv = NegativeSetVariant(
            label="random",
            rank_metrics=RankMetrics(total_results=50),
            negative_count=20,
        )
        assert nsv.label == "random"
        assert nsv.negative_count == 20


# ---------------------------------------------------------------------------
# Optimization types
# ---------------------------------------------------------------------------


class TestOptimizationSpec:
    def test_minimal(self) -> None:
        s = OptimizationSpec(name="evalue", type="numeric")
        assert s.min is None
        assert s.max is None
        assert s.choices is None


class TestThresholdKnob:
    def test_construction(self) -> None:
        k = ThresholdKnob(step_id="s1", param_name="evalue", min_val=0.0, max_val=1.0)
        assert k.step_size is None


class TestOperatorKnob:
    def test_default_options(self) -> None:
        k = OperatorKnob(combine_node_id="c1")
        assert "INTERSECT" in k.options
        assert "UNION" in k.options
        assert "MINUS" in k.options


class TestTreeOptimizationTrial:
    def test_defaults(self) -> None:
        t = TreeOptimizationTrial(trial_number=1)
        assert t.parameters == {}
        assert t.score == 0.0
        assert t.rank_metrics is None


class TestTreeOptimizationResult:
    def test_defaults(self) -> None:
        r = TreeOptimizationResult()
        assert r.best_trial is None
        assert r.all_trials == []
        assert r.objective == ""


# ---------------------------------------------------------------------------
# Experiment types
# ---------------------------------------------------------------------------


class TestExperimentConfig:
    def test_defaults(self) -> None:
        cfg = ExperimentConfig(
            site_id="plasmodb",
            record_type="gene",
            search_name="GenesByTaxon",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        )
        assert cfg.mode == "single"
        assert cfg.controls_value_format == "newline"
        assert cfg.enable_cross_validation is False
        assert cfg.k_folds == 5
        assert cfg.enable_step_analysis is False
        assert cfg.step_tree is None
        assert cfg.parent_experiment_id is None
        assert cfg.sort_direction == "ASC"


class TestBatchExperimentConfig:
    def test_construction(self) -> None:
        base = ExperimentConfig(
            site_id="plasmodb",
            record_type="gene",
            search_name="Test",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        )
        batch = BatchExperimentConfig(
            base_config=base,
            organism_param_name="organism",
            target_organisms=[
                BatchOrganismTarget(organism="P. falciparum"),
            ],
        )
        assert len(batch.target_organisms) == 1
        assert batch.organism_param_name == "organism"


class TestExperiment:
    def test_defaults(self) -> None:
        cfg = ExperimentConfig(
            site_id="plasmodb",
            record_type="gene",
            search_name="Test",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        )
        exp = Experiment(id="exp_001", config=cfg)
        assert exp.status == "pending"
        assert exp.metrics is None
        assert exp.cross_validation is None
        assert exp.enrichment_results == []
        assert exp.step_analysis is None
        assert exp.rank_metrics is None
        assert exp.robustness is None
        assert exp.tree_optimization is None


# ---------------------------------------------------------------------------
# Step analysis types
# ---------------------------------------------------------------------------


class TestStepEvaluation:
    def test_defaults(self) -> None:
        se = StepEvaluation(
            step_id="s1",
            search_name="S",
            display_name="S",
            result_count=0,
            positive_hits=0,
            positive_total=0,
            negative_hits=0,
            negative_total=0,
            recall=0.0,
            false_positive_rate=0.0,
        )
        assert se.tp_movement == 0
        assert se.fp_movement == 0
        assert se.fn_movement == 0
        assert se.captured_positive_ids == []
        assert se.captured_negative_ids == []


class TestOperatorVariant:
    def test_frozen(self) -> None:
        ov = OperatorVariant(
            operator="INTERSECT",
            positive_hits=5,
            negative_hits=2,
            total_results=100,
            recall=0.5,
            false_positive_rate=0.1,
            f1_score=0.6,
        )
        with pytest.raises(AttributeError):
            ov.operator = "UNION"  # type: ignore[misc]


class TestOperatorComparison:
    def test_defaults(self) -> None:
        oc = OperatorComparison(
            combine_node_id="c1",
            current_operator="INTERSECT",
        )
        assert oc.variants == []
        assert oc.recommendation == ""
        assert oc.recommended_operator == ""
        assert oc.precision_at_k_delta == {}


class TestStepContribution:
    def test_defaults(self) -> None:
        sc = StepContribution(
            step_id="s1",
            search_name="S",
            baseline_recall=0.8,
            ablated_recall=0.6,
            recall_delta=-0.2,
            baseline_fpr=0.1,
            ablated_fpr=0.05,
            fpr_delta=-0.05,
            verdict="essential",
        )
        assert sc.enrichment_delta == 0.0
        assert sc.narrative == ""


class TestParameterSweepPoint:
    def test_frozen(self) -> None:
        p = ParameterSweepPoint(
            value=0.5,
            positive_hits=5,
            negative_hits=2,
            total_results=100,
            recall=0.5,
            fpr=0.1,
            f1=0.6,
        )
        with pytest.raises(AttributeError):
            p.value = 0.7  # type: ignore[misc]


class TestParameterSensitivity:
    def test_defaults(self) -> None:
        ps = ParameterSensitivity(
            step_id="s1",
            param_name="evalue",
            current_value=1e-5,
        )
        assert ps.sweep_points == []
        assert ps.recommended_value == 0.0
        assert ps.recommendation == ""


class TestStepAnalysisResult:
    def test_empty_defaults(self) -> None:
        sar = StepAnalysisResult()
        assert sar.step_evaluations == []
        assert sar.operator_comparisons == []
        assert sar.step_contributions == []
        assert sar.parameter_sensitivities == []
