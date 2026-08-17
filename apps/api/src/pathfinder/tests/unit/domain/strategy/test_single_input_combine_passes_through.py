"""A combine with one input is that input.

Combining n criteria needs n-1 combine nodes. A spec that emits one per
criterion carries a spare node at the root with nothing to combine against.
Its meaning is unambiguous - there is no second operand - so rejecting it ends
a turn that had already bound every criterion.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
    operational_spec_to_step_tree,
)


def _spec(root: StructureNode) -> OperationalSpec:
    return OperationalSpec(
        goal="drug targets",
        criteria=[
            Criterion(
                id=name,
                text=name,
                role="filter",
                search_name=f"By{name}",
            )
            for name in ("a", "b", "c")
        ],
        structure=SpecStructure(root=root),
    )


def _leaf(name: str) -> StructureNode:
    return StructureNode(kind="leaf", criterion_id=name)


class TestASpareWrapperIsTransparent:
    def test_it_does_not_raise(self) -> None:
        pair = StructureNode(kind="combine", operator="INTERSECT", inputs=[_leaf("a"), _leaf("b")])
        wrapper = StructureNode(kind="combine", operator="INTERSECT", inputs=[pair])

        operational_spec_to_step_tree(_spec(wrapper))

    def test_the_tree_is_the_inner_combine(self) -> None:
        pair = StructureNode(kind="combine", operator="INTERSECT", inputs=[_leaf("a"), _leaf("b")])
        wrapper = StructureNode(kind="combine", operator="INTERSECT", inputs=[pair])

        tree = operational_spec_to_step_tree(_spec(wrapper))

        assert tree.operator == "INTERSECT"
        assert tree.primary_input is not None
        assert tree.secondary_input is not None

    def test_a_wrapper_around_a_leaf_is_the_leaf(self) -> None:
        wrapper = StructureNode(kind="combine", operator="INTERSECT", inputs=[_leaf("a")])

        tree = operational_spec_to_step_tree(_spec(wrapper))

        assert tree.search_name == "Bya"

    def test_nested_wrappers_all_collapse(self) -> None:
        inner = StructureNode(kind="combine", operator="INTERSECT", inputs=[_leaf("a")])
        outer = StructureNode(kind="combine", operator="INTERSECT", inputs=[inner])

        assert operational_spec_to_step_tree(_spec(outer)).search_name == "Bya"


class TestAnEmptyCombineIsStillAnError:
    def test_no_inputs_is_refused(self) -> None:
        node = StructureNode(kind="combine", operator="INTERSECT", inputs=[])

        with pytest.raises(ValueError, match="combine"):
            operational_spec_to_step_tree(_spec(node))

    def test_no_operator_with_two_inputs_is_refused(self) -> None:
        node = StructureNode(kind="combine", inputs=[_leaf("a"), _leaf("b")])

        with pytest.raises(ValueError, match="combine"):
            operational_spec_to_step_tree(_spec(node))
