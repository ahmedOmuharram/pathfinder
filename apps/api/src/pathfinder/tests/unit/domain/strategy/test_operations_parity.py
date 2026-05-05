import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.operations import GraphOperation
from pathfinder.domain.strategy.operations.apply import apply_operation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph

PARITY_FIXTURE = (
    Path(__file__).resolve().parents[8] / "packages" / "spec" / "operations_parity.json"
)


def _load_cases() -> list[dict[str, Any]]:
    raw = json.loads(PARITY_FIXTURE.read_text())
    return list(raw["cases"])


def _build_graph(initial: dict[str, Any]) -> StrategyGraph:
    g = StrategyGraph(graph_id="g", name="g", site_id="plasmodb")
    by_id: dict[str, StrategyStepNode] = {}
    for step in initial["steps"]:
        kind = step.get("kind", "search")
        search_name = (
            "__combine__"
            if kind == "combine"
            else "orthologs"
            if kind == "transform"
            else "geneById"
        )
        by_id[step["id"]] = StrategyStepNode(id=step["id"], search_name=search_name)
    for step in initial["steps"]:
        node = by_id[step["id"]]
        primary = step.get("primaryInputStepId")
        secondary = step.get("secondaryInputStepId")
        if primary:
            node.primary_input = by_id[primary]
        if secondary:
            node.secondary_input = by_id[secondary]
            if not node.operator:
                node.operator = CombineOp.INTERSECT
        g.steps[step["id"]] = node
    g.recompute_roots()
    return g


_OP_ADAPTER: TypeAdapter[GraphOperation] = TypeAdapter(GraphOperation)


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["name"])
def test_parity_case(case: dict[str, Any]) -> None:
    graph = _build_graph(case["initial"])
    op = _OP_ADAPTER.validate_python(case["op"])
    result = apply_operation(graph, op)
    expected = case["expected"]

    assert sorted(graph.steps.keys()) == sorted(expected["stepIds"])
    assert sorted(result.dropped_step_ids) == sorted(expected["droppedStepIds"])

    for parent_id, slots in expected["rootInputs"].items():
        node = graph.steps[parent_id]
        if "primary" in slots:
            expected_primary = slots["primary"]
            actual = node.primary_input.id if node.primary_input is not None else None
            assert actual == expected_primary, parent_id
        if "secondary" in slots:
            expected_secondary = slots["secondary"]
            actual = node.secondary_input.id if node.secondary_input is not None else None
            assert actual == expected_secondary, parent_id
