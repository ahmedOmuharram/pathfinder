from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.operations.types import (
    DeleteResolution,
    OperationChoice,
)
from pathfinder.domain.strategy.session import StrategyGraph


def compute_delete_choices(graph: StrategyGraph, step_id: str) -> list[OperationChoice]:
    target = graph.steps.get(step_id)
    if target is None:
        return []
    if len(graph.steps) == 1:
        return _sole_step_choices(step_id)
    if target.infer_kind() == "transform":
        return _transform_choices(step_id)
    parent_info = graph.find_parent(step_id)
    if parent_info is None:
        return _root_choices(graph, target)
    return _child_choices(target, parent_info)


def _sole_step_choices(step_id: str) -> list[OperationChoice]:
    return [
        OperationChoice(
            resolution=DeleteResolution.DELETE_STRATEGY,
            title="Delete strategy",
            description="This is the only step. Removing it empties the strategy.",
            is_default=True,
            will_delete=[step_id],
        )
    ]


def _transform_choices(step_id: str) -> list[OperationChoice]:
    return [
        OperationChoice(
            resolution=DeleteResolution.COLLAPSE_COMBINE,
            title="Delete this transform",
            description=(
                "The step it consumed becomes the input of the next step downstream."
            ),
            is_default=True,
            will_delete=[step_id],
        )
    ]


def _root_choices(
    graph: StrategyGraph, target: StrategyStepNode
) -> list[OperationChoice]:
    if target.infer_kind() == "combine":
        secondary = target.secondary_input
        secondary_subtree_ids = (
            [s.id for s in walk_step_tree(secondary)] if secondary else []
        )
        return [
            OperationChoice(
                resolution=DeleteResolution.PROMOTE_PRIMARY,
                title="Keep primary branch only",
                description=(
                    "Drop this combine and the secondary branch; the primary "
                    "branch becomes the new root."
                ),
                is_default=True,
                will_delete=[target.id, *secondary_subtree_ids],
            ),
            OperationChoice(
                resolution=DeleteResolution.DELETE_STRATEGY,
                title="Delete entire strategy",
                description="Remove every step.",
                is_default=False,
                will_delete=sorted(graph.steps.keys()),
            ),
        ]
    return [
        OperationChoice(
            resolution=DeleteResolution.DELETE_STRATEGY,
            title="Delete strategy",
            description="Removing this leaf leaves no steps.",
            is_default=True,
            will_delete=sorted(graph.steps.keys()),
        )
    ]


def _child_choices(
    target: StrategyStepNode, parent_info: tuple[StrategyStepNode, str]
) -> list[OperationChoice]:
    parent, _ = parent_info
    subtree_ids = sorted({s.id for s in walk_step_tree(target)})
    will_delete = sorted([*subtree_ids, parent.id])
    if parent.infer_kind() == "combine":
        return [
            OperationChoice(
                resolution=DeleteResolution.COLLAPSE_COMBINE,
                title="Delete and collapse",
                description=(
                    "Drop this branch and the combine; the other branch reconnects "
                    "upward."
                ),
                is_default=True,
                will_delete=will_delete,
            ),
            OperationChoice(
                resolution=DeleteResolution.DELETE_SUBTREE,
                title="Delete this subtree",
                description=(
                    "Same as the first option for a leaf, but for a multi-step "
                    "branch it removes everything below."
                ),
                is_default=False,
                will_delete=will_delete,
            ),
        ]
    return [
        OperationChoice(
            resolution=DeleteResolution.DELETE_SUBTREE,
            title="Delete this and the transform above it",
            description=(
                "The transform consuming this step has no other input, so it is "
                "removed too."
            ),
            is_default=True,
            will_delete=will_delete,
        )
    ]


def is_ambiguous_delete(graph: StrategyGraph, step_id: str) -> bool:
    return len(compute_delete_choices(graph, step_id)) > 1
