"""The bottom-up fold every boundary traversal is written on.

A node sees its inputs already folded, in slot order. An empty slot is absent
from the list, so the length states the kind.
"""

from __future__ import annotations

from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
    fold_step_tree,
    walk_step_tree,
)
from pathfinder.domain.strategy.ops import CombineOp


def _tree() -> StrategyStepNode:
    """``orthologs(a) INTERSECT b``."""
    return StrategyStepNode(
        id="c",
        search_name=COMBINE_SEARCH_NAME,
        operator=CombineOp.INTERSECT,
        primary_input=StrategyStepNode(
            id="t",
            search_name="GenesByOrthologs",
            primary_input=StrategyStepNode(id="a", search_name="GenesByText"),
        ),
        secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
    )


def _render(node: StrategyStepNode, inputs: list[str]) -> str:
    return f"{node.id}[{','.join(inputs)}]"


def test_a_search_sees_no_inputs() -> None:
    assert fold_step_tree(StrategyStepNode(id="a", search_name="x"), _render) == "a[]"


def test_a_transform_sees_its_one_input() -> None:
    root = StrategyStepNode(
        id="t",
        search_name="GenesByOrthologs",
        primary_input=StrategyStepNode(id="a", search_name="x"),
    )

    assert fold_step_tree(root, _render) == "t[a[]]"


def test_a_combine_sees_both_inputs_in_slot_order() -> None:
    assert fold_step_tree(_tree(), _render) == "c[t[a[]],b[]]"


def test_every_node_is_folded_exactly_once() -> None:
    seen: list[str] = []

    def fold(node: StrategyStepNode, inputs: list[None]) -> None:
        del inputs
        seen.append(node.id)

    fold_step_tree(_tree(), fold)

    assert seen == [step.id for step in walk_step_tree(_tree())]


def test_the_fold_never_mutates_the_tree() -> None:
    root = _tree()
    before = root.model_dump(by_alias=True, mode="json")

    fold_step_tree(root, lambda node, inputs: node.id)

    assert root.model_dump(by_alias=True, mode="json") == before
