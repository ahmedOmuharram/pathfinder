"""Step analysis dataclasses for multi-step experiment decomposition."""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.services.experiment.types.core import StepContributionVerdict


@dataclass(frozen=True, slots=True)
class StepEvaluation:
    """Per-leaf-step evaluation against controls."""

    step_id: str
    search_name: str
    display_name: str
    result_count: int
    positive_hits: int
    positive_total: int
    negative_hits: int
    negative_total: int
    recall: float
    false_positive_rate: float
    captured_positive_ids: list[str] = field(default_factory=list)
    captured_negative_ids: list[str] = field(default_factory=list)
    tp_movement: int = 0
    fp_movement: int = 0
    fn_movement: int = 0


@dataclass(frozen=True, slots=True)
class OperatorVariant:
    """Metrics for one boolean operator at a combine node."""

    operator: str
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    false_positive_rate: float
    f1_score: float


@dataclass(frozen=True, slots=True)
class OperatorComparison:
    """Comparison of operators at a single combine node."""

    combine_node_id: str
    current_operator: str
    variants: list[OperatorVariant] = field(default_factory=list)
    recommendation: str = ""
    recommended_operator: str = ""
    precision_at_k_delta: dict[int, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepContribution:
    """Ablation analysis for one leaf step."""

    step_id: str
    search_name: str
    baseline_recall: float
    ablated_recall: float
    recall_delta: float
    baseline_fpr: float
    ablated_fpr: float
    fpr_delta: float
    verdict: StepContributionVerdict
    enrichment_delta: float = 0.0
    narrative: str = ""


@dataclass(frozen=True, slots=True)
class ParameterSweepPoint:
    """One data point in a parameter sensitivity sweep."""

    value: float
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    fpr: float
    f1: float


@dataclass(frozen=True, slots=True)
class ParameterSensitivity:
    """Sensitivity sweep for one numeric parameter on one leaf step."""

    step_id: str
    param_name: str
    current_value: float
    sweep_points: list[ParameterSweepPoint] = field(default_factory=list)
    recommended_value: float = 0.0
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class StepAnalysisResult:
    """Container for all deterministic step analysis results."""

    step_evaluations: list[StepEvaluation] = field(default_factory=list)
    operator_comparisons: list[OperatorComparison] = field(default_factory=list)
    step_contributions: list[StepContribution] = field(default_factory=list)
    parameter_sensitivities: list[ParameterSensitivity] = field(default_factory=list)
