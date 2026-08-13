from __future__ import annotations

from typing import Literal

from pydantic import Field

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.constraints import Constraint
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.platform.pydantic_base import CamelModel

CriterionRole = Literal["seed", "filter", "transform", "exclude"]
_MIN_COMBINE_INPUTS = 2


class OpenSlot(CamelModel):
    """A required param FRAME could not resolve — surfaced to the user (Tier-3).

    ``criterion_id`` is empty when the resolver emits a param-level slot; FRAME
    fills it when the slot is attached to a bound criterion."""

    criterion_id: str = ""
    param_name: str
    question: str = ""
    options: list[str] = Field(default_factory=list)


class DroppedCriterion(CamelModel):
    """A criterion with no realizable WDK search — surfaced, never silently lost."""

    text: str
    reason: str


class StructureNode(CamelModel):
    kind: Literal["leaf", "combine", "transform"]
    criterion_id: str | None = None
    operator: CombineOp | None = None
    inputs: list[StructureNode] = Field(default_factory=list)


class SpecStructure(CamelModel):
    root: StructureNode


class Criterion(CamelModel):
    id: str
    text: str
    search_name: str = ""
    role: CriterionRole = "filter"
    resolved_params: dict[str, ParamValue] = Field(default_factory=dict)
    # Params holding the search default rather than a value the request states.
    # Reported to the user, because a default is a safe choice and a silent one.
    defaulted_params: list[str] = Field(default_factory=list)
    open_params: list[OpenSlot] = Field(default_factory=list)
    confidence: float = 0.0

    @property
    def bound(self) -> bool:
        return bool(self.search_name)


class OperationalSpec(CamelModel):
    goal: str = ""
    interpreted_goal: str = ""
    record_type: str = "transcript"
    organism_scope: str | None = None
    title: str = ""
    criteria: list[Criterion] = Field(default_factory=list)
    structure: SpecStructure | None = None
    dropped: list[DroppedCriterion] = Field(default_factory=list)
    open_slots: list[OpenSlot] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)

    @property
    def ready_to_build(self) -> bool:
        if not self.criteria or self.structure is None or self.open_slots:
            return False
        return all(c.bound and not c.open_params for c in self.criteria)


def operational_spec_to_step_tree(spec: OperationalSpec) -> StrategyStepNode:
    """Pure FRAME→BUILD seam: convert the spec's structure into the declarative
    builder's ``StrategyStepNode`` tree. Raises if any referenced criterion is
    missing or unbound."""
    if spec.structure is None:
        msg = "spec has no structure"
        raise ValueError(msg)
    by_id = {c.id: c for c in spec.criteria}
    return _node_to_step(spec.structure.root, by_id)


def _node_to_step(node: StructureNode, by_id: dict[str, Criterion]) -> StrategyStepNode:
    if node.kind == "leaf":
        crit = by_id.get(node.criterion_id or "")
        if crit is None or not crit.bound:
            msg = f"criterion {node.criterion_id!r} is missing or unbound"
            raise ValueError(msg)
        return StrategyStepNode(
            search_name=crit.search_name,
            parameters=dict(crit.resolved_params),
            display_name=crit.text[:60],
        )
    if node.kind == "transform":
        crit = by_id.get(node.criterion_id or "")
        if crit is None or not crit.bound:
            msg = f"transform criterion {node.criterion_id!r} is missing or unbound"
            raise ValueError(msg)
        if not node.inputs:
            msg = f"transform criterion {node.criterion_id!r} has no input step"
            raise ValueError(msg)
        return StrategyStepNode(
            search_name=crit.search_name,
            parameters=dict(crit.resolved_params),
            display_name=crit.text[:60],
            primary_input=_node_to_step(node.inputs[0], by_id),
        )
    if node.operator is None or len(node.inputs) < _MIN_COMBINE_INPUTS:
        msg = "combine node needs an operator and at least two inputs"
        raise ValueError(msg)
    combined = StrategyStepNode(
        search_name=COMBINE_SEARCH_NAME,
        operator=node.operator,
        primary_input=_node_to_step(node.inputs[0], by_id),
        secondary_input=_node_to_step(node.inputs[1], by_id),
    )
    for extra in node.inputs[2:]:
        combined = StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            operator=node.operator,
            primary_input=combined,
            secondary_input=_node_to_step(extra, by_id),
        )
    return combined
