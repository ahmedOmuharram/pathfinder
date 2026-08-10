"""Apply one operation to the working graph.

Steps are keyed by id and reference each other by id, so an edit here changes
exactly one step. Under the old nested model ``graph.steps`` indexed the very
objects the tree hung off, and rewiring a slot silently rewrote both views at
once - which is why callers needed a deep copy to work out what had changed.
"""

from dataclasses import dataclass, field

from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.graph_model import (
    DuplicateStepIdError,
    StepKind,
    StrategyStep,
    flatten_tree,
    subtree_ids,
)
from pathfinder.domain.strategy.operations.types import (
    AddCombineOp,
    AddLeafOp,
    AddTransformOp,
    AttachIntoSlot,
    DeleteEdgeOp,
    DeleteEdgeResolution,
    DeleteResolution,
    DeleteStepOp,
    DuplicateStepOp,
    GraphOperation,
    ReplaceStrategyOp,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepMetaOp,
    UpdateStepParamsOp,
    UpdateStrategyMetaOp,
    WireInputOp,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


@dataclass
class ApplyResult:
    description: str
    dropped_step_ids: list[str] = field(default_factory=list)


class ApplyError(Exception):
    """Raised when an operation cannot be applied (rejected, not validated)."""


def apply_operation(graph: StrategyGraph, op: GraphOperation) -> ApplyResult:
    structural = _try_apply_structural(graph, op)
    if structural is not None:
        return structural
    return _apply_field_update(graph, op)


def _try_apply_structural(
    graph: StrategyGraph, op: GraphOperation
) -> ApplyResult | None:
    add_result = _try_apply_add_op(graph, op)
    if add_result is not None:
        return add_result
    if isinstance(op, DeleteStepOp):
        return _apply_delete_step(graph, op)
    if isinstance(op, DeleteEdgeOp):
        return _apply_delete_edge(graph, op)
    if isinstance(op, ReplaceSubtreeOp):
        return _apply_replace_subtree(graph, op)
    if isinstance(op, ReplaceStrategyOp):
        return _apply_replace_strategy(graph, op)
    return None


def _try_apply_add_op(graph: StrategyGraph, op: GraphOperation) -> ApplyResult | None:
    if isinstance(op, AddLeafOp):
        return _apply_add_leaf(graph, op)
    if isinstance(op, AddCombineOp):
        return _apply_add_combine(graph, op)
    if isinstance(op, AddTransformOp):
        return _apply_add_transform(graph, op)
    if isinstance(op, DuplicateStepOp):
        return _apply_duplicate_step(graph, op)
    return None


def _apply_field_update(graph: StrategyGraph, op: GraphOperation) -> ApplyResult:
    if isinstance(op, UpdateStepParamsOp):
        return _apply_update_params(graph, op)
    if isinstance(op, UpdateCombineOperatorOp):
        return _apply_update_combine_operator(graph, op)
    if isinstance(op, UpdateStepMetaOp):
        return _apply_update_step_meta(graph, op)
    if isinstance(op, UpdateStrategyMetaOp):
        return _apply_update_strategy_meta(graph, op)
    if isinstance(op, WireInputOp):
        return _apply_wire_input(graph, op)
    msg = f"unsupported operation: {type(op).__name__}"
    raise ApplyError(msg)


def _require(graph: StrategyGraph, step_id: str, label: str) -> StrategyStep:
    step = graph.steps.get(step_id)
    if step is None:
        msg = f"{label} {step_id!r} not found"
        raise ApplyError(msg)
    return step


def _reject_existing(graph: StrategyGraph, step_id: str, label: str) -> None:
    if step_id in graph.steps:
        msg = f"{label} {step_id!r} already exists"
        raise ApplyError(msg)


def _set_input_slot(parent: StrategyStep, slot: str, value: str | None) -> None:
    if slot == "primary":
        parent.primary_input_id = value
    else:
        parent.secondary_input_id = value


def _drop(graph: StrategyGraph, step_ids: set[str]) -> None:
    for step_id in step_ids:
        graph.steps.pop(step_id, None)


def _settle(graph: StrategyGraph, last_step_id: str | None = None) -> None:
    graph.recompute_roots()
    graph.last_step_id = (
        last_step_id if last_step_id in graph.steps else graph.primary_root_id()
    )


def _step_from_node(node: StrategyStepNode, kind: StepKind) -> StrategyStep:
    """Convert an incoming wire node into a keyed step.

    Any nesting the caller sent is dropped on purpose: wiring travels in the
    operation's own fields (``attach``, ``left_id``/``right_id``, ``input_id``),
    so a node arriving with inputs already set would silently contradict them.
    """
    return StrategyStep(
        id=node.id,
        kind=kind,
        search_name=(
            None
            if kind is StepKind.COMBINE and node.search_name == COMBINE_SEARCH_NAME
            else node.search_name
        ),
        parameters=dict(node.parameters),
        display_name=node.display_name,
        operator=node.operator,
        colocation_params=node.colocation_params,
        filters=list(node.filters),
        analyses=list(node.analyses),
        reports=list(node.reports),
        wdk_weight=node.wdk_weight,
        expanded_strategy_id=node.expanded_strategy_id,
        expanded_name=node.expanded_name,
    )


def _apply_add_leaf(graph: StrategyGraph, op: AddLeafOp) -> ApplyResult:
    step = _step_from_node(op.step, StepKind.SEARCH)
    _reject_existing(graph, step.id, "step id")
    graph.steps[step.id] = step
    if isinstance(op.attach, AttachIntoSlot):
        target = _require(graph, op.attach.target_step_id, "target step")
        _set_input_slot(target, op.attach.slot, step.id)
    _settle(graph, step.id)
    return ApplyResult(description=f"Added {step.display_name or step.id}")


def _apply_add_combine(graph: StrategyGraph, op: AddCombineOp) -> ApplyResult:
    if op.left_id == op.right_id:
        msg = "combine inputs must differ"
        raise ApplyError(msg)
    _require(graph, op.left_id, "combine input step")
    _require(graph, op.right_id, "combine input step")
    _reject_existing(graph, op.step.id, "step id")
    combine = _step_from_node(op.step, StepKind.COMBINE)
    combine.primary_input_id = op.left_id
    combine.secondary_input_id = op.right_id
    graph.steps[combine.id] = combine
    _settle(graph, combine.id)
    return ApplyResult(description=f"Combined {op.left_id} and {op.right_id}")


def _apply_add_transform(graph: StrategyGraph, op: AddTransformOp) -> ApplyResult:
    _require(graph, op.input_id, "input step")
    _reject_existing(graph, op.step.id, "step id")
    transform = _step_from_node(op.step, StepKind.TRANSFORM)
    transform.primary_input_id = op.input_id
    consumer_info = graph.find_parent(op.input_id) if op.mode == "before-consumer" else (
        None
    )
    graph.steps[transform.id] = transform
    if consumer_info is not None:
        consumer, slot = consumer_info
        _set_input_slot(consumer, slot, transform.id)
    _settle(graph, transform.id)
    return ApplyResult(
        description=f"Inserted transform {transform.display_name or transform.id}"
    )


def _apply_delete_step(graph: StrategyGraph, op: DeleteStepOp) -> ApplyResult:
    target = _require(graph, op.step_id, "step")

    if op.resolution == DeleteResolution.DELETE_STRATEGY:
        dropped = sorted(graph.steps)
        graph.steps.clear()
        graph.roots.clear()
        graph.last_step_id = None
        return ApplyResult(description="Deleted strategy", dropped_step_ids=dropped)

    parent_info = graph.find_parent(op.step_id)

    if op.resolution == DeleteResolution.DELETE_SUBTREE:
        return _delete_subtree(graph, target, parent_info)
    if op.resolution == DeleteResolution.COLLAPSE_COMBINE:
        return _collapse_combine(graph, target, parent_info)
    if op.resolution == DeleteResolution.ORPHAN_SIBLING:
        return _orphan_sibling(graph, target, parent_info)
    if op.resolution == DeleteResolution.PROMOTE_PRIMARY:
        return _promote_primary(graph, target, parent_info)

    msg = f"unhandled resolution {op.resolution!r}"
    raise ApplyError(msg)


def _delete_subtree(
    graph: StrategyGraph,
    target: StrategyStep,
    parent_info: tuple[StrategyStep, str] | None,
) -> ApplyResult:
    to_delete = set(subtree_ids(target.id, graph.steps))
    if parent_info is not None:
        parent, slot = parent_info
        if parent.kind is StepKind.TRANSFORM:
            # A transform with nothing to consume has no meaning, so it goes
            # too, and its own consumer loses that input.
            to_delete.add(parent.id)
            grandparent_info = graph.find_parent(parent.id)
            if grandparent_info is not None:
                grandparent, gp_slot = grandparent_info
                _set_input_slot(grandparent, gp_slot, None)
        else:
            _set_input_slot(parent, slot, None)
    _drop(graph, to_delete)
    _settle(graph)
    return ApplyResult(
        description=f"Deleted {target.id} and subtree",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_combine(
    graph: StrategyGraph,
    target: StrategyStep,
    parent_info: tuple[StrategyStep, str] | None,
) -> ApplyResult:
    if parent_info is None:
        return _collapse_root_combine(graph, target)
    parent, slot = parent_info
    if parent.kind is StepKind.TRANSFORM:
        return _collapse_through_transform_parent(graph, target, parent)
    return _collapse_combine_parent(graph, target, parent, slot)


def _collapse_root_combine(
    graph: StrategyGraph, target: StrategyStep
) -> ApplyResult:
    if target.kind is not StepKind.COMBINE:
        msg = "collapse-combine on non-combine root"
        raise ApplyError(msg)
    secondary_id = target.secondary_input_id
    to_delete = {target.id}
    if secondary_id is not None:
        to_delete |= set(subtree_ids(secondary_id, graph.steps))
    primary_id = target.primary_input_id
    _drop(graph, to_delete)
    _settle(graph, primary_id)
    return ApplyResult(
        description=f"Collapsed combine {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_through_transform_parent(
    graph: StrategyGraph,
    target: StrategyStep,
    parent: StrategyStep,
) -> ApplyResult:
    to_delete = set(subtree_ids(target.id, graph.steps)) | {parent.id}
    grandparent_info = graph.find_parent(parent.id)
    if grandparent_info is not None:
        grandparent, gp_slot = grandparent_info
        _set_input_slot(grandparent, gp_slot, None)
    _drop(graph, to_delete)
    _settle(graph)
    return ApplyResult(
        description=f"Collapsed via transform {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_combine_parent(
    graph: StrategyGraph,
    target: StrategyStep,
    parent: StrategyStep,
    slot: str,
) -> ApplyResult:
    sibling_id = (
        parent.secondary_input_id if slot == "primary" else parent.primary_input_id
    )
    to_delete = set(subtree_ids(target.id, graph.steps)) | {parent.id}
    grandparent_info = graph.find_parent(parent.id)
    if grandparent_info is not None:
        grandparent, gp_slot = grandparent_info
        _set_input_slot(grandparent, gp_slot, sibling_id)
    _drop(graph, to_delete)
    _settle(graph)
    return ApplyResult(
        description=f"Collapsed combine {parent.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _demote_to_single_input(step: StrategyStep, slot: str) -> None:
    """Clear a slot, moving the survivor up if the primary one was cleared.

    A secondary input with no primary is not a shape WDK or the node model
    accepts, so the remaining branch takes the primary slot.
    """
    _set_input_slot(step, slot, None)
    if slot == "primary" and step.secondary_input_id is not None:
        step.primary_input_id = step.secondary_input_id
        step.secondary_input_id = None
    step.operator = None
    step.colocation_params = None
    if step.primary_input_id is not None:
        step.kind = StepKind.TRANSFORM if step.search_name else StepKind.COMBINE


def _orphan_sibling(
    graph: StrategyGraph,
    target: StrategyStep,
    parent_info: tuple[StrategyStep, str] | None,
) -> ApplyResult:
    """Delete this branch and let the combine and its other input float.

    The survivors stay as their own component. That is what the dialog offers
    ("leave them as orphan nodes, not pushed") and what
    ``StrategyAst.detached_roots`` carries: persisted locally, never sent to
    WDK, which rejects a step that has inputs but no strategy.
    """
    if parent_info is None:
        msg = "orphan-sibling requires a combine parent"
        raise ApplyError(msg)

    parent, slot = parent_info
    to_delete = set(subtree_ids(target.id, graph.steps))
    _drop(graph, to_delete)
    _demote_to_single_input(parent, slot)

    grandparent_info = graph.find_parent(parent.id)
    if grandparent_info is not None:
        grandparent, gp_slot = grandparent_info
        _demote_to_single_input(grandparent, gp_slot)

    _settle(graph)
    return ApplyResult(
        description=f"Deleted {target.id}, orphaned {parent.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _promote_primary(
    graph: StrategyGraph,
    target: StrategyStep,
    parent_info: tuple[StrategyStep, str] | None,
) -> ApplyResult:
    if target.kind is not StepKind.COMBINE:
        msg = "promote-primary on non-combine"
        raise ApplyError(msg)
    secondary_id = target.secondary_input_id
    to_delete = {target.id}
    if secondary_id is not None:
        to_delete |= set(subtree_ids(secondary_id, graph.steps))
    primary_id = target.primary_input_id
    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, primary_id)
    _drop(graph, to_delete)
    _settle(graph, primary_id)
    return ApplyResult(
        description=f"Promoted primary of {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _apply_delete_edge(graph: StrategyGraph, op: DeleteEdgeOp) -> ApplyResult:
    target = _require(graph, op.target_id, "step")

    if op.resolution == DeleteEdgeResolution.COLLAPSE:
        return _apply_delete_step(
            graph,
            DeleteStepOp(
                step_id=op.source_id,
                resolution=DeleteResolution.COLLAPSE_COMBINE,
            ),
        )

    wired = (
        target.primary_input_id
        if op.slot == "primary"
        else target.secondary_input_id
    )
    if wired != op.source_id:
        msg = (
            f"{op.slot} input of {op.target_id!r} is not wired to {op.source_id!r}; "
            f"the graph changed since this edge was drawn"
        )
        raise ApplyError(msg)

    _demote_to_single_input(target, op.slot)
    _settle(graph, op.target_id)
    return ApplyResult(description=f"Detached edge {op.source_id} to {op.target_id}")


def _apply_replace_subtree(graph: StrategyGraph, op: ReplaceSubtreeOp) -> ApplyResult:
    _require(graph, op.step_id, "step")
    old_ids = set(subtree_ids(op.step_id, graph.steps))
    parent_info = graph.find_parent(op.step_id)

    try:
        incoming = flatten_tree(op.subtree)
    except DuplicateStepIdError as exc:
        raise ApplyError(str(exc)) from exc
    _drop(graph, old_ids)
    graph.steps.update(incoming)

    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, op.subtree.id)
    _settle(graph, op.subtree.id)
    return ApplyResult(
        description=f"Replaced subtree at {op.step_id}",
        dropped_step_ids=sorted(old_ids - set(incoming)),
    )


def _apply_replace_strategy(
    graph: StrategyGraph, op: ReplaceStrategyOp
) -> ApplyResult:
    """Swap the whole graph for ``op.root``.

    Undo and redo replay a captured tree through this, so it restores a shape
    exactly rather than merging: anything the tree does not mention is gone.
    """
    try:
        rebuilt = flatten_tree(op.root)
    except DuplicateStepIdError as exc:
        raise ApplyError(str(exc)) from exc
    dropped = sorted(set(graph.steps) - set(rebuilt))
    graph.steps = rebuilt
    graph.roots = {op.root.id}
    graph.last_step_id = op.root.id
    if op.name is not None:
        graph.name = op.name
    if op.description is not None:
        graph.description = op.description
    return ApplyResult(description="Replaced strategy", dropped_step_ids=dropped)


def _apply_update_params(graph: StrategyGraph, op: UpdateStepParamsOp) -> ApplyResult:
    target = _require(graph, op.step_id, "step")
    target.parameters = {**target.parameters, **op.parameters}
    return ApplyResult(description=f"Updated parameters of {op.step_id}")


def _apply_update_combine_operator(
    graph: StrategyGraph, op: UpdateCombineOperatorOp
) -> ApplyResult:
    target = _require(graph, op.step_id, "step")
    target.operator = op.operator
    target.colocation_params = op.colocation_params
    return ApplyResult(
        description=f"Set operator of {op.step_id} to {op.operator.value}"
    )


def _apply_update_step_meta(graph: StrategyGraph, op: UpdateStepMetaOp) -> ApplyResult:
    target = _require(graph, op.step_id, "step")
    target.display_name = op.display_name
    return ApplyResult(description=f"Renamed {op.step_id}")


def _apply_update_strategy_meta(
    graph: StrategyGraph,
    op: UpdateStrategyMetaOp,
) -> ApplyResult:
    if op.name is not None:
        graph.name = op.name
    if op.description is not None:
        graph.description = op.description
    return ApplyResult(description="Updated strategy metadata")


def _apply_duplicate_step(
    graph: StrategyGraph,
    op: DuplicateStepOp,
) -> ApplyResult:
    source = _require(graph, op.source_step_id, "step")
    _reject_existing(graph, op.duplicate_step_id, "duplicate id")
    _reject_existing(graph, op.combine_step_id, "combine id")

    duplicate = source.model_copy(
        update={
            "id": op.duplicate_step_id,
            "kind": StepKind.SEARCH,
            "primary_input_id": None,
            "secondary_input_id": None,
            "operator": None,
            "colocation_params": None,
        }
    )
    combine = StrategyStep(
        id=op.combine_step_id,
        kind=StepKind.COMBINE,
        primary_input_id=source.id,
        secondary_input_id=duplicate.id,
        operator=CombineOp.INTERSECT,
        display_name=op.combine_display_name,
    )

    parent_info = graph.find_parent(op.source_step_id)
    graph.steps[duplicate.id] = duplicate
    graph.steps[combine.id] = combine
    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, combine.id)
    _settle(graph, combine.id)
    return ApplyResult(description=f"Duplicated {op.source_step_id}")


def _apply_wire_input(graph: StrategyGraph, op: WireInputOp) -> ApplyResult:
    target = _require(graph, op.target_step_id, "target step")
    _require(graph, op.source_step_id, "source step")
    _set_input_slot(target, op.slot, op.source_step_id)
    if target.primary_input_id and target.secondary_input_id:
        target.kind = StepKind.COMBINE
    _settle(graph, target.id)
    return ApplyResult(
        description=f"Wired {op.source_step_id} to {op.target_step_id}",
    )
