"""Separating step data from tree structure has to be lossless.

``StrategyStepNode`` nests the whole node inside ``primaryInput`` /
``secondaryInput``, so the flat ``StrategyGraph.steps`` dict and the tree hold
the SAME objects. Every in-place edit mutates both views at once, which is why
``apply_and_commit`` needs a defensive deep copy before it can tell what
changed, and why a half-applied batch corrupts the graph.

WDK does not model it that way. ``StrategyDetails`` carries structure and data
separately::

    stepTree: StepTree            // nested, carries only stepId
    steps: Record<number, Step>   // the data

This is the conversion to that shape. Nothing may be lost in either
direction - every persisted strategy has to survive the migration - so the
round trip is asserted over generated trees rather than a handful of examples.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import (
    StepKind,
    find_parent,
    flatten_tree,
    is_computable,
    pushable_root_id,
    rebuild_tree,
    root_ids,
    subtree_ids,
)
from pathfinder.domain.strategy.ops import CombineOp

_IDS = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=8
)


@st.composite
def _node(draw: st.DrawFn) -> StrategyStepNode:
    """Build an arbitrary valid strategy tree with unique step ids."""
    used: set[str] = set()

    def fresh() -> str:
        while True:
            candidate = draw(_IDS)
            if candidate not in used:
                used.add(candidate)
                return candidate

    def build(depth: int) -> StrategyStepNode:
        shape = draw(st.sampled_from(["leaf", "transform", "combine"])) if depth else (
            "leaf"
        )
        params = draw(
            st.one_of(
                st.just({}),
                st.just({"organism": MultiPickValue(values=["Pf3D7"])}),
                st.just({"text": StringValue(value="kinase")}),
            )
        )
        display = draw(st.one_of(st.none(), st.just("A label")))
        if shape == "leaf":
            return StrategyStepNode(
                id=fresh(),
                search_name="GenesByTaxon",
                parameters=params,
                display_name=display,
            )
        if shape == "transform":
            return StrategyStepNode(
                id=fresh(),
                search_name="orthologs",
                parameters=params,
                display_name=display,
                primary_input=build(depth - 1),
            )
        primary = build(depth - 1)
        secondary = build(depth - 1)
        return StrategyStepNode(
            id=fresh(),
            search_name="__combine__",
            display_name=display,
            operator=draw(st.sampled_from([CombineOp.INTERSECT, CombineOp.UNION])),
            primary_input=primary,
            secondary_input=secondary,
        )

    return build(draw(st.integers(min_value=0, max_value=3)))


class TestRoundTrip:
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    @given(_node())
    def test_a_tree_survives_the_split_and_rejoin(
        self, node: StrategyStepNode
    ) -> None:
        steps = flatten_tree(node)

        assert rebuild_tree(node.id, steps) == node

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(_node())
    def test_every_step_appears_exactly_once_in_the_map(
        self, node: StrategyStepNode
    ) -> None:
        steps = flatten_tree(node)

        ids = subtree_ids(node.id, steps)

        assert sorted(ids) == sorted(steps)
        assert len(ids) == len(set(ids))

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(_node())
    def test_the_data_map_holds_no_structure(self, node: StrategyStepNode) -> None:
        """The whole point: a step no longer contains its inputs, so editing
        one cannot mutate the tree behind another view's back."""
        steps = flatten_tree(node)

        for step in steps.values():
            assert not hasattr(step, "primary_input")
            assert not hasattr(step, "secondary_input")

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(_node())
    def test_the_tree_has_exactly_one_root(self, node: StrategyStepNode) -> None:
        steps = flatten_tree(node)

        assert root_ids(steps) == {node.id}

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(_node())
    def test_every_non_root_step_has_a_parent(self, node: StrategyStepNode) -> None:
        steps = flatten_tree(node)

        for step_id in steps:
            if step_id == node.id:
                continue
            assert find_parent(step_id, steps) is not None


class TestKindIsExplicit:
    def test_a_leaf_is_a_search(self) -> None:
        steps = flatten_tree(StrategyStepNode(id="a", search_name="GenesByTaxon"))

        assert steps["a"].kind is StepKind.SEARCH

    def test_one_input_is_a_transform(self) -> None:
        node = StrategyStepNode(
            id="t",
            search_name="orthologs",
            primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
        )

        steps = flatten_tree(node)

        assert steps["t"].kind is StepKind.TRANSFORM

    def test_two_inputs_are_a_combine(self) -> None:
        node = StrategyStepNode(
            id="c",
            search_name="__combine__",
            operator=CombineOp.INTERSECT,
            primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
            secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
        )

        steps = flatten_tree(node)

        assert steps["c"].kind is StepKind.COMBINE

    def test_the_combine_sentinel_does_not_survive_as_a_search_name(self) -> None:
        """``__combine__`` exists only because kind had to be guessed from
        structure. With kind explicit the placeholder has no job."""
        node = StrategyStepNode(
            id="c",
            search_name="__combine__",
            operator=CombineOp.INTERSECT,
            primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
            secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
        )

        steps = flatten_tree(node)

        assert steps["c"].search_name is None

    def test_rebuilding_restores_the_sentinel_for_the_wdk_boundary(self) -> None:
        """WDK still wants a question name on the wire, so the projection
        back to the nested shape puts it back."""
        node = StrategyStepNode(
            id="c",
            search_name="__combine__",
            operator=CombineOp.INTERSECT,
            primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
            secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
        )

        steps = flatten_tree(node)

        assert rebuild_tree(node.id, steps).search_name == "__combine__"


class TestComputability:
    """A combine needs two inputs and an operator to mean anything.

    Detaching an edge leaves one behind deliberately - the canvas keeps the
    node so the researcher can rewire it. WDK cannot compute it in that state,
    so the projection has to walk past it rather than push a step that will be
    rejected. The old model hid this: kind was re-derived from whichever inputs
    happened to be set, so a half-wired combine silently became a "transform".
    """

    def test_a_wired_combine_is_computable(self) -> None:
        node = StrategyStepNode(
            id="c",
            search_name="__combine__",
            operator=CombineOp.INTERSECT,
            primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
            secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
        )
        steps = flatten_tree(node)

        assert is_computable(steps["c"])

    def test_a_combine_missing_its_secondary_is_not(self) -> None:
        steps = flatten_tree(
            StrategyStepNode(
                id="c",
                search_name="__combine__",
                operator=CombineOp.INTERSECT,
                primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
            )
        )
        steps["c"].secondary_input_id = None

        assert not is_computable(steps["c"])

    def test_a_combine_without_an_operator_is_not(self) -> None:
        steps = flatten_tree(
            StrategyStepNode(
                id="c",
                search_name="__combine__",
                operator=CombineOp.INTERSECT,
                primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
            )
        )
        steps["c"].operator = None

        assert not is_computable(steps["c"])

    def test_a_leaf_is_always_computable(self) -> None:
        steps = flatten_tree(StrategyStepNode(id="a", search_name="GenesByTaxon"))

        assert is_computable(steps["a"])

    def test_the_pushable_root_walks_past_a_half_wired_combine(self) -> None:
        """What WDK is given after an edge is cut: the surviving branch."""
        steps = flatten_tree(
            StrategyStepNode(
                id="c",
                search_name="__combine__",
                operator=CombineOp.INTERSECT,
                primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
            )
        )
        steps["c"].secondary_input_id = None
        steps["c"].operator = None

        assert pushable_root_id("c", steps) == "a"

    def test_a_fully_wired_root_is_its_own_pushable_root(self) -> None:
        steps = flatten_tree(
            StrategyStepNode(
                id="c",
                search_name="__combine__",
                operator=CombineOp.INTERSECT,
                primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
            )
        )

        assert pushable_root_id("c", steps) == "c"

    def test_a_combine_with_nothing_left_has_no_pushable_root(self) -> None:
        steps = flatten_tree(
            StrategyStepNode(
                id="c",
                search_name="__combine__",
                operator=CombineOp.INTERSECT,
                primary_input=StrategyStepNode(id="a", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
            )
        )
        steps["c"].primary_input_id = None
        steps["c"].secondary_input_id = None
        steps["c"].operator = None

        assert pushable_root_id("c", steps) is None
