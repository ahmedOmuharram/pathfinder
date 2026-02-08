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
    """Return ids of steps that are not referenced as inputs by other steps."""
    referenced = find_referenced_step_ids(graph)
    return [step_id for step_id in graph.steps if step_id not in referenced]


def validate_graph_integrity(graph: StrategyGraph) -> list[GraphIntegrityError]:
    """Validate graph structure + single-output invariant."""
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

    referenced: set[str] = set()
    for step_id, step in graph.steps.items():
        if not isinstance(step, PlanStepNode):
            continue
        primary = getattr(step.primary_input, "id", None)
        secondary = getattr(step.secondary_input, "id", None)
        if isinstance(primary, str) and primary:
            referenced.add(primary)
            if primary not in all_ids:
                add_missing(primary, step_id, "primary_input")
        if isinstance(secondary, str) and secondary:
            referenced.add(secondary)
            if secondary not in all_ids:
                add_missing(secondary, step_id, "secondary_input")

    root_ids = [sid for sid in graph.steps if sid not in referenced]
    if len(root_ids) == 0:
        errors.append(
            GraphIntegrityError("NO_ROOTS", "Strategy graph has no root/output steps.")
        )
    elif len(root_ids) > 1:
        errors.append(
            GraphIntegrityError(
                "MULTIPLE_ROOTS", "Strategy graph must have a single final output step."
            )
        )

    return errors
