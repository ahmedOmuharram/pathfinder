"""Main entry point: run_step_analysis coordinates all four analysis phases."""

from collections.abc import Callable
from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
    ProgressCallback,
)
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
    ControlTestResult,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)

logger = get_logger(__name__)

_RECALL_DROP_THRESHOLD = -0.05
_RECALL_IMPROVEMENT_THRESHOLD = 0.02
_FPR_DROP_THRESHOLD = -0.05
_FPR_INCREASE_THRESHOLD = 0.05


# ---------------------------------------------------------------------------
# Post-processing: enrich evaluations / contributions with derived fields
# ---------------------------------------------------------------------------


def _enrich_step_evals_with_movement(
    evals: list[StepEvaluation],
    baseline_result: ControlTestResult,
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
        if sc.recall_delta < _RECALL_DROP_THRESHOLD:
            parts.append(
                f"Removing this step drops recall by {abs(sc.recall_delta):.0%}"
            )
        elif sc.recall_delta > _RECALL_IMPROVEMENT_THRESHOLD:
            parts.append(f"Removing this step improves recall by {sc.recall_delta:.0%}")

        if sc.fpr_delta < _FPR_DROP_THRESHOLD:
            parts.append(f"and reduces false positive rate by {abs(sc.fpr_delta):.0%}")
        elif sc.fpr_delta > _FPR_INCREASE_THRESHOLD:
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
    ctx: ControlsContext,
    tree: JSONObject,
    baseline_result: ControlTestResult,
    phases: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> StepAnalysisResult:
    """Run all requested step analysis phases.

    :param ctx: Shared controls context (site, record type, controls config).
    :param tree: ``PlanStepNode``-shaped dict.
    :param baseline_result: Typed control-test result from the initial tree evaluation.
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

    # Phase descriptors: (phase_key, progress_message, async_fn)
    # Each phase_fn takes (ctx, tree, progress_callback) with optional extras.
    phase_descriptors: list[tuple[str, str, Callable[..., Any]]] = [
        ("step_evaluation", "Starting per-step evaluation...", evaluate_steps),
        ("operator_comparison", "Comparing operators...", compare_operators),
        ("contribution", "Running ablation analysis...", analyze_contributions),
        ("sensitivity", "Sweeping parameters...", sweep_parameters),
    ]

    results: dict[str, Any] = {}
    for phase_key, message, phase_fn in phase_descriptors:
        if phase_key not in enabled:
            continue
        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {"phase": phase_key, "message": message},
                }
            )
        if phase_key == "contribution":
            results[phase_key] = await phase_fn(
                ctx, tree, baseline_result, progress_callback
            )
        else:
            results[phase_key] = await phase_fn(ctx, tree, progress_callback)

    # Post-process phases that need enrichment.
    step_evals: list[StepEvaluation] = results.get("step_evaluation", [])
    if step_evals:
        step_evals = _enrich_step_evals_with_movement(step_evals, baseline_result)

    contributions: list[StepContribution] = results.get("contribution", [])
    if contributions:
        contributions = _enrich_contributions_with_narrative(contributions)

    return StepAnalysisResult(
        step_evaluations=step_evals,
        operator_comparisons=results.get("operator_comparison", []),
        step_contributions=contributions,
        parameter_sensitivities=results.get("sensitivity", []),
    )
