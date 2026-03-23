"""Strategy graph integrity helpers (service layer).

These utilities validate the *working graph* state (mutable session graph), not the
compiled DSL AST (which is single-root by construction).

Design goals:
- DRY: centralize root detection / validation logic.
- Separation of concerns: keep logic out of AI prompt text and tool mixins.
"""

from pydantic import ConfigDict

from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.pydantic_base import CamelModel


class GraphIntegrityError(CamelModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    step_id: str | None = None
    input_step_id: str | None = None
    kind: str | None = None


def find_root_step_ids(graph: StrategyGraph) -> list[str]:
    """Return root step IDs in sorted order.

    Uses the incrementally-maintained ``graph.roots`` set (O(1)) instead of
    recomputing from scratch.

    :param graph: Strategy graph.
    :returns: Sorted list of root step IDs.
    """
    return sorted(graph.roots)


def validate_graph_integrity(graph: StrategyGraph) -> list[GraphIntegrityError]:
    """Validate graph structure and single-output invariant.

    Uses ``graph.roots`` for root detection and additionally checks for
    dangling input references.

    :param graph: Strategy graph to validate.
    :returns: List of integrity errors (empty if valid).
    """
    all_ids = set(graph.steps.keys())
    if not all_ids:
        return [GraphIntegrityError(code="EMPTY_GRAPH", message="No steps in graph.")]

    errors: list[GraphIntegrityError] = []

    def add_missing(ref_id: str, step_id: str, kind: str) -> None:
        errors.append(
            GraphIntegrityError(
                code="UNKNOWN_STEP_REFERENCE",
                message="Step references an unknown input step.",
                step_id=step_id,
                input_step_id=ref_id,
                kind=kind,
            )
        )

    # Check for dangling references (inputs pointing to non-existent steps).
    for step_id, step in graph.steps.items():
        primary = step.primary_input.id if step.primary_input else None
        secondary = step.secondary_input.id if step.secondary_input else None
        if primary and primary not in all_ids:
            add_missing(primary, step_id, "primary_input")
        if secondary and secondary not in all_ids:
            add_missing(secondary, step_id, "secondary_input")

    # Use the incrementally-maintained root set.
    root_count = len(graph.roots)
    if root_count == 0:
        errors.append(
            GraphIntegrityError(
                code="NO_ROOTS", message="Strategy graph has no root/output steps."
            )
        )
    elif root_count > 1:
        errors.append(
            GraphIntegrityError(
                code="MULTIPLE_ROOTS",
                message=f"Strategy graph has {root_count} roots — expected 1. "
                f"Roots: {sorted(graph.roots)}",
            )
        )

    return errors
