"""Experiment and ExperimentConfig types."""

from pydantic import Field

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat2
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types.core import (
    DEFAULT_STEP_ANALYSIS_PHASES,
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    ExperimentStatus,
    OptimizationObjective,
)
from veupath_chatbot.services.experiment.types.enrichment import EnrichmentResult
from veupath_chatbot.services.experiment.types.metrics import (
    CrossValidationResult,
    ExperimentMetrics,
    GeneInfo,
)
from veupath_chatbot.services.experiment.types.optimization import (
    OperatorKnob,
    OptimizationSpec,
    ThresholdKnob,
    TreeOptimizationResult,
)
from veupath_chatbot.services.experiment.types.rank import (
    BootstrapResult,
    RankMetrics,
)
from veupath_chatbot.services.experiment.types.step_analysis import StepAnalysisResult


class ExperimentConfig(CamelModel):
    """Full configuration for an experiment run.

    Supports three modes:

    * **single** (default): one search + parameters.
    * **multi-step**: a recursive ``step_tree`` of search/combine/transform nodes.
    * **import**: import an existing Pathfinder strategy by ``source_strategy_id``.
    """

    site_id: str
    record_type: str
    search_name: str
    parameters: JSONObject
    positive_controls: list[str]
    negative_controls: list[str]
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat = "newline"
    enable_cross_validation: bool = False
    k_folds: int = 5
    enrichment_types: list[EnrichmentAnalysisType] = Field(default_factory=list)
    name: str = ""
    description: str = ""
    optimization_specs: list[OptimizationSpec] | None = None
    optimization_budget: int = 30
    optimization_objective: OptimizationObjective = "balanced_accuracy"
    parameter_display_values: dict[str, str] | None = None
    mode: ExperimentMode = "single"
    step_tree: PlanStepNode | None = None
    source_strategy_id: str | None = None
    optimization_target_step: str | None = None
    enable_step_analysis: bool = False
    step_analysis_phases: list[str] = Field(
        default_factory=lambda: list(DEFAULT_STEP_ANALYSIS_PHASES)
    )
    control_set_id: str | None = None
    threshold_knobs: list[ThresholdKnob] | None = None
    operator_knobs: list[OperatorKnob] | None = None
    tree_optimization_objective: str = "precision_at_50"
    tree_optimization_budget: int = 50
    max_list_size: int | None = None
    sort_attribute: str | None = None
    sort_direction: str = "ASC"
    parent_experiment_id: str | None = None
    target_gene_ids: list[str] | None = None

    @property
    def is_tree_mode(self) -> bool:
        """Whether this config uses a multi-step strategy tree."""
        return self.mode in ("multi-step", "import") and self.step_tree is not None


class BatchOrganismTarget(CamelModel):
    """Per-organism overrides for a cross-organism batch experiment."""

    organism: str
    positive_controls: list[str] | None = None
    negative_controls: list[str] | None = None


class BatchExperimentConfig(CamelModel):
    """Configuration for running the same search across multiple organisms."""

    base_config: ExperimentConfig
    organism_param_name: str
    target_organisms: list[BatchOrganismTarget] = Field(default_factory=list)


class Experiment(CamelModel):
    """Full experiment with config and results."""

    id: str
    config: ExperimentConfig
    user_id: str | None = None
    status: ExperimentStatus = "pending"
    metrics: ExperimentMetrics | None = None
    cross_validation: CrossValidationResult | None = None
    enrichment_results: list[EnrichmentResult] = Field(default_factory=list)
    true_positive_genes: list[GeneInfo] = Field(default_factory=list)
    false_negative_genes: list[GeneInfo] = Field(default_factory=list)
    false_positive_genes: list[GeneInfo] = Field(default_factory=list)
    true_negative_genes: list[GeneInfo] = Field(default_factory=list)
    error: str | None = None
    total_time_seconds: RoundedFloat2 | None = None
    created_at: str = ""
    completed_at: str | None = None
    batch_id: str | None = None
    benchmark_id: str | None = None
    control_set_label: str | None = None
    is_primary_benchmark: bool = False
    optimization_result: JSONObject | None = None
    wdk_strategy_id: int | None = None
    wdk_step_id: int | None = None
    notes: str | None = None
    step_analysis: StepAnalysisResult | None = None
    rank_metrics: RankMetrics | None = None
    robustness: BootstrapResult | None = None
    tree_optimization: TreeOptimizationResult | None = None

    def classification_id_sets(
        self,
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        """Build classification ID sets from the gene lists.

        :returns: ``(tp_ids, fp_ids, fn_ids, tn_ids)``
        """
        return (
            {g.id for g in self.true_positive_genes},
            {g.id for g in self.false_positive_genes},
            {g.id for g in self.false_negative_genes},
            {g.id for g in self.true_negative_genes},
        )

    def result_gene_ids(self) -> set[str]:
        """Return the set of all result gene IDs (TP + FP)."""
        return {g.id for g in self.true_positive_genes} | {
            g.id for g in self.false_positive_genes
        }
