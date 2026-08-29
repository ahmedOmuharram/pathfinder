from __future__ import annotations

from typing import Literal, NamedTuple

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.constraints import Constraint
from pathfinder.domain.strategy.ops import CombineOp

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


class SpecTree(NamedTuple):
    """The tree a spec converts to, and the step each criterion became."""

    root: StrategyStepNode
    step_id_by_criterion: dict[str, str]


def operational_spec_to_step_tree(spec: OperationalSpec) -> StrategyStepNode:
    """Pure FRAME→BUILD seam: convert the spec's structure into the declarative
    builder's ``StrategyStepNode`` tree. Raises if any referenced criterion is
    missing or unbound."""
    return build_step_tree(spec).root


def build_step_tree(spec: OperationalSpec) -> SpecTree:
    """Convert the spec and report the step id it minted for each criterion."""
    if spec.structure is None:
        msg = "spec has no structure"
        raise ValueError(msg)
    by_id = {c.id: c for c in spec.criteria}
    minted: dict[str, str] = {}
    return SpecTree(
        root=_node_to_step(spec.structure.root, by_id, minted),
        step_id_by_criterion=minted,
    )


def renumber_criteria(
    spec: OperationalSpec, step_id_by_criterion: dict[str, str]
) -> OperationalSpec:
    """Re-key the spec on the step ids a build produced.

    A criterion and the step it built are then the same address, so a later
    edit changes that step rather than rebuilding the strategy around it.
    """
    renumbered = spec.model_copy(deep=True)
    for criterion in renumbered.criteria:
        criterion.id = step_id_by_criterion.get(criterion.id, criterion.id)
    for slot in renumbered.open_slots:
        slot.criterion_id = step_id_by_criterion.get(
            slot.criterion_id, slot.criterion_id
        )
    if renumbered.structure is not None:
        _renumber_structure(renumbered.structure.root, step_id_by_criterion)
    return renumbered


def _renumber_structure(node: StructureNode, mapping: dict[str, str]) -> None:
    if node.criterion_id is not None:
        node.criterion_id = mapping.get(node.criterion_id, node.criterion_id)
    for child in node.inputs:
        _renumber_structure(child, mapping)


def _bound_criterion(
    node: StructureNode, by_id: dict[str, Criterion], label: str
) -> Criterion:
    crit = by_id.get(node.criterion_id or "")
    if crit is None or not crit.bound:
        msg = f"{label} {node.criterion_id!r} is missing or unbound"
        raise ValueError(msg)
    return crit


def _node_to_step(
    node: StructureNode, by_id: dict[str, Criterion], minted: dict[str, str]
) -> StrategyStepNode:
    if node.kind == "leaf":
        crit = _bound_criterion(node, by_id, "criterion")
        step = StrategyStepNode(
            search_name=crit.search_name,
            parameters=dict(crit.resolved_params),
            display_name=crit.text[:60],
        )
        minted[crit.id] = step.id
        return step
    if node.kind == "transform":
        crit = _bound_criterion(node, by_id, "transform criterion")
        if not node.inputs:
            msg = f"transform criterion {node.criterion_id!r} has no input step"
            raise ValueError(msg)
        step = StrategyStepNode(
            search_name=crit.search_name,
            parameters=dict(crit.resolved_params),
            display_name=crit.text[:60],
            primary_input=_node_to_step(node.inputs[0], by_id, minted),
        )
        minted[crit.id] = step.id
        return step
    # Combining n criteria takes n-1 nodes. A spec that emits one per criterion
    # carries a spare with nothing to combine against, and one operand is that
    # operand.
    if len(node.inputs) == 1:
        return _node_to_step(node.inputs[0], by_id, minted)
    if node.operator is None or len(node.inputs) < _MIN_COMBINE_INPUTS:
        msg = "combine node needs an operator and at least two inputs"
        raise ValueError(msg)
    combined = StrategyStepNode(
        search_name=COMBINE_SEARCH_NAME,
        operator=node.operator,
        primary_input=_node_to_step(node.inputs[0], by_id, minted),
        secondary_input=_node_to_step(node.inputs[1], by_id, minted),
    )
    for extra in node.inputs[2:]:
        combined = StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            operator=node.operator,
            primary_input=combined,
            secondary_input=_node_to_step(extra, by_id, minted),
        )
    return combined
