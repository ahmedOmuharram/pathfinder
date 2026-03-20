"""Internal endpoints — not for production use."""

from fastapi import APIRouter
from pydantic import BaseModel

from veupath_chatbot.transport.http.schemas.chat import (
    CitationResponse,
    PlanningArtifactResponse,
)
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
from veupath_chatbot.transport.http.schemas.optimization import (
    OptimizationParameterSpecData,
    OptimizationProgressEventData,
    OptimizationTrialData,
)
from veupath_chatbot.transport.http.schemas.sse import (
    AssistantDeltaEventData,
    AssistantMessageEventData,
    CitationsEventData,
    ErrorEventData,
    ExecutorBuildRequestEventData,
    GeneSetSummary,
    GraphClearedEventData,
    GraphPlanEventData,
    GraphSnapshotEventData,
    MessageEndEventData,
    MessageStartEventData,
    ModelSelectedEventData,
    PlanningArtifactEventData,
    ReasoningEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
    StrategyUpdateEventData,
    SubKaniTaskEndEventData,
    SubKaniTaskStartEventData,
    SubKaniToolCallEndEventData,
    SubKaniToolCallStartEventData,
    TokenUsagePartialEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
    UserMessageEventData,
    WorkbenchGeneSetEventData,
)

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


class SSESchemaIndex(BaseModel):
    """Index of all SSE event data schemas. Never called -- exists for OpenAPI generation."""

    message_start: MessageStartEventData | None = None
    user_message: UserMessageEventData | None = None
    assistant_delta: AssistantDeltaEventData | None = None
    assistant_message: AssistantMessageEventData | None = None
    tool_call_start: ToolCallStartEventData | None = None
    tool_call_end: ToolCallEndEventData | None = None
    subkani_task_start: SubKaniTaskStartEventData | None = None
    subkani_tool_call_start: SubKaniToolCallStartEventData | None = None
    subkani_tool_call_end: SubKaniToolCallEndEventData | None = None
    subkani_task_end: SubKaniTaskEndEventData | None = None
    token_usage_partial: TokenUsagePartialEventData | None = None
    model_selected: ModelSelectedEventData | None = None
    optimization_progress: OptimizationProgressEventData | None = None
    optimization_trial: OptimizationTrialData | None = None
    optimization_parameter_spec: OptimizationParameterSpecData | None = None
    error: ErrorEventData | None = None
    graph_snapshot: GraphSnapshotEventData | None = None
    strategy_meta: StrategyMetaEventData | None = None
    graph_plan: GraphPlanEventData | None = None
    strategy_update: StrategyUpdateEventData | None = None
    strategy_link: StrategyLinkEventData | None = None
    graph_cleared: GraphClearedEventData | None = None
    executor_build_request: ExecutorBuildRequestEventData | None = None
    gene_set_summary: GeneSetSummary | None = None
    workbench_gene_set: WorkbenchGeneSetEventData | None = None
    citations: CitationsEventData | None = None
    planning_artifact: PlanningArtifactEventData | None = None
    reasoning: ReasoningEventData | None = None
    message_end: MessageEndEventData | None = None


@router.get("/sse-schemas", response_model=SSESchemaIndex, include_in_schema=True)
async def sse_schemas() -> SSESchemaIndex:
    """SSE event data schemas -- for OpenAPI generation only."""
    return SSESchemaIndex()


class ExperimentSchemaIndex(BaseModel):
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
    citation: CitationResponse | None = None
    planning_artifact: PlanningArtifactResponse | None = None


@router.get(
    "/experiment-schemas",
    response_model=ExperimentSchemaIndex,
    include_in_schema=True,
)
async def experiment_schemas() -> ExperimentSchemaIndex:
    """Experiment response schemas -- for OpenAPI generation only."""
    return ExperimentSchemaIndex()
