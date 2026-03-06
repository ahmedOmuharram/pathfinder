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
from veupath_chatbot.services.experiment.types.json_codec import from_json, to_json
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
    "experiment_summary_to_json",
    "experiment_to_json",
    "from_json",
    "to_json",
]
