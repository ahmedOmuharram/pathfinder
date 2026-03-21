"""Unit tests for workbench read tools.

Tests WorkbenchReadToolsMixin methods: get_evaluation_summary,
get_enrichment_results, get_confidence_scores, get_step_contributions,
get_experiment_config, get_ensemble_analysis, and get_result_gene_lists.
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.workbench_read_tools import WorkbenchReadToolsMixin
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    CrossValidationResult,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    FoldMetrics,
    GeneInfo,
    StepContribution,
)
from veupath_chatbot.services.experiment.types.step_analysis import StepAnalysisResult


def _cfg() -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmodb",
        record_type="gene",
        search_name="GenesByTextSearch",
        parameters={},
        positive_controls=["g1", "g2"],
        negative_controls=["n1", "n2"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


def _confusion_matrix() -> ConfusionMatrix:
    return ConfusionMatrix(
        true_positives=2,
        false_positives=1,
        true_negatives=1,
        false_negatives=0,
    )


def _metrics() -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=_confusion_matrix(),
        sensitivity=1.0,
        specificity=0.5,
        precision=0.667,
        f1_score=0.8,
        mcc=0.577,
        balanced_accuracy=0.75,
        total_results=3,
        total_positives=2,
        total_negatives=2,
    )


def _exp(
    exp_id: str = "exp_001",
    with_metrics: bool = False,
    with_enrichment: bool = False,
    with_cross_validation: bool = False,
    with_step_analysis: bool = False,
) -> Experiment:
    exp = Experiment(id=exp_id, config=_cfg(), status="completed")
    exp.true_positive_genes = [
        GeneInfo(id="g1", name="PfCRT"),
        GeneInfo(id="g2", name="PfMDR1"),
    ]
    exp.false_positive_genes = [GeneInfo(id="n1")]
    exp.false_negative_genes = []
    exp.true_negative_genes = [GeneInfo(id="n2")]
    exp.wdk_strategy_id = 42
    exp.wdk_step_id = 99

    if with_metrics:
        exp.metrics = _metrics()

    if with_enrichment:
        exp.enrichment_results = [
            EnrichmentResult(
                analysis_type="go_function",
                terms=[
                    EnrichmentTerm(
                        term_id="GO:0006813",
                        term_name="potassium ion transport",
                        gene_count=12,
                        background_count=50,
                        fold_enrichment=3.2,
                        odds_ratio=4.1,
                        p_value=0.001,
                        fdr=0.01,
                        bonferroni=0.05,
                        genes=["g1", "g2"],
                    )
                ],
                total_genes_analyzed=3,
                background_size=5000,
            )
        ]

    if with_cross_validation:
        fold_metrics = FoldMetrics(
            fold_index=0,
            metrics=_metrics(),
            positive_control_ids=["g1"],
            negative_control_ids=["n1"],
        )
        exp.cross_validation = CrossValidationResult(
            k=5,
            folds=[fold_metrics],
            mean_metrics=_metrics(),
            std_metrics={"sensitivity": 0.05},
            overfitting_score=0.1,
            overfitting_level="low",
        )

    if with_step_analysis:
        exp.step_analysis = StepAnalysisResult(
            step_contributions=[
                StepContribution(
                    step_id="step_1",
                    search_name="GenesByTextSearch",
                    baseline_recall=0.8,
                    ablated_recall=0.5,
                    recall_delta=0.3,
                    baseline_fpr=0.2,
                    ablated_fpr=0.25,
                    fpr_delta=-0.05,
                    verdict="essential",
                    narrative="This step contributes significantly.",
                )
            ]
        )

    return exp


class FakeAgent(WorkbenchReadToolsMixin):
    """Minimal concrete class for testing the mixin."""

    def __init__(self, site_id: str, experiment_id: str) -> None:
        self.site_id = site_id
        self.experiment_id = experiment_id


def _make_mock_store(experiment: Experiment | None) -> AsyncMock:
    store = AsyncMock()
    store.aget = AsyncMock(return_value=experiment)
    return store


# ---------------------------------------------------------------------------
# get_evaluation_summary
# ---------------------------------------------------------------------------


class TestGetEvaluationSummary:
    async def test_returns_summary_with_valid_metrics(self) -> None:
        exp = _exp(with_metrics=True)
        store = _make_mock_store(exp)

        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_evaluation_summary()

        assert "error" not in result
        assert "metrics" in result
        assert "classificationCounts" in result
        assert "sampleGeneIds" in result
        assert result["status"] == "completed"

        counts = result["classificationCounts"]
        assert isinstance(counts, dict)
        assert counts["truePositives"] == 2
        assert counts["falsePositives"] == 1
        assert counts["falseNegatives"] == 0
        assert counts["trueNegatives"] == 1

        sample_ids = result["sampleGeneIds"]
        assert isinstance(sample_ids, dict)
        assert "g1" in sample_ids["truePositives"]
        assert "g2" in sample_ids["truePositives"]

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_evaluation_summary()

        assert "error" in result
        assert result["error"] == "Experiment not found"

    async def test_returns_error_when_no_metrics(self) -> None:
        exp = _exp(with_metrics=False)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_evaluation_summary()

        assert "error" in result
        assert "metrics" in result["error"]

    async def test_sample_gene_ids_capped_at_five(self) -> None:
        exp = _exp(with_metrics=True)
        # Add more than 5 TPs to confirm capping
        exp.true_positive_genes = [GeneInfo(id=f"g{i}") for i in range(10)]
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_evaluation_summary()

        sample_ids = result["sampleGeneIds"]
        assert isinstance(sample_ids, dict)
        assert len(sample_ids["truePositives"]) == 5


# ---------------------------------------------------------------------------
# get_enrichment_results
# ---------------------------------------------------------------------------


class TestGetEnrichmentResults:
    async def test_returns_enrichment_results(self) -> None:
        exp = _exp(with_enrichment=True)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_enrichment_results()

        assert "error" not in result
        assert "enrichmentResults" in result
        assert result["count"] == 1
        enrichment_list = result["enrichmentResults"]
        assert isinstance(enrichment_list, list)
        assert enrichment_list[0]["analysisType"] == "go_function"

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_enrichment_results()

        assert "error" in result
        assert result["error"] == "Experiment not found"

    async def test_returns_error_when_no_enrichment_results(self) -> None:
        exp = _exp(with_enrichment=False)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_enrichment_results()

        assert "error" in result
        assert "enrichment" in result["error"].lower()


# ---------------------------------------------------------------------------
# get_confidence_scores
# ---------------------------------------------------------------------------


class TestGetConfidenceScores:
    async def test_returns_cross_validation_results(self) -> None:
        exp = _exp(with_cross_validation=True)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_confidence_scores()

        assert "error" not in result
        assert "crossValidation" in result
        cv = result["crossValidation"]
        assert isinstance(cv, dict)
        assert cv["k"] == 5
        assert cv["overfittingLevel"] == "low"

    async def test_returns_error_when_no_cross_validation(self) -> None:
        exp = _exp(with_cross_validation=False)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_confidence_scores()

        assert "error" in result
        assert "cross-validation" in result["error"].lower()

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_confidence_scores()

        assert "error" in result
        assert result["error"] == "Experiment not found"


# ---------------------------------------------------------------------------
# get_step_contributions
# ---------------------------------------------------------------------------


class TestGetStepContributions:
    async def test_returns_step_contributions(self) -> None:
        exp = _exp(with_step_analysis=True)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_step_contributions()

        assert "error" not in result
        assert "stepContributions" in result
        assert result["count"] == 1
        contributions = result["stepContributions"]
        assert isinstance(contributions, list)
        assert contributions[0]["stepId"] == "step_1"
        assert contributions[0]["verdict"] == "essential"

    async def test_returns_error_when_no_step_analysis(self) -> None:
        exp = _exp(with_step_analysis=False)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_step_contributions()

        assert "error" in result
        assert "step analysis" in result["error"].lower()

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_step_contributions()

        assert "error" in result
        assert result["error"] == "Experiment not found"


# ---------------------------------------------------------------------------
# get_experiment_config
# ---------------------------------------------------------------------------


class TestGetExperimentConfig:
    async def test_returns_config_fields(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_experiment_config()

        assert "error" not in result
        assert "config" in result
        assert result["status"] == "completed"
        assert result["wdkStrategyId"] == 42
        assert result["wdkStepId"] == 99
        assert result["notes"] is None

        config = result["config"]
        assert isinstance(config, dict)
        assert config["siteId"] == "plasmodb"
        assert config["searchName"] == "GenesByTextSearch"

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_experiment_config()

        assert "error" in result
        assert result["error"] == "Experiment not found"


# ---------------------------------------------------------------------------
# get_ensemble_analysis
# ---------------------------------------------------------------------------


class TestGetEnsembleAnalysis:
    async def test_returns_step_analysis(self) -> None:
        exp = _exp(with_step_analysis=True)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_ensemble_analysis()

        assert "error" not in result
        assert "stepAnalysis" in result
        analysis = result["stepAnalysis"]
        assert isinstance(analysis, dict)
        assert "stepContributions" in analysis
        assert len(analysis["stepContributions"]) == 1

    async def test_returns_error_when_no_step_analysis(self) -> None:
        exp = _exp(with_step_analysis=False)
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_ensemble_analysis()

        assert "error" in result
        assert "step analysis" in result["error"].lower()

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_ensemble_analysis()

        assert "error" in result
        assert result["error"] == "Experiment not found"


# ---------------------------------------------------------------------------
# get_result_gene_lists
# ---------------------------------------------------------------------------


class TestGetResultGeneLists:
    async def test_returns_true_positives(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="tp", limit=10)

        assert "error" not in result
        assert result["classification"] == "tp"
        assert result["total"] == 2
        assert result["returned"] == 2
        genes = result["genes"]
        assert isinstance(genes, list)
        gene_ids = [g["id"] for g in genes]
        assert "g1" in gene_ids
        assert "g2" in gene_ids

    async def test_returns_false_positives(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="fp")

        assert "error" not in result
        assert result["classification"] == "fp"
        assert result["total"] == 1

    async def test_returns_true_negatives(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="tn")

        assert "error" not in result
        assert result["classification"] == "tn"
        assert result["total"] == 1

    async def test_returns_false_negatives_empty(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="fn")

        assert "error" not in result
        assert result["classification"] == "fn"
        assert result["total"] == 0
        assert result["returned"] == 0

    async def test_returns_error_for_invalid_classification(self) -> None:
        exp = _exp()
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="invalid")

        assert "error" in result
        assert "invalid" in result["error"].lower()

    async def test_returns_error_when_experiment_not_found(self) -> None:
        store = _make_mock_store(None)
        agent = FakeAgent("plasmodb", "missing")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="tp")

        assert "error" in result
        assert result["error"] == "Experiment not found"

    async def test_limit_is_capped_at_200(self) -> None:
        exp = _exp()
        exp.true_positive_genes = [GeneInfo(id=f"g{i}") for i in range(300)]
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="tp", limit=500)

        assert "error" not in result
        assert result["returned"] == 200
        assert result["total"] == 300

    async def test_limit_default_is_50(self) -> None:
        exp = _exp()
        exp.true_positive_genes = [GeneInfo(id=f"g{i}") for i in range(100)]
        store = _make_mock_store(exp)
        agent = FakeAgent("plasmodb", "exp_001")

        with patch(
            "veupath_chatbot.ai.tools.workbench_read_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.get_result_gene_lists(classification="tp")

        assert "error" not in result
        assert result["returned"] == 50
        assert result["total"] == 100
