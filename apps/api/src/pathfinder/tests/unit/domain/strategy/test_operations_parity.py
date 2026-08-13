import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from pathfinder.domain.strategy.graph_model import StepKind, StrategyStep
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
    """The fixture already describes steps by id, which is now exactly the
    shape the graph holds - no nested round trip needed."""
    g = StrategyGraph(graph_id="g", name="g", site_id="plasmodb")
    for step in initial["steps"]:
        kind = StepKind(step.get("kind", "search"))
        g.steps[step["id"]] = StrategyStep(
            id=step["id"],
            kind=kind,
            search_name=(
                None
                if kind is StepKind.COMBINE
                else "orthologs"
                if kind is StepKind.TRANSFORM
                else "geneById"
            ),
            primary_input_id=step.get("primaryInputStepId"),
            secondary_input_id=step.get("secondaryInputStepId"),
            operator=(CombineOp.INTERSECT if kind is StepKind.COMBINE else None),
        )
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
            assert node.primary_input_id == expected_primary, parent_id
        if "secondary" in slots:
            expected_secondary = slots["secondary"]
            assert node.secondary_input_id == expected_secondary, parent_id
