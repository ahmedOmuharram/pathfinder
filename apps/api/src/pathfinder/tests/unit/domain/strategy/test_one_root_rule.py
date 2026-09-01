"""Which root a multi-root graph is addressed by.

A mid-edit canvas holds several roots. One rule picks the main tree, and every
reader that needs "the root" asks it.
"""

from __future__ import annotations

from pathfinder.domain.strategy.graph_model import StepKind, StrategyStep
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


def _leaf(step_id: str) -> StrategyStep:
    return StrategyStep(id=step_id, kind=StepKind.SEARCH, search_name="GenesByText")


def _graph() -> StrategyGraph:
    graph = StrategyGraph("g1", "kinases", "plasmodb")
    graph.record_type = "transcript"
    return graph


def _with_a_pair_and_a_stray() -> StrategyGraph:
    """``(a INTERSECT b)`` beside a leaf nobody consumes."""
    graph = _graph()
    graph.add_step(_leaf("a"))
    graph.add_step(_leaf("b"))
    graph.add_step(
        StrategyStep(
            id="c",
            kind=StepKind.COMBINE,
            primary_input_id="a",
            secondary_input_id="b",
            operator=CombineOp.INTERSECT,
        )
    )
    graph.add_step(_leaf("stray"))
    return graph


class TestThePrimaryRoot:
    def test_an_empty_graph_has_none(self) -> None:
        assert _graph().primary_root_id() is None

    def test_one_root_is_the_root(self) -> None:
        graph = _graph()
        graph.add_step(_leaf("a"))

        assert graph.primary_root_id() == "a"

    def test_the_largest_subtree_wins(self) -> None:
        assert _with_a_pair_and_a_stray().primary_root_id() == "c"

    def test_the_last_added_root_does_not_win_by_being_last(self) -> None:
        graph = _with_a_pair_and_a_stray()

        assert graph.last_step_id == "stray"
        assert graph.primary_root_id() == "c"

    def test_a_tie_goes_to_the_step_added_first(self) -> None:
        graph = _graph()
        graph.add_step(_leaf("first"))
        graph.add_step(_leaf("second"))

        assert graph.primary_root_id() == "first"
