"""Main entry point: run_step_analysis coordinates all four analysis phases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _extract_eval_counts,
)
from veupath_chatbot.services.experiment.step_analysis.phase_contribution import (
    analyze_contributions,
)
from veupath_chatbot.services.experiment.step_analysis.phase_operators import (
    compare_operators,
)
from veupath_chatbot.services.experiment.step_analysis.phase_sensitivity import (
    sweep_parameters,
)
from veupath_chatbot.services.experiment.step_analysis.phase_step_eval import (
    evaluate_steps,
)
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OperatorComparison,
    ParameterSensitivity,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)

ProgressCallback = Callable[[JSONObject], Awaitable[None]]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Post-processing: enrich evaluations / contributions with derived fields
# ---------------------------------------------------------------------------


def _enrich_step_evals_with_movement(
    evals: list[StepEvaluation],
    baseline_result: JSONObject,
    positive_controls: list[str],
    negative_controls: list[str],
) -> list[StepEvaluation]:
    """Add TP/FP/FN movement fields relative to the full-strategy baseline."""
    baseline_counts = _extract_eval_counts(baseline_result)
    baseline_tp = baseline_counts.pos_hits
    baseline_fp = baseline_counts.neg_hits
    baseline_fn = baseline_counts.pos_total - baseline_counts.pos_hits

    enriched: list[StepEvaluation] = []
    for ev in evals:
        step_fn = ev.positive_total - ev.positive_hits
        enriched.append(
            StepEvaluation(
                step_id=ev.step_id,
                search_name=ev.search_name,
                display_name=ev.display_name,
                result_count=ev.result_count,
                positive_hits=ev.positive_hits,
                positive_total=ev.positive_total,
                negative_hits=ev.negative_hits,
                negative_total=ev.negative_total,
                recall=ev.recall,
                false_positive_rate=ev.false_positive_rate,
                captured_positive_ids=ev.captured_positive_ids,
                captured_negative_ids=ev.captured_negative_ids,
                tp_movement=ev.positive_hits - baseline_tp,
                fp_movement=ev.negative_hits - baseline_fp,
                fn_movement=step_fn - baseline_fn,
            )
        )
    return enriched


def _enrich_contributions_with_narrative(
    contributions: list[StepContribution],
) -> list[StepContribution]:
    """Generate human-readable narrative text for each contribution."""
    enriched: list[StepContribution] = []
    for sc in contributions:
        parts: list[str] = []
        if sc.recall_delta < -0.05:
            parts.append(
                f"Removing this step drops recall by {abs(sc.recall_delta):.0%}"
            )
        elif sc.recall_delta > 0.02:
            parts.append(f"Removing this step improves recall by {sc.recall_delta:.0%}")

        if sc.fpr_delta < -0.05:
            parts.append(f"and reduces false positive rate by {abs(sc.fpr_delta):.0%}")
        elif sc.fpr_delta > 0.05:
            parts.append(f"but increases false positive rate by {sc.fpr_delta:.0%}")

        if not parts:
            if sc.verdict == "neutral":
                narrative = "This step has minimal impact on results."
            elif sc.verdict == "essential":
                narrative = "This step is critical \u2014 removing it significantly hurts recall."
            else:
                narrative = f"Verdict: {sc.verdict}."
        else:
            narrative = ", ".join(parts) + "."

        enriched.append(
            StepContribution(
                step_id=sc.step_id,
                search_name=sc.search_name,
                baseline_recall=sc.baseline_recall,
                ablated_recall=sc.ablated_recall,
                recall_delta=sc.recall_delta,
                baseline_fpr=sc.baseline_fpr,
                ablated_fpr=sc.ablated_fpr,
                fpr_delta=sc.fpr_delta,
                verdict=sc.verdict,
                enrichment_delta=sc.enrichment_delta,
                narrative=narrative,
            )
        )
    return enriched


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_step_analysis(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
    baseline_result: JSONObject,
    phases: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> StepAnalysisResult:
    """Run all requested step analysis phases.

    :param tree: ``PlanStepNode``-shaped dict.
    :param baseline_result: Raw result from the initial tree evaluation.
    :param phases: Which phases to run. Defaults to all four.
    :returns: Aggregated :class:`StepAnalysisResult`.
    """
    enabled = set(
        phases
        or [
            "step_evaluation",
            "operator_comparison",
            "contribution",
            "sensitivity",
        ]
    )

    step_evals: list[StepEvaluation] = []
    op_comparisons: list[OperatorComparison] = []
    contributions: list[StepContribution] = []
    sensitivities: list[ParameterSensitivity] = []

    if "step_evaluation" in enabled:
        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "step_evaluation",
                        "message": "Starting per-step evaluation...",
                    },
                }
            )
        step_evals = await evaluate_steps(
            site_id=site_id,
            record_type=record_type,
            tree=tree,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_value_format=controls_value_format,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            progress_callback=progress_callback,
        )
        step_evals = _enrich_step_evals_with_movement(
            step_evals,
            baseline_result,
            positive_controls,
            negative_controls,
        )

    if "operator_comparison" in enabled:
        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "operator_comparison",
                        "message": "Comparing operators...",
                    },
                }
            )
        op_comparisons = await compare_operators(
            site_id=site_id,
            record_type=record_type,
            tree=tree,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_value_format=controls_value_format,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            progress_callback=progress_callback,
        )

    if "contribution" in enabled:
        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "contribution",
                        "message": "Running ablation analysis...",
                    },
                }
            )
        contributions = await analyze_contributions(
            site_id=site_id,
            record_type=record_type,
            tree=tree,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_value_format=controls_value_format,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            baseline_metrics=baseline_result,
            progress_callback=progress_callback,
        )
        contributions = _enrich_contributions_with_narrative(contributions)

    if "sensitivity" in enabled:
        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "sensitivity",
                        "message": "Sweeping parameters...",
                    },
                }
            )
        sensitivities = await sweep_parameters(
            site_id=site_id,
            record_type=record_type,
            tree=tree,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            controls_value_format=controls_value_format,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            progress_callback=progress_callback,
        )

    return StepAnalysisResult(
        step_evaluations=step_evals,
        operator_comparisons=op_comparisons,
        step_contributions=contributions,
        parameter_sensitivities=sensitivities,
    )
