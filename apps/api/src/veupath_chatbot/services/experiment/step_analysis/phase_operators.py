"""Phase 2: Operator comparison -- try all operators at each combine node."""

import asyncio

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
    ProgressCallback,
)
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _extract_eval_counts,
    _f1_from_counts,
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _build_subtree_with_operator,
    _collect_combine_nodes,
    _node_id,
)
from veupath_chatbot.services.experiment.types import (
    OperatorComparison,
    OperatorVariant,
)

COMPARISON_OPERATORS = [
    op
    for op in CombineOp
    if op not in (CombineOp.COLOCATE, CombineOp.LONLY, CombineOp.RONLY)
]

logger = get_logger(__name__)


async def compare_operators(
    ctx: ControlsContext,
    tree: PlanStepNode,
    progress_callback: ProgressCallback | None = None,
) -> list[OperatorComparison]:
    """For each combine node, evaluate INTERSECT, UNION, MINUS and recommend.

    :param tree: Strategy tree as a :class:`PlanStepNode`.
    :returns: One :class:`OperatorComparison` per combine node.
    """
    combine_nodes = _collect_combine_nodes(tree)
    if not combine_nodes:
        return []

    results: list[OperatorComparison] = []
    sem = asyncio.Semaphore(2)

    for ci, cnode in enumerate(combine_nodes):
        cid = _node_id(cnode)
        current_op = cnode.operator.value if cnode.operator is not None else "INTERSECT"

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "operator_comparison",
                        "message": f"Comparing operators at node {ci + 1}/{len(combine_nodes)}",
                        "current": ci + 1,
                        "total": len(combine_nodes),
                    },
                }
            )

        variants: list[OperatorVariant] = []

        async def _try_operator(
            op: CombineOp,
            _cnode: PlanStepNode = cnode,
            _cid: str = cid,
        ) -> OperatorVariant | None:
            subtree = _build_subtree_with_operator(_cnode, op)
            try:
                async with sem:
                    raw = await run_controls_against_tree(ctx, subtree)
            except AppError as exc:
                logger.warning(
                    "Operator comparison failed",
                    node=_cid,
                    op=op.value,
                    error=str(exc),
                )
                return None

            counts = _extract_eval_counts(raw)

            recall = counts.pos_hits / counts.pos_total if counts.pos_total > 0 else 0.0
            fpr = counts.neg_hits / counts.neg_total if counts.neg_total > 0 else 0.0

            return OperatorVariant(
                operator=op.value,
                positive_hits=counts.pos_hits,
                negative_hits=counts.neg_hits,
                total_results=counts.total_results,
                recall=recall,
                false_positive_rate=fpr,
                f1_score=_f1_from_counts(counts),
            )

        op_tasks = [_try_operator(op) for op in COMPARISON_OPERATORS]
        op_results = await asyncio.gather(*op_tasks)
        variants = [v for v in op_results if v is not None]

        best = max(variants, key=lambda v: v.f1_score) if variants else None
        recommendation = ""
        recommended_op = current_op
        if best and best.operator != current_op:
            cur = next((v for v in variants if v.operator == current_op), None)
            if cur and best.f1_score > cur.f1_score + 0.01:
                recommended_op = best.operator
                recommendation = (
                    f"Switching from {current_op} to {best.operator} "
                    f"improves F1 from {cur.f1_score:.2f} to {best.f1_score:.2f} "
                    f"(recall {cur.recall:.0%} -> {best.recall:.0%}, "
                    f"FPR {cur.false_positive_rate:.0%} -> {best.false_positive_rate:.0%})"
                )
            else:
                recommendation = (
                    f"Current operator {current_op} is already optimal or near-optimal."
                )
        elif best:
            recommendation = f"Current operator {current_op} is already optimal."

        oc = OperatorComparison(
            combine_node_id=cid,
            current_operator=current_op,
            variants=variants,
            recommendation=recommendation,
            recommended_operator=recommended_op,
        )
        results.append(oc)

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "operator_comparison",
                        "message": (
                            f"Node {cid}: {recommendation}"
                            if recommendation
                            else f"Node {cid}: compared {len(variants)} operators"
                        ),
                        "current": ci + 1,
                        "total": len(combine_nodes),
                        "operatorComparison": oc.model_dump(by_alias=True),
                    },
                }
            )

    logger.info("Operator comparison complete", count=len(results))
    return results
