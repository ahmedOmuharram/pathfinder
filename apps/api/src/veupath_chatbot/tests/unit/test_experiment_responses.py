"""Tests for experiment response Pydantic models — camelCase, from_attributes, construction."""

import pytest
from pydantic import BaseModel, ValidationError

from veupath_chatbot.transport.http.schemas.experiment_responses import (
    BootstrapResultResponse,
    ConfidenceIntervalResponse,
    ConfusionMatrixResponse,
    ControlSetSummaryResponse,
    CrossValidationResultResponse,
    EnrichmentResultResponse,
    EnrichmentTermResponse,
    ExperimentConfigResponse,
    ExperimentMetricsResponse,
    ExperimentProgressDataResponse,
    ExperimentResponse,
    ExperimentSummaryResponse,
    FoldMetricsResponse,
    GeneInfoResponse,
    NegativeSetVariantResponse,
    OperatorComparisonResponse,
    OperatorKnobResponse,
    OperatorVariantResponse,
    OptimizationResultResponse,
    OptimizationSpecResponse,
    ParameterSensitivityResponse,
    ParameterSweepPointResponse,
    RankMetricsResponse,
    StepAnalysisProgressDataResponse,
    StepAnalysisResultResponse,
    StepContributionResponse,
    StepEvaluationResponse,
    ThresholdKnobResponse,
    TreeOptimizationResultResponse,
    TreeOptimizationTrialResponse,
    TrialProgressDataResponse,
)


def _has_snake_case_key(dumped: dict) -> str | None:
    """Return the first snake_case key found at top level, or None."""
    for key in dumped:
        if "_" in key and not key.startswith("_"):
            return key
    return None


def _check_nested_snake_case(dumped: dict) -> str | None:
    """Recursively check for snake_case keys."""
    for key, value in dumped.items():
        if "_" in key and not key.startswith("_"):
            return key
        if isinstance(value, dict):
            found = _check_nested_snake_case(value)
            if found:
                return found
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _check_nested_snake_case(item)
                    if found:
                        return found
    return None


# ---------------------------------------------------------------------------
# Minimal construction data for every model
# ---------------------------------------------------------------------------

_CONFUSION = {
    "truePositives": 10,
    "falsePositives": 2,
    "trueNegatives": 80,
    "falseNegatives": 5,
}
_METRICS = {
    "confusionMatrix": _CONFUSION,
    "sensitivity": 0.67,
    "specificity": 0.98,
    "precision": 0.83,
    "f1Score": 0.74,
    "mcc": 0.7,
    "balancedAccuracy": 0.82,
}
_ENRICHMENT_TERM = {
    "termId": "GO:0001234",
    "termName": "kinase activity",
    "geneCount": 5,
    "backgroundCount": 100,
    "foldEnrichment": 2.5,
    "oddsRatio": 3.0,
    "pValue": 0.001,
    "fdr": 0.01,
    "bonferroni": 0.05,
}
_STEP_CONTRIBUTION = {
    "stepId": "s1",
    "searchName": "GenesByOrthologs",
    "baselineRecall": 0.8,
    "ablatedRecall": 0.5,
    "recallDelta": -0.3,
    "baselineFpr": 0.1,
    "ablatedFpr": 0.05,
    "fprDelta": -0.05,
    "verdict": "essential",
}
_TREE_TRIAL = {
    "trialNumber": 1,
    "score": 0.85,
}
_BOOTSTRAP = {
    "nIterations": 100,
}
_OPTIMIZATION_RESULT = {
    "optimizationId": "opt-1",
    "status": "completed",
}
_CONFIG = {
    "siteId": "PlasmoDB",
    "recordType": "gene",
    "searchName": "GenesByText",
    "parameters": {"text_expression": "kinase"},
    "positiveControls": ["PF3D7_0100100"],
    "negativeControls": ["PF3D7_0200200"],
    "controlsSearchName": "GeneByLocusTag",
    "controlsParamName": "single_gene_id",
}
_EXPERIMENT = {
    "id": "exp-1",
    "config": _CONFIG,
}
_SUMMARY = {
    "id": "exp-1",
    "name": "Test Experiment",
    "siteId": "PlasmoDB",
    "searchName": "GenesByText",
    "recordType": "gene",
    "mode": "single",
    "status": "completed",
    "totalPositives": 10,
    "totalNegatives": 80,
    "createdAt": "2026-03-14T00:00:00Z",
}


MODELS_WITH_MINIMAL_DATA: list[tuple[type[BaseModel], dict]] = [
    (ConfusionMatrixResponse, _CONFUSION),
    (ExperimentMetricsResponse, _METRICS),
    (GeneInfoResponse, {"id": "PF3D7_0100100"}),
    (EnrichmentTermResponse, _ENRICHMENT_TERM),
    (
        EnrichmentResultResponse,
        {"analysisType": "go_function", "terms": [_ENRICHMENT_TERM]},
    ),
    (StepContributionResponse, _STEP_CONTRIBUTION),
    (TreeOptimizationTrialResponse, _TREE_TRIAL),
    (BootstrapResultResponse, _BOOTSTRAP),
    (OptimizationResultResponse, _OPTIMIZATION_RESULT),
    (ExperimentConfigResponse, _CONFIG),
    (ExperimentResponse, _EXPERIMENT),
    (ExperimentSummaryResponse, _SUMMARY),
    (RankMetricsResponse, {}),
    (ConfidenceIntervalResponse, {}),
    (NegativeSetVariantResponse, {"label": "random", "rankMetrics": {}}),
    (
        StepEvaluationResponse,
        {
            "stepId": "s1",
            "searchName": "GenesByText",
            "displayName": "Text Search",
            "resultCount": 100,
            "positiveHits": 8,
            "positiveTotal": 10,
            "negativeHits": 5,
            "negativeTotal": 80,
            "recall": 0.8,
            "falsePositiveRate": 0.0625,
        },
    ),
    (
        OperatorVariantResponse,
        {
            "operator": "INTERSECT",
            "positiveHits": 8,
            "negativeHits": 2,
            "totalResults": 10,
            "recall": 0.8,
            "falsePositiveRate": 0.025,
            "f1Score": 0.75,
        },
    ),
    (
        OperatorComparisonResponse,
        {"combineNodeId": "c1", "currentOperator": "INTERSECT"},
    ),
    (
        ParameterSweepPointResponse,
        {
            "value": 0.5,
            "positiveHits": 8,
            "negativeHits": 2,
            "totalResults": 10,
            "recall": 0.8,
            "fpr": 0.025,
            "f1": 0.75,
        },
    ),
    (
        ParameterSensitivityResponse,
        {"stepId": "s1", "paramName": "threshold", "currentValue": 0.5},
    ),
    (StepAnalysisResultResponse, {}),
    (OptimizationSpecResponse, {"name": "threshold", "type": "numeric"}),
    (
        ThresholdKnobResponse,
        {"stepId": "s1", "paramName": "threshold", "minVal": 0.0, "maxVal": 1.0},
    ),
    (OperatorKnobResponse, {"combineNodeId": "c1"}),
    (TreeOptimizationResultResponse, {}),
    (
        FoldMetricsResponse,
        {"foldIndex": 0, "metrics": _METRICS},
    ),
    (
        CrossValidationResultResponse,
        {
            "k": 5,
            "folds": [{"foldIndex": 0, "metrics": _METRICS}],
            "meanMetrics": _METRICS,
        },
    ),
    (
        ControlSetSummaryResponse,
        {
            "id": "cs-1",
            "name": "Test",
            "source": "paper",
            "positiveCount": 10,
            "negativeCount": 80,
        },
    ),
    (
        TrialProgressDataResponse,
        {"trialNumber": 1, "totalTrials": 10, "status": "running"},
    ),
    (StepAnalysisProgressDataResponse, {"phase": "step_evaluation"}),
    (ExperimentProgressDataResponse, {"phase": "evaluating"}),
]


@pytest.mark.parametrize(
    ("model_cls", "data"),
    MODELS_WITH_MINIMAL_DATA,
    ids=[cls.__name__ for cls, _ in MODELS_WITH_MINIMAL_DATA],
)
class TestExperimentResponseModels:
    """All experiment response models must serialize with camelCase."""

    def test_instantiation(self, model_cls: type[BaseModel], data: dict):
        instance = model_cls(**data)
        assert instance is not None

    def test_camel_case_serialization(self, model_cls: type[BaseModel], data: dict):
        instance = model_cls(**data)
        dumped = instance.model_dump(by_alias=True)
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None, f"snake_case key in {model_cls.__name__}: {snake_key}"

    def test_from_attributes_config(self, model_cls: type[BaseModel], data: dict):
        """Models with from_attributes=True should accept attribute-style objects."""
        config = model_cls.model_config
        if config.get("from_attributes"):
            # Create a simple namespace object from the data
            instance = model_cls(**data)
            # Reconstruct from the model itself (which has attributes)
            reconstructed = model_cls.model_validate(instance)
            assert reconstructed.model_dump(by_alias=True) == instance.model_dump(
                by_alias=True
            )


class TestConfusionMatrixResponse:
    """Detailed tests for ConfusionMatrixResponse."""

    def test_all_fields_required(self):
        with pytest.raises(ValidationError):
            ConfusionMatrixResponse()

    def test_field_values(self):
        cm = ConfusionMatrixResponse(**_CONFUSION)
        assert cm.true_positives == 10
        assert cm.false_positives == 2
        assert cm.true_negatives == 80
        assert cm.false_negatives == 5


class TestExperimentMetricsResponse:
    """Detailed tests for ExperimentMetricsResponse."""

    def test_nested_confusion_matrix_camel_case(self):
        metrics = ExperimentMetricsResponse(**_METRICS)
        dumped = metrics.model_dump(by_alias=True)
        snake_key = _check_nested_snake_case(dumped)
        assert snake_key is None, f"Nested snake_case key: {snake_key}"

    def test_default_fields(self):
        metrics = ExperimentMetricsResponse(**_METRICS)
        assert metrics.negative_predictive_value == 0.0
        assert metrics.false_positive_rate == 0.0
        assert metrics.youdens_j == 0.0
        assert metrics.total_results == 0


class TestExperimentConfigResponse:
    """ExperimentConfigResponse is the largest model — test thoroughly."""

    def test_defaults(self):
        config = ExperimentConfigResponse(**_CONFIG)
        assert config.controls_value_format == "newline"
        assert config.enable_cross_validation is False
        assert config.k_folds == 5
        assert config.mode == "single"
        assert config.optimization_budget == 30
        assert config.optimization_objective == "balanced_accuracy"

    def test_full_serialization_camel_case(self):
        config = ExperimentConfigResponse(**_CONFIG)
        dumped = config.model_dump(by_alias=True)
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None, f"snake_case key: {snake_key}"


class TestExperimentResponse:
    """ExperimentResponse wraps config + results."""

    def test_minimal_construction(self):
        exp = ExperimentResponse(**_EXPERIMENT)
        assert exp.id == "exp-1"
        assert exp.status == "pending"

    def test_top_level_camel_case(self):
        exp = ExperimentResponse(**_EXPERIMENT)
        dumped = exp.model_dump(by_alias=True)
        # Check top-level keys only (nested user data like `parameters`
        # contains user-provided keys that are not Pydantic field aliases).
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None, f"snake_case key at top level: {snake_key}"

    def test_config_fields_camel_case(self):
        exp = ExperimentResponse(**_EXPERIMENT)
        dumped = exp.model_dump(by_alias=True)
        config_dumped = dumped["config"]
        snake_key = _has_snake_case_key(config_dumped)
        assert snake_key is None, f"snake_case key in config: {snake_key}"


class TestExperimentSummaryResponse:
    """Lightweight summary for list views."""

    def test_construction_and_serialization(self):
        summary = ExperimentSummaryResponse(**_SUMMARY)
        dumped = summary.model_dump(by_alias=True)
        assert dumped["siteId"] == "PlasmoDB"
        assert dumped["searchName"] == "GenesByText"
        assert dumped["totalPositives"] == 10
        snake_key = _has_snake_case_key(dumped)
        assert snake_key is None
