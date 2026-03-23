"""Phase 3: Step contribution (ablation) -- measure impact of removing each leaf."""

import asyncio

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
    ProgressCallback,
)
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _extract_eval_counts,
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _collect_leaves,
    _node_id,
    _remove_leaf_from_tree,
)
from veupath_chatbot.services.experiment.types import (
    ControlTestResult,
    StepContribution,
    StepContributionVerdict,
)

logger = get_logger(__name__)

_MIN_LEAVES_FOR_ABLATION = 2
_RECALL_ESSENTIAL_THRESHOLD = -0.1
_RECALL_HELPFUL_THRESHOLD = -0.02
_FPR_HARMFUL_THRESHOLD = -0.05
_RECALL_HARMFUL_IMPROVEMENT = 0.02


async def analyze_contributions(
    ctx: ControlsContext,
    tree: PlanStepNode,
    baseline_metrics: ControlTestResult,
    progress_callback: ProgressCallback | None = None,
) -> list[StepContribution]:
    """Ablation analysis: remove each leaf and measure the impact.

    :param baseline_metrics: Typed control-test result from the full tree evaluation.
    :returns: One :class:`StepContribution` per leaf.
    """
    leaves = _collect_leaves(tree)
    if len(leaves) < _MIN_LEAVES_FOR_ABLATION:
        return []

    baseline_counts = _extract_eval_counts(baseline_metrics)
    bl_recall = (
        baseline_counts.pos_hits / baseline_counts.pos_total
        if baseline_counts.pos_total > 0
        else 0.0
    )
    bl_fpr = (
        baseline_counts.neg_hits / baseline_counts.neg_total
        if baseline_counts.neg_total > 0
        else 0.0
    )

    results: list[StepContribution] = []
    sem = asyncio.Semaphore(3)

    async def _ablate_leaf(leaf: PlanStepNode, idx: int) -> StepContribution | None:
        lid = _node_id(leaf)
        search_name = leaf.search_name
        display = leaf.display_name or search_name

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "contribution",
                        "message": f"Ablation {idx + 1}/{len(leaves)}: removing {display}",
                        "current": idx + 1,
                        "total": len(leaves),
                    },
                }
            )

        ablated_tree = _remove_leaf_from_tree(tree, lid)
        if ablated_tree is None:
            return None

        try:
            async with sem:
                raw = await run_controls_against_tree(ctx, ablated_tree)
        except AppError as exc:
            logger.warning("Ablation failed", step=lid, error=str(exc))
            return None

        counts = _extract_eval_counts(raw)

        ablated_recall = (
            counts.pos_hits / counts.pos_total if counts.pos_total > 0 else 0.0
        )
        ablated_fpr = (
            counts.neg_hits / counts.neg_total if counts.neg_total > 0 else 0.0
        )

        recall_delta = ablated_recall - bl_recall
        fpr_delta = ablated_fpr - bl_fpr

        verdict: StepContributionVerdict
        if recall_delta < _RECALL_ESSENTIAL_THRESHOLD:
            verdict = "essential"
        elif recall_delta < _RECALL_HELPFUL_THRESHOLD:
            verdict = "helpful"
        elif (
            fpr_delta < _FPR_HARMFUL_THRESHOLD
            or recall_delta > _RECALL_HARMFUL_IMPROVEMENT
        ):
            # Step is harmful if removing it either reduces FPR meaningfully
            # or *improves* recall (meaning the step was hurting recall).
            verdict = "harmful"
        else:
            verdict = "neutral"

        sc = StepContribution(
            step_id=lid,
            search_name=search_name,
            baseline_recall=bl_recall,
            ablated_recall=ablated_recall,
            recall_delta=recall_delta,
            baseline_fpr=bl_fpr,
            ablated_fpr=ablated_fpr,
            fpr_delta=fpr_delta,
            verdict=verdict,
        )

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "contribution",
                        "message": f"Ablation {display}: {verdict} (recall \u0394{recall_delta:+.0%})",
                        "current": idx + 1,
                        "total": len(leaves),
                        "stepContribution": sc.model_dump(by_alias=True),
                    },
                }
            )

        return sc

    tasks = [_ablate_leaf(leaf, i) for i, leaf in enumerate(leaves)]
    ablations = await asyncio.gather(*tasks)
    results = [c for c in ablations if c is not None]

    logger.info("Contribution analysis complete", count=len(results))
    return results
