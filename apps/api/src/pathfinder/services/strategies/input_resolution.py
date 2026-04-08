"""Step input resolution — primary/secondary lookup, root checks, duplication.

Resolves input step references from the strategy graph, validates
preconditions (primary present before secondary, operator required for
binary), and auto-duplicates consumed subtrees so the same search result
can appear in multiple tree positions (matching WDK's native behaviour).
"""

from dataclasses import dataclass

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.errors import ErrorCode
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)


@dataclass
class StepInputs:
    """Resolved step input nodes, operator, and parameters for validation."""

    primary: PlanStepNode | None
    secondary: PlanStepNode | None
    operator: str | None
    params: JSONObject | None = None


def _validate_primary_input(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
) -> tuple[PlanStepNode | None, ToolErrorPayload | None]:
    """Resolve primary input step, returning (step, error_or_none)."""
    if not primary_input_step_id:
        return None, None
    step = graph.get_step(primary_input_step_id)
    if step:
        return step, None
    return None, tool_error(
        ErrorCode.STEP_NOT_FOUND,
        "Primary input step not found.",
        graphId=graph.id,
        stepId=primary_input_step_id,
    )


def _check_secondary_preconditions(
    graph: StrategyGraph,
    primary_input: PlanStepNode | None,
    operator: str | None,
) -> ToolErrorPayload | None:
    """Check preconditions for secondary input: primary present and operator provided."""
    if primary_input is None:
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            "secondary_input_step_id requires primary_input_step_id.",
            graphId=graph.id,
        )
    if not operator:
        return tool_error(
            ErrorCode.INVALID_STRATEGY,
            "operator is required when secondary_input_step_id is provided.",
            graphId=graph.id,
        )
    return None


def _validate_secondary_input(
    graph: StrategyGraph,
    primary_input: PlanStepNode | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[PlanStepNode | None, ToolErrorPayload | None]:
    """Resolve secondary input step and validate preconditions, returning (step, error_or_none)."""
    if not secondary_input_step_id:
        return None, None
    step = graph.get_step(secondary_input_step_id)
    if not step:
        return None, tool_error(
            ErrorCode.STEP_NOT_FOUND,
            "Secondary input step not found.",
            graphId=graph.id,
            stepId=secondary_input_step_id,
        )
    precond_error = _check_secondary_preconditions(graph, primary_input, operator)
    return (None, precond_error) if precond_error else (step, None)


def _validate_inputs(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[PlanStepNode | None, PlanStepNode | None, ToolErrorPayload | None]:
    """Validate and resolve input step references.

    :returns: (primary_input, secondary_input, error_or_none).
        If error is not None, the caller should return it immediately.
    """
    primary_input, primary_error = _validate_primary_input(graph, primary_input_step_id)
    if primary_error is not None:
        return None, None, primary_error

    secondary_input, secondary_error = _validate_secondary_input(
        graph, primary_input, secondary_input_step_id, operator
    )
    if secondary_error is not None:
        return None, None, secondary_error

    return primary_input, secondary_input, None


def _duplicate_subtree(
    step: PlanStepNode,
    graph: StrategyGraph,
) -> PlanStepNode:
    """Deep-clone a step and its entire input subtree with fresh IDs.

    All cloned nodes are registered in ``graph.steps``.  The clone root
    is **not** added to ``graph.roots`` — the caller uses it as input to
    a new step that will consume it immediately.
    """
    cloned_primary = (
        _duplicate_subtree(step.primary_input, graph)
        if step.primary_input
        else None
    )
    cloned_secondary = (
        _duplicate_subtree(step.secondary_input, graph)
        if step.secondary_input
        else None
    )
    clone = PlanStepNode(
        search_name=step.search_name,
        parameters=dict(step.parameters),
        primary_input=cloned_primary,
        secondary_input=cloned_secondary,
        operator=step.operator,
        colocation_params=step.colocation_params,
        display_name=step.display_name,
        filters=list(step.filters),
        wdk_weight=step.wdk_weight,
    )
    graph.steps[clone.id] = clone
    return clone


def validate_inputs_and_roots(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[PlanStepNode | None, PlanStepNode | None, ToolErrorPayload | None]:
    """Resolve input steps and validate root status.

    When a referenced step is already consumed (not a subtree root),
    its subtree is silently duplicated so the same search result can
    appear in multiple positions — matching WDK's native behaviour.

    Returns (primary, secondary, error).
    """
    primary_input, secondary_input, error = _validate_inputs(
        graph,
        primary_input_step_id,
        secondary_input_step_id,
        operator,
    )
    if error is not None:
        return None, None, error

    # Auto-duplicate consumed inputs so the same search result can
    # appear in multiple tree positions (matching WDK's native behaviour).
    if (
        primary_input is not None
        and primary_input_step_id is not None
        and primary_input_step_id not in graph.roots
    ):
        logger.info(
            "Auto-duplicating consumed step for reuse",
            original_id=primary_input_step_id,
            slot="primary",
        )
        primary_input = _duplicate_subtree(primary_input, graph)

    if (
        secondary_input is not None
        and secondary_input_step_id is not None
        and secondary_input_step_id not in graph.roots
    ):
        logger.info(
            "Auto-duplicating consumed step for reuse",
            original_id=secondary_input_step_id,
            slot="secondary",
        )
        secondary_input = _duplicate_subtree(secondary_input, graph)

    return primary_input, secondary_input, None
