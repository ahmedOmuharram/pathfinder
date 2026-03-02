"""Shared data types for the Experiment Lab.

This package consolidates all experiment-related dataclasses, type aliases,
and serialization helpers. All public symbols are re-exported here.
"""

from veupath_chatbot.services.experiment.types.core import (
    DEFAULT_K_VALUES,
    ControlSetSource,
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    ExperimentProgressPhase,
    ExperimentStatus,
    OptimizationObjective,
    ParameterType,
    StepContributionVerdict,
    WizardStep,
)
from veupath_chatbot.services.experiment.types.enrichment import (
    EnrichmentResult,
    EnrichmentTerm,
)
from veupath_chatbot.services.experiment.types.experiment import (
    BatchExperimentConfig,
    BatchOrganismTarget,
    Experiment,
    ExperimentConfig,
)
from veupath_chatbot.services.experiment.types.metrics import (
    ConfusionMatrix,
    CrossValidationResult,
    ExperimentMetrics,
    FoldMetrics,
    GeneInfo,
)
from veupath_chatbot.services.experiment.types.optimization import (
    ControlSetSummary,
    OperatorKnob,
    OptimizationSpec,
    ThresholdKnob,
    TreeOptimizationResult,
    TreeOptimizationTrial,
)
from veupath_chatbot.services.experiment.types.rank import (
    BootstrapResult,
    ConfidenceInterval,
    NegativeSetVariant,
    RankMetrics,
)
from veupath_chatbot.services.experiment.types.serialization import (
    bootstrap_result_to_json,
    confidence_interval_to_json,
    cv_result_to_json,
    enrichment_result_to_json,
    enrichment_term_to_json,
    experiment_summary_to_json,
    experiment_to_json,
    fold_metrics_to_json,
    gene_info_to_json,
    metrics_to_json,
    negative_set_variant_to_json,
    operator_comparison_to_json,
    operator_variant_to_json,
    parameter_sensitivity_to_json,
    parameter_sweep_point_to_json,
    rank_metrics_to_json,
    step_analysis_to_json,
    step_contribution_to_json,
    step_evaluation_to_json,
    tree_optimization_result_to_json,
    tree_optimization_trial_to_json,
)
from veupath_chatbot.services.experiment.types.step_analysis import (
    OperatorComparison,
    OperatorVariant,
    ParameterSensitivity,
    ParameterSweepPoint,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)

__all__ = [
    # Core type aliases
    "ControlSetSource",
    "ControlValueFormat",
    "DEFAULT_K_VALUES",
    "EnrichmentAnalysisType",
    "ExperimentMode",
    "ExperimentProgressPhase",
    "ExperimentStatus",
    "OptimizationObjective",
    "ParameterType",
    "StepContributionVerdict",
    "WizardStep",
    # Metrics
    "ConfusionMatrix",
    "CrossValidationResult",
    "ExperimentMetrics",
    "FoldMetrics",
    "GeneInfo",
    # Enrichment
    "EnrichmentResult",
    "EnrichmentTerm",
    # Rank
    "BootstrapResult",
    "ConfidenceInterval",
    "NegativeSetVariant",
    "RankMetrics",
    # Optimization
    "ControlSetSummary",
    "OperatorKnob",
    "OptimizationSpec",
    "ThresholdKnob",
    "TreeOptimizationResult",
    "TreeOptimizationTrial",
    # Step analysis
    "OperatorComparison",
    "OperatorVariant",
    "ParameterSensitivity",
    "ParameterSweepPoint",
    "StepAnalysisResult",
    "StepContribution",
    "StepEvaluation",
    # Experiment
    "BatchExperimentConfig",
    "BatchOrganismTarget",
    "Experiment",
    "ExperimentConfig",
    # Serialization
    "bootstrap_result_to_json",
    "confidence_interval_to_json",
    "cv_result_to_json",
    "enrichment_result_to_json",
    "enrichment_term_to_json",
    "experiment_summary_to_json",
    "experiment_to_json",
    "fold_metrics_to_json",
    "gene_info_to_json",
    "metrics_to_json",
    "negative_set_variant_to_json",
    "operator_comparison_to_json",
    "operator_variant_to_json",
    "parameter_sensitivity_to_json",
    "parameter_sweep_point_to_json",
    "rank_metrics_to_json",
    "step_analysis_to_json",
    "step_contribution_to_json",
    "step_evaluation_to_json",
    "tree_optimization_result_to_json",
    "tree_optimization_trial_to_json",
]
