"""Core type aliases and Literal types for the Experiment Lab."""

from typing import Literal

EnrichmentAnalysisType = Literal[
    "go_function", "go_component", "go_process", "pathway", "word"
]

ExperimentMode = Literal["single", "multi-step", "import"]

ParameterType = Literal["numeric", "integer", "categorical"]

ExperimentStatus = Literal["pending", "running", "completed", "error", "cancelled"]

ExperimentProgressPhase = Literal[
    "started",
    "evaluating",
    "optimizing",
    "cross_validating",
    "enriching",
    "step_analysis",
    "completed",
    "error",
]

ControlValueFormat = Literal["newline", "json_list", "comma"]

OptimizationObjective = Literal[
    "f1",
    "f_beta",
    "recall",
    "precision",
    "specificity",
    "balanced_accuracy",
    "mcc",
    "youdens_j",
    "custom",
]

ControlSetSource = Literal["paper", "curation", "db_build", "other"]

StepContributionVerdict = Literal["essential", "helpful", "neutral", "harmful"]

DEFAULT_K_VALUES: list[int] = [10, 25, 50, 100]

DEFAULT_STEP_ANALYSIS_PHASES: list[str] = [
    "step_evaluation",
    "operator_comparison",
    "contribution",
    "sensitivity",
]
