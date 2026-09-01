"""The AST the model is shown names the main tree as its root.

The rest of a mid-edit canvas travels in ``detached_roots``.
"""

from __future__ import annotations

from pathfinder.ai.tools.standalone._graph_helpers import build_context_strategy_ast
from pathfinder.domain.strategy.graph_model import StepKind, StrategyStep
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.strategies.sync_state import WDKSyncState


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


class TestTheContextPayloadUsesThatRule:
    def test_one_root_is_the_payload_root(self) -> None:
        graph = _graph()
        graph.add_step(_leaf("a"))
        session = StrategySession("plasmodb")
        session.add_graph(graph)
        session.sync_state = WDKSyncState()

        payload = build_context_strategy_ast(session, graph)

        assert payload is not None
        assert payload.strategy_ast.root.id == "a"

    def test_several_roots_take_the_main_tree_and_carry_the_rest_detached(
        self,
    ) -> None:
        graph = _with_a_pair_and_a_stray()
        session = StrategySession("plasmodb")
        session.add_graph(graph)
        session.sync_state = WDKSyncState()

        payload = build_context_strategy_ast(session, graph)

        assert payload is not None
        assert payload.strategy_ast.root.id == "c"
        assert [d.id for d in payload.strategy_ast.detached_roots] == ["stray"]

    def test_no_steps_is_no_payload(self) -> None:
        graph = _graph()
        session = StrategySession("plasmodb")
        session.add_graph(graph)

        assert build_context_strategy_ast(session, graph) is None

    def test_no_record_type_is_no_payload(self) -> None:
        graph = StrategyGraph("g1", "kinases", "plasmodb")
        graph.add_step(_leaf("a"))
        session = StrategySession("plasmodb")
        session.add_graph(graph)

        assert build_context_strategy_ast(session, graph) is None
