"""Step analysis types for multi-step experiment decomposition."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat
from veupath_chatbot.services.experiment.types.core import StepContributionVerdict


class StepEvaluation(CamelModel):
    """Per-leaf-step evaluation against controls."""

    model_config = ConfigDict(frozen=True)

    step_id: str
    search_name: str
    display_name: str
    estimated_size: int
    positive_hits: int
    positive_total: int
    negative_hits: int
    negative_total: int
    recall: RoundedFloat
    false_positive_rate: RoundedFloat
    captured_positive_ids: list[str] = Field(default_factory=list)
    captured_negative_ids: list[str] = Field(default_factory=list)
    tp_movement: int = 0
    fp_movement: int = 0
    fn_movement: int = 0


class OperatorVariant(CamelModel):
    """Metrics for one boolean operator at a combine node."""

    model_config = ConfigDict(frozen=True)

    operator: str
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: RoundedFloat
    false_positive_rate: RoundedFloat
    f1_score: RoundedFloat


class OperatorComparison(CamelModel):
    """Comparison of operators at a single combine node."""

    model_config = ConfigDict(frozen=True)

    combine_node_id: str
    current_operator: str
    variants: list[OperatorVariant] = Field(default_factory=list)
    recommendation: str = ""
    recommended_operator: str = ""
    precision_at_k_delta: dict[int, float] = Field(default_factory=dict)


class StepContribution(CamelModel):
    """Ablation analysis for one leaf step."""

    model_config = ConfigDict(frozen=True)

    step_id: str
    search_name: str
    baseline_recall: RoundedFloat
    ablated_recall: RoundedFloat
    recall_delta: RoundedFloat
    baseline_fpr: RoundedFloat
    ablated_fpr: RoundedFloat
    fpr_delta: RoundedFloat
    verdict: StepContributionVerdict
    enrichment_delta: RoundedFloat = 0.0
    narrative: str = ""


class ParameterSweepPoint(CamelModel):
    """One data point in a parameter sensitivity sweep."""

    model_config = ConfigDict(frozen=True)

    value: RoundedFloat
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: RoundedFloat
    fpr: RoundedFloat
    f1: RoundedFloat


class ParameterSensitivity(CamelModel):
    """Sensitivity sweep for one numeric parameter on one leaf step."""

    model_config = ConfigDict(frozen=True)

    step_id: str
    param_name: str
    current_value: RoundedFloat
    sweep_points: list[ParameterSweepPoint] = Field(default_factory=list)
    recommended_value: RoundedFloat = 0.0
    recommendation: str = ""


class StepAnalysisResult(CamelModel):
    """Container for all deterministic step analysis results."""

    model_config = ConfigDict(frozen=True)

    step_evaluations: list[StepEvaluation] = Field(default_factory=list)
    operator_comparisons: list[OperatorComparison] = Field(default_factory=list)
    step_contributions: list[StepContribution] = Field(default_factory=list)
    parameter_sensitivities: list[ParameterSensitivity] = Field(default_factory=list)
