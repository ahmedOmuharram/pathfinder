"""Phase 3: Step contribution (ablation) -- measure impact of removing each leaf."""

from __future__ import annotations

import asyncio

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import ProgressCallback
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _evaluate_tree_against_controls,
    _extract_eval_counts,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _collect_leaves,
    _node_id,
    _remove_leaf_from_tree,
)
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    StepContribution,
    StepContributionVerdict,
    to_json,
)

logger = get_logger(__name__)


async def analyze_contributions(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
    baseline_metrics: JSONObject,
    progress_callback: ProgressCallback | None = None,
) -> list[StepContribution]:
    """Ablation analysis: remove each leaf and measure the impact.

    :param baseline_metrics: Metrics from the full tree evaluation.
    :returns: One :class:`StepContribution` per leaf.
    """
    leaves = _collect_leaves(tree)
    if len(leaves) < 2:
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

    async def _ablate_leaf(leaf: JSONObject, idx: int) -> StepContribution | None:
        lid = _node_id(leaf)
        search_name = str(leaf.get("searchName", ""))
        display = str(leaf.get("displayName", search_name))

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
                raw = await _evaluate_tree_against_controls(
                    site_id=site_id,
                    record_type=record_type,
                    tree=ablated_tree,
                    controls_search_name=controls_search_name,
                    controls_param_name=controls_param_name,
                    controls_value_format=controls_value_format,
                    positive_controls=positive_controls,
                    negative_controls=negative_controls,
                )
        except Exception as exc:
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
        if recall_delta < -0.1:
            verdict = "essential"
        elif recall_delta < -0.02:
            verdict = "helpful"
        elif fpr_delta < -0.05:
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
                        "stepContribution": to_json(sc),
                    },
                }
            )

        return sc

    tasks = [_ablate_leaf(leaf, i) for i, leaf in enumerate(leaves)]
    ablations = await asyncio.gather(*tasks)
    results = [c for c in ablations if c is not None]

    logger.info("Contribution analysis complete", count=len(results))
    return results
