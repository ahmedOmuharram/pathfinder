"""Tests for ai.tools.strategy_tools.graph_ops -- AI-exposed graph inspection tools."""

from veupath_chatbot.ai.tools.strategy_tools.operations import StrategyTools
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategySession


def _make_graph_ops(
    *, with_steps: bool = True, connect: bool = False
) -> tuple[StrategyTools, list[str]]:
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    graph.record_type = "gene"

    step_ids: list[str] = []

    if with_steps:
        step_a = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
        step_b = PlanStepNode(search_name="SearchB", parameters={"y": "2"})
        graph.add_step(step_a)
        graph.add_step(step_b)
        step_ids = [step_a.id, step_b.id]

        if connect:
            combine = PlanStepNode(
                search_name="__combine__",
                parameters={},
                primary_input=step_a,
                secondary_input=step_b,
                operator=CombineOp.UNION,
            )
            graph.add_step(combine)
            step_ids.append(combine.id)

    ops = StrategyTools(session)
    return ops, step_ids


# -- list_current_steps --


async def test_list_current_steps_returns_all():
    ops, step_ids = _make_graph_ops()

    result = await ops.list_current_steps(graph_id="g1")

    assert result["graphId"] == "g1"
    assert result["stepCount"] == 2
    assert result["recordType"] == "gene"
    assert result["isBuilt"] is False
    returned_ids = [s["id"] for s in result["steps"]]
    for sid in step_ids:
        assert sid in returned_ids


async def test_list_current_steps_empty_graph():
    ops, _ = _make_graph_ops(with_steps=False)

    result = await ops.list_current_steps(graph_id="g1")

    assert result["stepCount"] == 0
    assert result["steps"] == []


async def test_list_current_steps_includes_wdk_ids():
    ops, step_ids = _make_graph_ops()
    graph = ops.session.get_graph("g1")
    graph.wdk_step_ids = {step_ids[0]: 100, step_ids[1]: 200}
    graph.wdk_strategy_id = 42

    result = await ops.list_current_steps(graph_id="g1")

    assert result["wdkStrategyId"] == 42
    assert result["isBuilt"] is True
    steps_by_id = {s["id"]: s for s in result["steps"]}
    assert steps_by_id[step_ids[0]]["wdkStepId"] == 100
    assert steps_by_id[step_ids[0]]["isBuilt"] is True


async def test_list_current_steps_includes_counts():
    ops, step_ids = _make_graph_ops()
    graph = ops.session.get_graph("g1")
    graph.step_counts = {step_ids[0]: 150, step_ids[1]: 0}

    result = await ops.list_current_steps(graph_id="g1")

    steps_by_id = {s["id"]: s for s in result["steps"]}
    assert steps_by_id[step_ids[0]]["estimatedSize"] == 150
    assert steps_by_id[step_ids[1]]["estimatedSize"] == 0


async def test_list_current_steps_step_kinds():
    ops, step_ids = _make_graph_ops(with_steps=True, connect=True)

    result = await ops.list_current_steps(graph_id="g1")

    kinds = {s["id"]: s["kind"] for s in result["steps"]}
    assert kinds[step_ids[0]] == "search"
    assert kinds[step_ids[1]] == "search"
    assert kinds[step_ids[2]] == "combine"


# -- validate_graph_structure --


async def test_validate_graph_single_root_ok():
    ops, _ = _make_graph_ops(with_steps=True, connect=True)

    result = await ops.validate_graph_structure(graph_id="g1")

    assert result.ok is True
    assert result.root_count == 1
    assert result.errors == []


async def test_validate_graph_multiple_roots_reports_error():
    ops, _ = _make_graph_ops(with_steps=True, connect=False)

    result = await ops.validate_graph_structure(graph_id="g1")

    assert result.ok is False
    assert result.root_count == 2
    assert len(result.errors) > 0
    assert result.errors[0]["code"] == "MULTIPLE_ROOTS"


async def test_validate_graph_suggests_union_for_multiple_roots():
    ops, _ = _make_graph_ops(with_steps=True, connect=False)

    result = await ops.validate_graph_structure(graph_id="g1")

    assert result.suggested_fix is not None
    assert result.suggested_fix["action"] == "UNION_ROOTS"
    assert result.suggested_fix["operator"] == "UNION"


async def test_validate_empty_graph():
    ops, _ = _make_graph_ops(with_steps=False)

    result = await ops.validate_graph_structure(graph_id="g1")

    assert result.ok is False
    assert any(e["code"] == "EMPTY_GRAPH" for e in result.errors)


async def test_validate_graph_includes_snapshot():
    ops, _ = _make_graph_ops(with_steps=True, connect=True)

    result = await ops.validate_graph_structure(graph_id="g1")

    assert result.graph_snapshot is not None
    assert result.graph_snapshot["graphId"] == "g1"
    assert len(result.graph_snapshot["steps"]) == 3


# -- ensure_single_output --


async def test_ensure_single_output_already_valid():
    ops, step_ids = _make_graph_ops(with_steps=True, connect=True)

    result = await ops.ensure_single_output(graph_id="g1")

    assert result["ok"] is True
    assert result["rootStepId"] == step_ids[2]
