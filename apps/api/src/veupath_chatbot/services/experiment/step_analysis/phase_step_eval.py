"""Phase 1: Per-step evaluation -- evaluate each leaf independently."""

from __future__ import annotations

import asyncio

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import ProgressCallback
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _evaluate_single_step,
    _evaluate_tree_against_controls,
    _extract_eval_counts,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _collect_leaves,
    _extract_leaf_branch,
    _node_id,
)
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    StepEvaluation,
    to_json,
)

logger = get_logger(__name__)


async def evaluate_steps(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
    progress_callback: ProgressCallback | None = None,
) -> list[StepEvaluation]:
    """Evaluate each leaf step against controls, preserving ancestor transforms.

    For each leaf, the evaluation includes any transform chain above it
    (e.g. ``GenesByOrthologs``) so that cross-organism searches are
    converted before being compared against controls.

    :param tree: ``PlanStepNode``-shaped dict.
    :returns: One :class:`StepEvaluation` per leaf.
    """
    leaves = _collect_leaves(tree)
    if not leaves:
        return []

    results: list[StepEvaluation] = []
    sem = asyncio.Semaphore(3)

    async def _eval_leaf(leaf: JSONObject, idx: int) -> StepEvaluation | None:
        search_name = str(leaf.get("searchName", ""))
        if not search_name or search_name.startswith("__"):
            return None

        display = str(leaf.get("displayName", search_name))
        lid = _node_id(leaf)

        branch = _extract_leaf_branch(tree, lid)
        has_transforms = branch is not None and isinstance(
            branch.get("primaryInput"), dict
        )

        if progress_callback:
            label = f"{display} (via transforms)" if has_transforms else display
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "step_evaluation",
                        "message": f"Evaluating step {idx + 1}/{len(leaves)}: {label}",
                        "current": idx + 1,
                        "total": len(leaves),
                    },
                }
            )

        try:
            async with sem:
                if branch is not None and has_transforms:
                    raw = await _evaluate_tree_against_controls(
                        site_id=site_id,
                        record_type=record_type,
                        tree=branch,
                        controls_search_name=controls_search_name,
                        controls_param_name=controls_param_name,
                        controls_value_format=controls_value_format,
                        positive_controls=positive_controls,
                        negative_controls=negative_controls,
                    )
                else:
                    raw_params = leaf.get("parameters")
                    parameters: JSONObject = (
                        raw_params if isinstance(raw_params, dict) else {}
                    )
                    raw = await _evaluate_single_step(
                        site_id=site_id,
                        record_type=record_type,
                        search_name=search_name,
                        parameters=parameters,
                        controls_search_name=controls_search_name,
                        controls_param_name=controls_param_name,
                        controls_value_format=controls_value_format,
                        positive_controls=positive_controls,
                        negative_controls=negative_controls,
                    )
        except Exception as exc:
            logger.warning("Step evaluation failed", step=lid, error=str(exc))
            return None

        counts = _extract_eval_counts(raw)

        recall = counts.pos_hits / counts.pos_total if counts.pos_total > 0 else 0.0
        fpr = counts.neg_hits / counts.neg_total if counts.neg_total > 0 else 0.0

        ev = StepEvaluation(
            step_id=lid,
            search_name=search_name,
            display_name=display,
            result_count=counts.total_results,
            positive_hits=counts.pos_hits,
            positive_total=counts.pos_total,
            negative_hits=counts.neg_hits,
            negative_total=counts.neg_total,
            recall=recall,
            false_positive_rate=fpr,
            captured_positive_ids=counts.pos_ids,
            captured_negative_ids=counts.neg_ids,
        )

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "step_evaluation",
                        "message": f"Evaluated {display}: recall {recall:.0%}, FPR {fpr:.0%}",
                        "current": idx + 1,
                        "total": len(leaves),
                        "stepEvaluation": to_json(ev),
                    },
                }
            )

        return ev

    tasks = [_eval_leaf(leaf, i) for i, leaf in enumerate(leaves)]
    evaluations = await asyncio.gather(*tasks)
    results = [e for e in evaluations if e is not None]

    logger.info("Step evaluation complete", count=len(results))
    return results
