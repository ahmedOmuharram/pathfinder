"""Unit tests for experiment serialization and deserialization roundtrips."""

from __future__ import annotations

from veupath_chatbot.services.experiment._deserialize import experiment_from_json
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    GeneInfo,
    RankMetrics,
    experiment_to_json,
    metrics_to_json,
    rank_metrics_to_json,
)


def _make_metrics() -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=8,
            false_positives=3,
            true_negatives=17,
            false_negatives=2,
        ),
        sensitivity=0.8,
        specificity=0.85,
        precision=0.7273,
        negative_predictive_value=0.8947,
        false_positive_rate=0.15,
        false_negative_rate=0.2,
        f1_score=0.7619,
        mcc=0.6122,
        balanced_accuracy=0.825,
        youdens_j=0.65,
        total_results=100,
        total_positives=10,
        total_negatives=20,
    )


def _make_experiment(mode: str = "single") -> Experiment:
    config = ExperimentConfig(
        site_id="plasmodb",
        record_type="gene",
        search_name="GenesByTextSearch",
        parameters={"text_expression": "kinase"},
        positive_controls=["PF3D7_0100100", "PF3D7_0100200"],
        negative_controls=["PF3D7_0900100"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
        controls_value_format="newline",
        mode=mode,
        name="Test Experiment",
        description="A test experiment",
        step_tree={"id": "s1", "searchName": "TestSearch"}
        if mode == "multi-step"
        else None,
        source_strategy_id="strat_123" if mode == "import" else None,
        enable_step_analysis=mode == "multi-step",
        sort_attribute="score" if mode == "multi-step" else None,
    )
    exp = Experiment(
        id="exp_test_001",
        config=config,
        status="completed",
        created_at="2024-06-15T12:00:00Z",
        completed_at="2024-06-15T12:01:30Z",
    )
    exp.metrics = _make_metrics()
    exp.true_positive_genes = [
        GeneInfo(id="PF3D7_0100100", name="PfKin1", organism="P. falciparum"),
    ]
    exp.false_negative_genes = [
        GeneInfo(id="PF3D7_0100200"),
    ]
    return exp


class TestMetricsSerialization:
    def test_metrics_to_json_camel_case(self) -> None:
        m = _make_metrics()
        j = metrics_to_json(m)
        assert "confusionMatrix" in j
        assert "truePositives" in j["confusionMatrix"]
        assert j["sensitivity"] == 0.8
        assert j["f1Score"] == 0.7619
        assert j["totalResults"] == 100

    def test_metrics_roundtrip_values(self) -> None:
        m = _make_metrics()
        j = metrics_to_json(m)
        assert j["confusionMatrix"]["truePositives"] == 8
        assert j["confusionMatrix"]["falseNegatives"] == 2


class TestRankMetricsSerialization:
    def test_rank_metrics_to_json(self) -> None:
        rm = RankMetrics(
            precision_at_k={10: 0.5, 50: 0.3},
            recall_at_k={10: 0.25, 50: 0.75},
            enrichment_at_k={10: 2.5, 50: 1.5},
            pr_curve=[(0.5, 0.25), (0.3, 0.75)],
            list_size_vs_recall=[(10, 0.25), (50, 0.75)],
            total_results=200,
        )
        j = rank_metrics_to_json(rm)
        # Keys should be stringified
        assert j["precisionAtK"]["10"] == 0.5
        assert j["recallAtK"]["50"] == 0.75
        assert j["totalResults"] == 200
        assert len(j["prCurve"]) == 2


class TestExperimentRoundtrip:
    def test_single_mode_roundtrip(self) -> None:
        exp = _make_experiment(mode="single")
        j = experiment_to_json(exp)
        restored = experiment_from_json(j)

        assert restored.id == exp.id
        assert restored.status == "completed"
        assert restored.config.site_id == "plasmodb"
        assert restored.config.mode == "single"
        assert restored.config.search_name == "GenesByTextSearch"
        assert restored.config.positive_controls == ["PF3D7_0100100", "PF3D7_0100200"]
        assert restored.metrics is not None
        assert restored.metrics.confusion_matrix.true_positives == 8

    def test_multi_step_mode_roundtrip(self) -> None:
        exp = _make_experiment(mode="multi-step")
        j = experiment_to_json(exp)
        restored = experiment_from_json(j)

        assert restored.config.mode == "multi-step"
        assert restored.config.step_tree is not None
        assert restored.config.enable_step_analysis is True
        assert restored.config.sort_attribute == "score"

    def test_import_mode_roundtrip(self) -> None:
        exp = _make_experiment(mode="import")
        j = experiment_to_json(exp)
        restored = experiment_from_json(j)

        assert restored.config.mode == "import"
        assert restored.config.source_strategy_id == "strat_123"

    def test_gene_lists_preserved(self) -> None:
        exp = _make_experiment()
        j = experiment_to_json(exp)
        restored = experiment_from_json(j)

        assert len(restored.true_positive_genes) == 1
        assert restored.true_positive_genes[0].id == "PF3D7_0100100"
        assert restored.true_positive_genes[0].name == "PfKin1"
        assert len(restored.false_negative_genes) == 1

    def test_empty_experiment_roundtrip(self) -> None:
        config = ExperimentConfig(
            site_id="toxodb",
            record_type="gene",
            search_name="GenesByTextSearch",
            parameters={},
            positive_controls=[],
            negative_controls=[],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        )
        exp = Experiment(id="exp_empty", config=config, created_at="2024-01-01")
        j = experiment_to_json(exp)
        restored = experiment_from_json(j)
        assert restored.id == "exp_empty"
        assert restored.config.site_id == "toxodb"
        assert restored.metrics is None
        assert restored.cross_validation is None

    def test_benchmark_fields_preserved(self) -> None:
        exp = _make_experiment()
        exp.benchmark_id = "bench_001"
        exp.control_set_label = "Published Paper Set"
        exp.is_primary_benchmark = True

        j = experiment_to_json(exp)
        restored = experiment_from_json(j)

        assert restored.benchmark_id == "bench_001"
        assert restored.control_set_label == "Published Paper Set"
        assert restored.is_primary_benchmark is True
