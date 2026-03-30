"""Tests for the step deletion service."""

from veupath_chatbot.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.services.strategies.step_deletion import (
    StepDeletionResult,
    delete_step_connected,
)


def _make_graph() -> StrategyGraph:
    return StrategyGraph("test-graph", "Test", "plasmodb.org")


def _leaf(name: str, step_id: str) -> PlanStepNode:
    return PlanStepNode(
        search_name=name,
        parameters={"organism": "Plasmodium falciparum 3D7"},
        id=step_id,
    )


def _populate_metadata(graph: StrategyGraph, step_id: str) -> None:
    """Add WDK metadata for a step so we can assert cleanup."""
    graph.wdk_step_ids[step_id] = 100
    graph.step_counts[step_id] = 42
    graph.step_validations[step_id] = WDKValidation(level="RUNNABLE", is_valid=True)
    graph.wdk_push_errors[step_id] = "some error"


async def test_deleting_leaf_cleans_up_wdk_step_ids() -> None:
    """wdk_step_ids entries for deleted steps are removed."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    graph.add_step(step_a)
    graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)

    graph.wdk_step_ids["step_a"] = 100
    graph.wdk_step_ids["step_b"] = 200

    result = await delete_step_connected(graph, "step_b")

    assert "step_b" in result.deleted_ids
    assert "step_b" not in graph.wdk_step_ids
    # step_a should be untouched
    assert graph.wdk_step_ids["step_a"] == 100


async def test_deleting_leaf_cleans_up_step_counts() -> None:
    """step_counts entries for deleted steps are removed."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    graph.add_step(step_a)
    graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)

    graph.step_counts["step_a"] = 42
    graph.step_counts["step_b"] = 99

    result = await delete_step_connected(graph, "step_b")

    assert "step_b" in result.deleted_ids
    assert "step_b" not in graph.step_counts
    assert graph.step_counts["step_a"] == 42


async def test_deleting_leaf_cleans_up_step_validations() -> None:
    """step_validations entries for deleted steps are removed."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    graph.add_step(step_a)
    graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)

    graph.step_validations["step_a"] = WDKValidation(level="RUNNABLE", is_valid=True)
    graph.step_validations["step_b"] = WDKValidation(level="RUNNABLE", is_valid=True)

    result = await delete_step_connected(graph, "step_b")

    assert "step_b" in result.deleted_ids
    assert "step_b" not in graph.step_validations
    assert graph.step_validations["step_a"].is_valid


async def test_deleting_leaf_cleans_up_wdk_push_errors() -> None:
    """wdk_push_errors entries for deleted steps are removed."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    graph.add_step(step_a)
    graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)

    graph.wdk_push_errors["step_a"] = "error a"
    graph.wdk_push_errors["step_b"] = "error b"

    result = await delete_step_connected(graph, "step_b")

    assert "step_b" in result.deleted_ids
    assert "step_b" not in graph.wdk_push_errors
    assert graph.wdk_push_errors["step_a"] == "error a"


async def test_deleting_step_without_metadata_does_not_error() -> None:
    """Deleting a step that has no WDK metadata should not raise."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    graph.add_step(step_a)

    # No metadata populated at all
    result = await delete_step_connected(graph, "step_a")

    assert "step_a" in result.deleted_ids
    assert len(graph.steps) == 0


async def test_deleting_nonexistent_step_returns_empty() -> None:
    """Deleting a step ID not in the graph returns empty deleted_ids."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    graph.add_step(step_a)

    result = await delete_step_connected(graph, "nonexistent")

    assert result.deleted_ids == []
    assert len(graph.steps) == 1


async def test_single_root_invariant_maintained_after_deletion() -> None:
    """After deletion, the graph has at most one root."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    step_c = _leaf("GenesByGoTerm", "step_c")
    graph.add_step(step_a)
    graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)
    # Now we have: combine(step_a, step_b)
    # Find the combine node id
    combine_ids = [
        sid
        for sid, s in graph.steps.items()
        if s.search_name == COMBINE_SEARCH_NAME
    ]
    assert len(combine_ids) == 1
    combine_id = combine_ids[0]
    graph.insert_step_with_combine(step_c, combine_id, CombineOp.UNION)
    # Tree shape: outer_combine(inner_combine(step_a, step_b), step_c)

    _populate_metadata(graph, "step_c")

    result = await delete_step_connected(graph, "step_c")

    assert "step_c" in result.deleted_ids
    assert len(graph.roots) == 1


async def test_combine_node_metadata_cleaned_on_collapse() -> None:
    """When deleting a leaf collapses its parent combine, combine metadata is cleaned too."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    step_b = _leaf("GenesByLocation", "step_b")
    graph.add_step(step_a)
    _, combine_id = graph.insert_step_with_combine(
        step_b, "step_a", CombineOp.INTERSECT,
    )

    _populate_metadata(graph, "step_b")
    # Also populate metadata for the combine node
    graph.wdk_step_ids[combine_id] = 300
    graph.step_counts[combine_id] = 10

    result = await delete_step_connected(graph, "step_b")

    # Both step_b and the combine should be deleted
    assert "step_b" in result.deleted_ids
    assert combine_id in result.deleted_ids
    # Metadata for both should be cleaned
    assert "step_b" not in graph.wdk_step_ids
    assert combine_id not in graph.wdk_step_ids
    assert "step_b" not in graph.step_counts
    assert combine_id not in graph.step_counts


async def test_result_type() -> None:
    """delete_step_connected returns a StepDeletionResult."""
    graph = _make_graph()
    step_a = _leaf("GenesByTaxon", "step_a")
    graph.add_step(step_a)

    result = await delete_step_connected(graph, "step_a")

    assert isinstance(result, StepDeletionResult)
    assert isinstance(result.deleted_ids, list)
