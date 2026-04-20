"""Internal endpoints — not for production use."""

from fastapi import APIRouter

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.transport.http.schemas.experiment_responses import (
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
from pathfinder.transport.http.schemas.optimization import (
    OptimizationParameterSpecData,
    OptimizationProgressEventData,
    OptimizationTrialData,
)

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


class ExperimentSchemaIndex(CamelModel):
    """Index of all experiment response schemas. Never called -- exists for OpenAPI generation."""

    experiment: ExperimentResponse | None = None
    experiment_summary: ExperimentSummaryResponse | None = None
    experiment_config: ExperimentConfigResponse | None = None
    confusion_matrix: ConfusionMatrixResponse | None = None
    experiment_metrics: ExperimentMetricsResponse | None = None
    gene_info: GeneInfoResponse | None = None
    fold_metrics: FoldMetricsResponse | None = None
    cross_validation_result: CrossValidationResultResponse | None = None
    enrichment_term: EnrichmentTermResponse | None = None
    enrichment_result: EnrichmentResultResponse | None = None
    rank_metrics: RankMetricsResponse | None = None
    confidence_interval: ConfidenceIntervalResponse | None = None
    negative_set_variant: NegativeSetVariantResponse | None = None
    bootstrap_result: BootstrapResultResponse | None = None
    step_evaluation: StepEvaluationResponse | None = None
    operator_variant: OperatorVariantResponse | None = None
    operator_comparison: OperatorComparisonResponse | None = None
    step_contribution: StepContributionResponse | None = None
    parameter_sweep_point: ParameterSweepPointResponse | None = None
    parameter_sensitivity: ParameterSensitivityResponse | None = None
    step_analysis_result: StepAnalysisResultResponse | None = None
    optimization_spec: OptimizationSpecResponse | None = None
    threshold_knob: ThresholdKnobResponse | None = None
    operator_knob: OperatorKnobResponse | None = None
    tree_optimization_trial: TreeOptimizationTrialResponse | None = None
    tree_optimization_result: TreeOptimizationResultResponse | None = None
    trial_progress_data: TrialProgressDataResponse | None = None
    step_analysis_progress_data: StepAnalysisProgressDataResponse | None = None
    experiment_progress_data: ExperimentProgressDataResponse | None = None
    optimization_result: OptimizationResultResponse | None = None
    control_set_summary: ControlSetSummaryResponse | None = None
    optimization_progress: OptimizationProgressEventData | None = None
    optimization_trial: OptimizationTrialData | None = None
    optimization_parameter_spec: OptimizationParameterSpecData | None = None


@router.get(
    "/experiment-schemas",
    response_model=ExperimentSchemaIndex,
    include_in_schema=True,
)
async def experiment_schemas() -> ExperimentSchemaIndex:
    """Experiment response schemas -- for OpenAPI generation only."""
    return ExperimentSchemaIndex()
