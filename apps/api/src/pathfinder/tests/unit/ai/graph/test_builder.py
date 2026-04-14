from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.builder import build_graph


@pytest.fixture
def compiled_graph() -> CompiledStateGraph:
    return build_graph(checkpointer=InMemorySaver())


def test_graph_has_all_phase_nodes(compiled_graph: CompiledStateGraph) -> None:
    nodes = set(compiled_graph.get_graph().nodes.keys())
    expected = {
        START,
        END,
        "scoping",
        "discovery",
        "planning",
        "execution",
        "verification",
    }
    assert expected.issubset(nodes), nodes


def test_graph_entry_edge_is_start_to_scoping(
    compiled_graph: CompiledStateGraph,
) -> None:
    edges = compiled_graph.get_graph().edges
    sources_to_scoping = {e.source for e in edges if e.target == "scoping"}
    assert START in sources_to_scoping


def test_compiled_graph_records_state_schema_with_checkpointer(
    compiled_graph: CompiledStateGraph,
) -> None:
    assert compiled_graph.checkpointer is not None
    assert getattr(compiled_graph, "context_schema", None) is not None

