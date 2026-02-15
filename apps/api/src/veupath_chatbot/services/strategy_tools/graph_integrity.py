"""Strategy graph integrity helpers (service layer).

These utilities validate the *working graph* state (mutable session graph), not the
compiled DSL AST (which is single-root by construction).

Design goals:
- DRY: centralize root detection / validation logic.
- Separation of concerns: keep logic out of AI prompt text and tool mixins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategy_session import StrategyGraph


@dataclass(frozen=True)
class GraphIntegrityError:
    code: str
    message: str
    step_id: str | None = None
    input_step_id: str | None = None
    kind: str | None = None

    def to_dict(self) -> JSONObject:
        payload: dict[str, str | None] = {"code": self.code, "message": self.message}
        if self.step_id:
            payload["stepId"] = self.step_id
        if self.input_step_id:
            payload["inputStepId"] = self.input_step_id
        if self.kind:
            payload["kind"] = self.kind
        return cast(JSONObject, payload)


def find_referenced_step_ids(graph: StrategyGraph) -> set[str]:
    """Return step IDs referenced as primary/secondary inputs (non-root steps).

    This is the complement of ``graph.roots``. Prefer using ``graph.roots``
    directly when you only need root step IDs.

    :param graph: Strategy graph.
    :returns: Set of step IDs that are referenced as inputs.
    """
    referenced: set[str] = set()
    for step in graph.steps.values():
        if not isinstance(step, PlanStepNode):
            continue
        primary = getattr(step.primary_input, "id", None)
        secondary = getattr(step.secondary_input, "id", None)
        if isinstance(primary, str) and primary:
            referenced.add(primary)
        if isinstance(secondary, str) and secondary:
            referenced.add(secondary)
    return referenced


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
        return [GraphIntegrityError("EMPTY_GRAPH", "No steps in graph.")]

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
        if not isinstance(step, PlanStepNode):
            continue
        primary = getattr(step.primary_input, "id", None)
        secondary = getattr(step.secondary_input, "id", None)
        if isinstance(primary, str) and primary and primary not in all_ids:
            add_missing(primary, step_id, "primary_input")
        if isinstance(secondary, str) and secondary and secondary not in all_ids:
            add_missing(secondary, step_id, "secondary_input")

    # Use the incrementally-maintained root set.
    root_count = len(graph.roots)
    if root_count == 0:
        errors.append(
            GraphIntegrityError("NO_ROOTS", "Strategy graph has no root/output steps.")
        )
    elif root_count > 1:
        errors.append(
            GraphIntegrityError(
                "MULTIPLE_ROOTS",
                f"Strategy graph has {root_count} roots — expected 1. "
                f"Roots: {sorted(graph.roots)}",
            )
        )

    return errors
