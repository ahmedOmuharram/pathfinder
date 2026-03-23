"""Tests for ai.tools.strategy_tools.step_ops -- step creation tool (thin wrapper).

The business logic is now in services.strategies.step_creation and is tested
in test_step_creation_service.py. These tests verify the tool layer still
orchestrates correctly (graph lookup, delegation, response formatting).
"""

from veupath_chatbot.ai.tools.strategy_tools.step_ops import (
    StepInputSpec,
    StrategyStepOps,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategySession


def _make_step_ops() -> StrategyStepOps:
    """Create a StrategyStepOps instance with a real session (no external calls needed)."""
    session = StrategySession("plasmodb")
    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session
    return ops


# -- create_step validation (no external calls) --


async def test_create_step_graph_not_found():
    """When session has no graph, create_step returns graph-not-found error."""
    session = StrategySession("plasmodb")
    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(search_name="GenesByText", graph_id="missing")
    assert result["ok"] is False
    assert result["code"] == "NOT_FOUND"


async def test_create_step_secondary_without_primary():
    """Secondary input without primary should be rejected."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    step_a = PlanStepNode(search_name="A", parameters={})
    step_b = PlanStepNode(search_name="B", parameters={})
    graph.add_step(step_a)
    graph.add_step(step_b)

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(
        inputs=StepInputSpec(secondary_input_step_id=step_b.id, operator="UNION"),
        graph_id="g1",
    )
    assert result["ok"] is False
    assert "primary_input_step_id" in str(result["message"])


async def test_create_step_secondary_without_operator():
    """Secondary input without operator should be rejected."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    step_a = PlanStepNode(search_name="A", parameters={})
    step_b = PlanStepNode(search_name="B", parameters={})
    graph.add_step(step_a)
    graph.add_step(step_b)

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(
        inputs=StepInputSpec(
            primary_input_step_id=step_a.id,
            secondary_input_step_id=step_b.id,
        ),
        graph_id="g1",
    )
    assert result["ok"] is False
    assert "operator is required" in str(result["message"])


async def test_create_step_leaf_requires_search_name():
    """Leaf steps (no inputs) require search_name."""
    session = StrategySession("plasmodb")
    session.create_graph("test", graph_id="g1")

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(graph_id="g1")
    assert result["ok"] is False
    assert "search_name is required" in str(result["message"])


async def test_create_step_primary_input_not_found():
    """Referencing a non-existent primary input step should fail."""
    session = StrategySession("plasmodb")
    session.create_graph("test", graph_id="g1")

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(
        inputs=StepInputSpec(primary_input_step_id="nonexistent"),
        search_name="SomeTransform",
        graph_id="g1",
    )
    assert result["ok"] is False
    assert result["code"] == "STEP_NOT_FOUND"


async def test_create_step_secondary_input_not_found():
    """Referencing a non-existent secondary input step should fail."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    step_a = PlanStepNode(search_name="A", parameters={})
    graph.add_step(step_a)

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    result = await ops.create_step(
        inputs=StepInputSpec(
            primary_input_step_id=step_a.id,
            secondary_input_step_id="nonexistent",
            operator="UNION",
        ),
        graph_id="g1",
    )
    assert result["ok"] is False
    assert result["code"] == "STEP_NOT_FOUND"


async def test_create_step_rejects_non_root_primary_input():
    """A step already consumed by another step cannot be used as primary input."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    step_a = PlanStepNode(search_name="A", parameters={})
    step_b = PlanStepNode(search_name="B", parameters={})
    graph.add_step(step_a)
    graph.add_step(step_b)

    # Create a combine that consumes both step_a and step_b
    combine = PlanStepNode(
        search_name="__combine__",
        parameters={},
        primary_input=step_a,
        secondary_input=step_b,
        operator=CombineOp.INTERSECT,
    )
    graph.add_step(combine)

    ops = StrategyStepOps.__new__(StrategyStepOps)
    ops.session = session

    # Try to use step_a again as primary input -- it's not a root anymore
    result = await ops.create_step(
        search_name="SomeSearch",
        inputs=StepInputSpec(primary_input_step_id=step_a.id),
        graph_id="g1",
    )
    assert result["ok"] is False
    assert "not a subtree root" in str(result["message"])
