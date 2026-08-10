"""Step input resolution — primary/secondary lookup, root checks, duplication.

Resolves input step references from the strategy graph, validates
preconditions (primary present before secondary, operator required for
binary), and auto-duplicates consumed subtrees so the same search result
can appear in multiple tree positions (matching WDK's native behaviour).
"""

from dataclasses import dataclass

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import StrategyStepNode, generate_step_id
from pathfinder.domain.strategy.graph_model import StrategyStep, subtree_ids
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.errors import ErrorCode
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error

logger = get_logger(__name__)


@dataclass
class StepInputs:
    """Resolved step input nodes, operator, and parameters for validation."""

    primary: StrategyStepNode | None
    secondary: StrategyStepNode | None
    operator: str | None
    params: dict[str, ParamValue] | None = None


def _validate_primary_input(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
) -> tuple[StrategyStep | None, ToolErrorPayload | None]:
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
    primary_input: StrategyStep | None,
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
    primary_input: StrategyStep | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[StrategyStep | None, ToolErrorPayload | None]:
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
) -> tuple[StrategyStep | None, StrategyStep | None, ToolErrorPayload | None]:
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
    step: StrategyStep,
    graph: StrategyGraph,
) -> StrategyStep:
    """Copy a subtree under fresh ids so it can be used a second time.

    WDK requires a step to occupy exactly one position, so reusing the same
    branch on both sides of a combine needs a real copy rather than a second
    reference to it.
    """
    remap: dict[str, str] = {}
    for old_id in subtree_ids(step.id, graph.steps):
        remap[old_id] = generate_step_id()
    for old_id, new_id in remap.items():
        source = graph.steps[old_id]
        graph.steps[new_id] = source.model_copy(
            update={
                "id": new_id,
                "primary_input_id": remap.get(source.primary_input_id or ""),
                "secondary_input_id": remap.get(source.secondary_input_id or ""),
            }
        )
    return graph.steps[remap[step.id]]


def validate_inputs_and_roots(
    graph: StrategyGraph,
    primary_input_step_id: str | None,
    secondary_input_step_id: str | None,
    operator: str | None,
) -> tuple[StrategyStep | None, StrategyStep | None, ToolErrorPayload | None]:
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
