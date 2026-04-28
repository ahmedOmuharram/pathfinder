from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState


@pytest.fixture
def compiled_graph() -> CompiledStateGraph[
    PipelineState, Context, PipelineState, PipelineState,
]:
    return build_graph(checkpointer=InMemorySaver())


def test_graph_has_supervisor_and_phase_nodes(
    compiled_graph: CompiledStateGraph[
        PipelineState, Context, PipelineState, PipelineState,
    ],
) -> None:
    nodes = set(compiled_graph.get_graph().nodes.keys())
    expected = {
        START,
        END,
        "supervisor",
        "scoping",
        "discovery",
        "planning",
        "execution",
        "verification",
        "validate",
        "research",
    }
    assert expected.issubset(nodes), nodes


def test_graph_entry_edges_include_supervisor_and_specialists(
    compiled_graph: CompiledStateGraph[
        PipelineState, Context, PipelineState, PipelineState,
    ],
) -> None:
    edges = compiled_graph.get_graph().edges
    targets_from_start = {e.target for e in edges if e.source == START}
    assert {"supervisor", "validate", "research"}.issubset(targets_from_start)


def test_compiled_graph_records_state_schema_with_checkpointer(
    compiled_graph: CompiledStateGraph[
        PipelineState, Context, PipelineState, PipelineState,
    ],
) -> None:
    assert compiled_graph.checkpointer is not None
    assert getattr(compiled_graph, "context_schema", None) is not None
