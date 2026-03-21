"""Tests for experiment serialization roundtrips and custom deserialization logic."""

from veupath_chatbot.services.experiment._deserialize import experiment_from_json
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    ExperimentMode,
    GeneInfo,
    experiment_to_json,
)


def _make_experiment(mode: ExperimentMode = "single") -> Experiment:
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
    exp.true_positive_genes = [
        GeneInfo(id="PF3D7_0100100", name="PfKin1", organism="P. falciparum"),
    ]
    exp.false_negative_genes = [GeneInfo(id="PF3D7_0100200")]
    return exp


class TestEnrichmentDeduplication:
    """Tests for the only custom logic in experiment_from_json."""

    def test_duplicate_analysis_types_keep_last(self) -> None:
        d = {
            "id": "exp-001",
            "config": {
                "siteId": "plasmo",
                "recordType": "gene",
                "searchName": "GenesByText",
                "parameters": {"text": "kinase"},
                "positiveControls": ["g1"],
                "negativeControls": ["n1"],
                "controlsSearchName": "GeneByLocusTag",
                "controlsParamName": "single_gene_id",
            },
            "status": "completed",
            "createdAt": "2025-01-01T00:00:00",
            "enrichmentResults": [
                {
                    "analysisType": "go_process",
                    "terms": [],
                    "totalGenesAnalyzed": 50,
                    "backgroundSize": 1000,
                },
                {
                    "analysisType": "pathway",
                    "terms": [],
                    "totalGenesAnalyzed": 60,
                    "backgroundSize": 2000,
                },
                {
                    "analysisType": "go_process",
                    "terms": [],
                    "totalGenesAnalyzed": 80,
                    "backgroundSize": 3000,
                },
            ],
        }
        exp = experiment_from_json(d)
        assert len(exp.enrichment_results) == 2
        types = [er.analysis_type for er in exp.enrichment_results]
        assert "go_process" in types
        assert "pathway" in types
        go = next(
            er for er in exp.enrichment_results if er.analysis_type == "go_process"
        )
        assert go.total_genes_analyzed == 80


class TestExperimentRoundtrip:
    """Roundtrip tests catch alias misconfigurations (camelCase <-> snake_case)."""

    def test_single_mode(self) -> None:
        exp = _make_experiment(mode="single")
        restored = experiment_from_json(experiment_to_json(exp))

        assert restored.id == exp.id
        assert restored.status == "completed"
        assert restored.config.site_id == "plasmodb"
        assert restored.config.mode == "single"
        assert restored.config.search_name == "GenesByTextSearch"
        assert restored.config.positive_controls == ["PF3D7_0100100", "PF3D7_0100200"]

    def test_multi_step_mode(self) -> None:
        exp = _make_experiment(mode="multi-step")
        restored = experiment_from_json(experiment_to_json(exp))

        assert restored.config.mode == "multi-step"
        assert restored.config.step_tree is not None
        assert restored.config.enable_step_analysis is True
        assert restored.config.sort_attribute == "score"

    def test_import_mode(self) -> None:
        exp = _make_experiment(mode="import")
        restored = experiment_from_json(experiment_to_json(exp))

        assert restored.config.mode == "import"
        assert restored.config.source_strategy_id == "strat_123"

    def test_gene_lists_preserved(self) -> None:
        exp = _make_experiment()
        restored = experiment_from_json(experiment_to_json(exp))

        assert len(restored.true_positive_genes) == 1
        assert restored.true_positive_genes[0].id == "PF3D7_0100100"
        assert restored.true_positive_genes[0].name == "PfKin1"
        assert len(restored.false_negative_genes) == 1

    def test_empty_experiment(self) -> None:
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
        restored = experiment_from_json(experiment_to_json(exp))

        assert restored.id == "exp_empty"
        assert restored.config.site_id == "toxodb"
        assert restored.metrics is None

    def test_benchmark_fields(self) -> None:
        exp = _make_experiment()
        exp.benchmark_id = "bench_001"
        exp.control_set_label = "Published Paper Set"
        exp.is_primary_benchmark = True

        restored = experiment_from_json(experiment_to_json(exp))

        assert restored.benchmark_id == "bench_001"
        assert restored.control_set_label == "Published Paper Set"
        assert restored.is_primary_benchmark is True
