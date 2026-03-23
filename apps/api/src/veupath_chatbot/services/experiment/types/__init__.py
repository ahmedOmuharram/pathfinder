"""Shared data types for the Experiment Lab.

This package consolidates all experiment-related dataclasses, type aliases,
and serialization helpers. All public symbols are re-exported here.
"""

from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)
from veupath_chatbot.services.experiment.types.core import (
    DEFAULT_K_VALUES,
    DEFAULT_STEP_ANALYSIS_PHASES,
    ControlSetSource,
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    ExperimentProgressPhase,
    ExperimentStatus,
    OptimizationObjective,
    ParameterType,
    StepContributionVerdict,
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
    experiment_summary_to_json,
    experiment_to_json,
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
    "DEFAULT_K_VALUES",
    "DEFAULT_STEP_ANALYSIS_PHASES",
    # Experiment
    "BatchExperimentConfig",
    "BatchOrganismTarget",
    # Rank
    "BootstrapResult",
    "ConfidenceInterval",
    # Metrics
    "ConfusionMatrix",
    # Control result
    "ControlSetData",
    # Core type aliases
    "ControlSetSource",
    "ControlTargetData",
    "ControlTestResult",
    "ControlValueFormat",
    "CrossValidationResult",
    "EnrichmentAnalysisType",
    # Enrichment
    "EnrichmentResult",
    "EnrichmentTerm",
    "Experiment",
    "ExperimentConfig",
    "ExperimentMetrics",
    "ExperimentMode",
    "ExperimentProgressPhase",
    "ExperimentStatus",
    "FoldMetrics",
    "GeneInfo",
    "NegativeSetVariant",
    # Step analysis
    "OperatorComparison",
    # Optimization
    "OperatorKnob",
    "OperatorVariant",
    "OptimizationObjective",
    "OptimizationSpec",
    "ParameterSensitivity",
    "ParameterSweepPoint",
    "ParameterType",
    "RankMetrics",
    "StepAnalysisResult",
    "StepContribution",
    "StepContributionVerdict",
    "StepEvaluation",
    "ThresholdKnob",
    "TreeOptimizationResult",
    "TreeOptimizationTrial",
    # Serialization
    "experiment_summary_to_json",
    "experiment_to_json",
]
