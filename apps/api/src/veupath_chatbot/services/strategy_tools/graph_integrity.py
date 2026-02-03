"""Strategy graph integrity helpers (service layer).

These utilities validate the *working graph* state (mutable session graph), not the
compiled DSL AST (which is single-root by construction).

Design goals:
- DRY: centralize root detection / validation logic.
- Separation of concerns: keep logic out of AI prompt text and tool mixins.
"""

from __future__ import annotations

from dataclasses import dataclass

from veupath_chatbot.domain.strategy.ast import CombineStep, TransformStep
from veupath_chatbot.services.strategy_session import StrategyGraph


@dataclass(frozen=True)
class GraphIntegrityError:
    code: str
    message: str
    step_id: str | None = None
    input_step_id: str | None = None
    kind: str | None = None

    def to_dict(self) -> dict:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.step_id:
            payload["stepId"] = self.step_id
        if self.input_step_id:
            payload["inputStepId"] = self.input_step_id
        if self.kind:
            payload["kind"] = self.kind
        return payload


def find_referenced_step_ids(graph: StrategyGraph) -> set[str]:
    referenced: set[str] = set()
    for step in graph.steps.values():
        if isinstance(step, TransformStep):
            ref = getattr(step.input, "id", None)
            if isinstance(ref, str) and ref:
                referenced.add(ref)
        elif isinstance(step, CombineStep):
            left = getattr(step.left, "id", None)
            right = getattr(step.right, "id", None)
            if isinstance(left, str) and left:
                referenced.add(left)
            if isinstance(right, str) and right:
                referenced.add(right)
    return referenced


def find_root_step_ids(graph: StrategyGraph) -> list[str]:
    """Return ids of steps that are not referenced as inputs by other steps."""
    referenced = find_referenced_step_ids(graph)
    return [step_id for step_id in graph.steps.keys() if step_id not in referenced]


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
        if isinstance(step, TransformStep):
            ref = getattr(step.input, "id", None)
            if isinstance(ref, str) and ref:
                referenced.add(ref)
                if ref not in all_ids:
                    add_missing(ref, step_id, "transform_input")
        elif isinstance(step, CombineStep):
            left = getattr(step.left, "id", None)
            right = getattr(step.right, "id", None)
            if isinstance(left, str) and left:
                referenced.add(left)
                if left not in all_ids:
                    add_missing(left, step_id, "combine_left")
            if isinstance(right, str) and right:
                referenced.add(right)
                if right not in all_ids:
                    add_missing(right, step_id, "combine_right")

    root_ids = [sid for sid in graph.steps.keys() if sid not in referenced]
    if len(root_ids) == 0:
        errors.append(GraphIntegrityError("NO_ROOTS", "Strategy graph has no root/output steps."))
    elif len(root_ids) > 1:
        errors.append(
            GraphIntegrityError(
                "MULTIPLE_ROOTS", "Strategy graph must have a single final output step."
            )
        )

    return errors

