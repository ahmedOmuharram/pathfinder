from dataclasses import dataclass, field

from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.operations.types import (
    AddCombineOp,
    AddLeafOp,
    AddTransformOp,
    AttachIntoSlot,
    DeleteResolution,
    DeleteStepOp,
    DuplicateStepOp,
    GraphOperation,
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
    if isinstance(op, ReplaceSubtreeOp):
        return _apply_replace_subtree(graph, op)
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


def _apply_add_leaf(graph: StrategyGraph, op: AddLeafOp) -> ApplyResult:
    if op.step.id in graph.steps:
        msg = f"step id {op.step.id!r} already exists"
        raise ApplyError(msg)
    graph.steps[op.step.id] = op.step
    if isinstance(op.attach, AttachIntoSlot):
        target = graph.steps.get(op.attach.target_step_id)
        if target is None:
            msg = f"target step {op.attach.target_step_id!r} not found"
            raise ApplyError(msg)
        if op.attach.slot == "primary":
            target.primary_input = op.step
        else:
            target.secondary_input = op.step
    graph.recompute_roots()
    graph.last_step_id = op.step.id
    return ApplyResult(description=f"Added {op.step.display_name or op.step.id}")


def _apply_add_combine(graph: StrategyGraph, op: AddCombineOp) -> ApplyResult:
    if op.left_id == op.right_id:
        msg = "combine inputs must differ"
        raise ApplyError(msg)
    left = graph.steps.get(op.left_id)
    right = graph.steps.get(op.right_id)
    if left is None or right is None:
        msg = "combine input step missing"
        raise ApplyError(msg)
    combine = op.step.model_copy(
        update={"primary_input": left, "secondary_input": right}
    )
    if op.step.id in graph.steps:
        msg = f"step id {op.step.id!r} already exists"
        raise ApplyError(msg)
    graph.steps[combine.id] = combine
    graph.recompute_roots()
    graph.last_step_id = combine.id
    return ApplyResult(description=f"Combined {op.left_id} and {op.right_id}")


def _apply_add_transform(graph: StrategyGraph, op: AddTransformOp) -> ApplyResult:
    input_step = graph.steps.get(op.input_id)
    if input_step is None:
        msg = f"input step {op.input_id!r} not found"
        raise ApplyError(msg)
    if op.step.id in graph.steps:
        msg = f"step id {op.step.id!r} already exists"
        raise ApplyError(msg)
    transform = op.step.model_copy(update={"primary_input": input_step})
    graph.steps[transform.id] = transform
    if op.mode == "before-consumer":
        consumer_info = graph.find_parent(op.input_id)
        if consumer_info is not None:
            consumer, slot = consumer_info
            _set_input_slot(consumer, slot, transform)
    graph.recompute_roots()
    graph.last_step_id = transform.id
    return ApplyResult(
        description=f"Inserted transform {op.step.display_name or op.step.id}"
    )


def _apply_delete_step(graph: StrategyGraph, op: DeleteStepOp) -> ApplyResult:
    target = graph.steps.get(op.step_id)
    if target is None:
        msg = f"step {op.step_id!r} not found"
        raise ApplyError(msg)

    if op.resolution == DeleteResolution.DELETE_STRATEGY:
        dropped = sorted(graph.steps.keys())
        graph.steps.clear()
        graph.roots.clear()
        graph.last_step_id = None
        return ApplyResult(description="Deleted strategy", dropped_step_ids=dropped)

    parent_info = graph.find_parent(op.step_id)

    if op.resolution == DeleteResolution.DELETE_SUBTREE:
        return _delete_subtree(graph, target, parent_info)

    if op.resolution == DeleteResolution.COLLAPSE_COMBINE:
        return _collapse_combine(graph, target, parent_info)

    if op.resolution == DeleteResolution.PROMOTE_PRIMARY:
        return _promote_primary(graph, target, parent_info)

    msg = f"unhandled resolution {op.resolution!r}"
    raise ApplyError(msg)


def _set_input_slot(
    parent: StrategyStepNode, slot: str, value: StrategyStepNode | None
) -> None:
    if slot == "primary":
        parent.primary_input = value
    else:
        parent.secondary_input = value


def _delete_subtree(
    graph: StrategyGraph,
    target: StrategyStepNode,
    parent_info: tuple[StrategyStepNode, str] | None,
) -> ApplyResult:
    to_delete = {s.id for s in walk_step_tree(target)}
    if parent_info is not None:
        parent, slot = parent_info
        if parent.infer_kind() == "transform":
            to_delete.add(parent.id)
            grandparent_info = graph.find_parent(parent.id)
            if grandparent_info is not None:
                gp, gp_slot = grandparent_info
                _set_input_slot(gp, gp_slot, None)
        else:
            _set_input_slot(parent, slot, None)
    for sid in to_delete:
        graph.steps.pop(sid, None)
    graph.recompute_roots()
    graph.last_step_id = next(iter(graph.roots), None)
    return ApplyResult(
        description=f"Deleted {target.id} and subtree",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_combine(
    graph: StrategyGraph,
    target: StrategyStepNode,
    parent_info: tuple[StrategyStepNode, str] | None,
) -> ApplyResult:
    if parent_info is None:
        return _collapse_root_combine(graph, target)
    parent, slot = parent_info
    if parent.infer_kind() == "transform":
        return _collapse_through_transform_parent(graph, target, parent)
    return _collapse_combine_parent(graph, target, parent, slot)


def _collapse_root_combine(
    graph: StrategyGraph, target: StrategyStepNode
) -> ApplyResult:
    if target.infer_kind() != "combine":
        msg = "collapse-combine on non-combine root"
        raise ApplyError(msg)
    secondary = target.secondary_input
    secondary_subtree_ids = (
        {s.id for s in walk_step_tree(secondary)} if secondary else set()
    )
    to_delete = secondary_subtree_ids | {target.id}
    for sid in to_delete:
        graph.steps.pop(sid, None)
    graph.recompute_roots()
    primary = target.primary_input
    graph.last_step_id = primary.id if primary else next(iter(graph.roots), None)
    return ApplyResult(
        description=f"Collapsed combine {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_through_transform_parent(
    graph: StrategyGraph,
    target: StrategyStepNode,
    parent: StrategyStepNode,
) -> ApplyResult:
    to_delete = {s.id for s in walk_step_tree(target)} | {parent.id}
    gp_info = graph.find_parent(parent.id)
    if gp_info is not None:
        gp, gp_slot = gp_info
        _set_input_slot(gp, gp_slot, None)
    for sid in to_delete:
        graph.steps.pop(sid, None)
    graph.recompute_roots()
    graph.last_step_id = next(iter(graph.roots), None)
    return ApplyResult(
        description=f"Collapsed via transform {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _collapse_combine_parent(
    graph: StrategyGraph,
    target: StrategyStepNode,
    parent: StrategyStepNode,
    slot: str,
) -> ApplyResult:
    sibling = parent.secondary_input if slot == "primary" else parent.primary_input
    to_delete = {s.id for s in walk_step_tree(target)} | {parent.id}
    grandparent_info = graph.find_parent(parent.id)
    if grandparent_info is not None:
        gp, gp_slot = grandparent_info
        _set_input_slot(gp, gp_slot, sibling)
    for sid in to_delete:
        graph.steps.pop(sid, None)
    graph.recompute_roots()
    graph.last_step_id = next(iter(graph.roots), None)
    return ApplyResult(
        description=f"Collapsed combine {parent.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _promote_primary(
    graph: StrategyGraph,
    target: StrategyStepNode,
    parent_info: tuple[StrategyStepNode, str] | None,
) -> ApplyResult:
    if target.infer_kind() != "combine":
        msg = "promote-primary on non-combine"
        raise ApplyError(msg)
    secondary = target.secondary_input
    secondary_subtree_ids = (
        {s.id for s in walk_step_tree(secondary)} if secondary else set()
    )
    to_delete = secondary_subtree_ids | {target.id}
    primary = target.primary_input
    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, primary)
    for sid in to_delete:
        graph.steps.pop(sid, None)
    graph.recompute_roots()
    graph.last_step_id = primary.id if primary else next(iter(graph.roots), None)
    return ApplyResult(
        description=f"Promoted primary of {target.id}",
        dropped_step_ids=sorted(to_delete),
    )


def _apply_replace_subtree(graph: StrategyGraph, op: ReplaceSubtreeOp) -> ApplyResult:
    old_root = graph.steps.get(op.step_id)
    if old_root is None:
        msg = f"step {op.step_id!r} not found"
        raise ApplyError(msg)
    old_subtree_ids = {s.id for s in walk_step_tree(old_root)}
    parent_info = graph.find_parent(op.step_id)

    for sid in old_subtree_ids:
        graph.steps.pop(sid, None)
    for node in walk_step_tree(op.subtree):
        graph.steps[node.id] = node

    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, op.subtree)
    graph.recompute_roots()
    graph.last_step_id = op.subtree.id
    return ApplyResult(
        description=f"Replaced subtree at {op.step_id}",
        dropped_step_ids=sorted(
            old_subtree_ids - {n.id for n in walk_step_tree(op.subtree)}
        ),
    )


def _apply_update_params(graph: StrategyGraph, op: UpdateStepParamsOp) -> ApplyResult:
    target = graph.steps.get(op.step_id)
    if target is None:
        msg = f"step {op.step_id!r} not found"
        raise ApplyError(msg)
    target.parameters = dict(op.parameters)
    return ApplyResult(description=f"Updated parameters of {op.step_id}")


def _apply_update_combine_operator(
    graph: StrategyGraph, op: UpdateCombineOperatorOp
) -> ApplyResult:
    target = graph.steps.get(op.step_id)
    if target is None:
        msg = f"step {op.step_id!r} not found"
        raise ApplyError(msg)
    target.operator = op.operator
    target.colocation_params = op.colocation_params
    return ApplyResult(
        description=f"Set operator of {op.step_id} to {op.operator.value}"
    )


def _apply_update_step_meta(graph: StrategyGraph, op: UpdateStepMetaOp) -> ApplyResult:
    target = graph.steps.get(op.step_id)
    if target is None:
        msg = f"step {op.step_id!r} not found"
        raise ApplyError(msg)
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
    source = graph.steps.get(op.source_step_id)
    if source is None:
        msg = f"step {op.source_step_id!r} not found"
        raise ApplyError(msg)
    if op.duplicate_step_id in graph.steps:
        msg = f"duplicate id {op.duplicate_step_id!r} already exists"
        raise ApplyError(msg)
    if op.combine_step_id in graph.steps:
        msg = f"combine id {op.combine_step_id!r} already exists"
        raise ApplyError(msg)

    duplicate = source.model_copy(
        update={
            "id": op.duplicate_step_id,
            "primary_input": None,
            "secondary_input": None,
            "operator": None,
            "colocation_params": None,
        },
        deep=False,
    )

    combine = StrategyStepNode(
        id=op.combine_step_id,
        search_name="__combine__",
        primary_input=source,
        secondary_input=duplicate,
        operator=CombineOp.INTERSECT,
        display_name=op.combine_display_name,
    )

    parent_info = graph.find_parent(op.source_step_id)
    graph.steps[duplicate.id] = duplicate
    graph.steps[combine.id] = combine
    if parent_info is not None:
        parent, slot = parent_info
        _set_input_slot(parent, slot, combine)
    graph.recompute_roots()
    graph.last_step_id = combine.id
    return ApplyResult(description=f"Duplicated {op.source_step_id}")


def _apply_wire_input(graph: StrategyGraph, op: WireInputOp) -> ApplyResult:
    target = graph.steps.get(op.target_step_id)
    source = graph.steps.get(op.source_step_id)
    if target is None:
        msg = f"target step {op.target_step_id!r} not found"
        raise ApplyError(msg)
    if source is None:
        msg = f"source step {op.source_step_id!r} not found"
        raise ApplyError(msg)
    _set_input_slot(target, op.slot, source)
    graph.recompute_roots()
    return ApplyResult(
        description=f"Wired {op.source_step_id} → {op.target_step_id}",
    )
