"""Deleting an edge on the canvas must reach the backend.

The frontend has always been able to delete an edge (ReactFlow calls it on
the edge's own control), applied it optimistically, and then POSTed a
``deleteEdge`` operation the backend's discriminated union did not contain.
FastAPI rejected the unknown tag with 422, the optimistic apply rolled back,
and the researcher saw "Operation failed" on a gesture that looked like it
had worked.

Detach clears the slot and the combine fields that only make sense while the
slot is filled. Collapse is the same thing the delete-step path already does
for a combine, so it delegates rather than reimplementing the traversal.
"""

from collections.abc import Iterable

import pytest
from pydantic import TypeAdapter, ValidationError

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree, rebuild_tree
from pathfinder.domain.strategy.operations import (
    DeleteEdgeOp,
    DeleteEdgeResolution,
    GraphOperation,
)
from pathfinder.domain.strategy.operations.apply import ApplyError, apply_operation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.pydantic_base import CamelModel


class _Request(CamelModel):
    """Mirrors ApplyOperationRequest so the wire shape is exercised."""

    op: GraphOperation


def _graph_with(roots: Iterable[StrategyStepNode]) -> StrategyGraph:
    g = StrategyGraph(graph_id="g1", name="g", site_id="plasmodb")
    for root in roots:
        g.steps.update(flatten_tree(root))
    g.recompute_roots()
    return g


def _leaf(id_: str) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="geneById")


def _combine(
    id_: str, primary: StrategyStepNode, secondary: StrategyStepNode
) -> StrategyStepNode:
    return StrategyStepNode(
        id=id_,
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
    )


class TestWireContract:
    """The 422: the union must carry the tag the canvas actually sends."""

    def test_delete_edge_parses_from_the_wire(self) -> None:
        request = _Request.model_validate(
            {
                "op": {
                    "kind": "deleteEdge",
                    "sourceId": "b",
                    "targetId": "c",
                    "slot": "secondary",
                    "resolution": "detach",
                }
            }
        )

        assert isinstance(request.op, DeleteEdgeOp)
        assert request.op.source_id == "b"
        assert request.op.target_id == "c"
        assert request.op.slot == "secondary"
        assert request.op.resolution == DeleteEdgeResolution.DETACH

    def test_slot_is_constrained_to_the_two_wdk_inputs(self) -> None:
        with pytest.raises(ValidationError):
            _Request.model_validate(
                {
                    "op": {
                        "kind": "deleteEdge",
                        "sourceId": "b",
                        "targetId": "c",
                        "slot": "tertiary",
                        "resolution": "detach",
                    }
                }
            )

    def test_round_trips_through_camel_case(self) -> None:
        op = DeleteEdgeOp(
            source_id="b",
            target_id="c",
            slot="primary",
            resolution=DeleteEdgeResolution.COLLAPSE,
        )
        adapter = TypeAdapter(GraphOperation)

        restored = adapter.validate_python(op.model_dump(by_alias=True, mode="json"))

        assert restored == op


class TestDetach:
    def test_clears_the_named_slot(self) -> None:
        a, b = _leaf("a"), _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])

        apply_operation(
            g,
            DeleteEdgeOp(
                source_id="b",
                target_id="c",
                slot="secondary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        assert g.steps["c"].secondary_input_id is None
        assert g.steps["c"].primary_input_id is not None

    def test_clears_combine_fields_that_need_the_slot(self) -> None:
        """An operator without a second input is not a combine any more."""
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        apply_operation(
            g,
            DeleteEdgeOp(
                source_id="b",
                target_id="c",
                slot="secondary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        assert g.steps["c"].operator is None
        assert g.steps["c"].colocation_params is None

    def test_detached_source_survives_as_its_own_root(self) -> None:
        """Detach is not delete - the freed subtree stays in the graph."""
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        apply_operation(
            g,
            DeleteEdgeOp(
                source_id="b",
                target_id="c",
                slot="secondary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        assert "b" in g.steps
        assert g.roots == {"b", "c"}

    def test_reports_no_dropped_steps(self) -> None:
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        result = apply_operation(
            g,
            DeleteEdgeOp(
                source_id="b",
                target_id="c",
                slot="secondary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        assert result.dropped_step_ids == []

    def test_detaching_primary_promotes_the_surviving_secondary(self) -> None:
        """``secondaryInput`` without ``primaryInput`` violates the node
        invariant, so the remaining wire moves up instead of being stranded."""
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        apply_operation(
            g,
            DeleteEdgeOp(
                source_id="a",
                target_id="c",
                slot="primary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        assert g.steps["c"].primary_input_id is not None
        assert g.steps["c"].primary_input_id == "b"
        assert g.steps["c"].secondary_input_id is None
        assert g.roots == {"a", "c"}

    def test_the_detached_node_still_projects_to_wdk(self) -> None:
        """Detaching leaves a shape the nested projection must still accept.

        ``secondaryInput`` without ``primaryInput`` is rejected by
        ``StrategyStepNode``, so promoting the survivor is what keeps the
        graph pushable after an edge is cut.
        """
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        apply_operation(
            g,
            DeleteEdgeOp(
                source_id="a",
                target_id="c",
                slot="primary",
                resolution=DeleteEdgeResolution.DETACH,
            ),
        )

        projected = rebuild_tree("c", g.steps)
        dumped = projected.model_dump(by_alias=True, mode="json")
        assert StrategyStepNode.model_validate(dumped).primary_input is not None

    def test_unknown_target_is_rejected(self) -> None:
        g = _graph_with([_leaf("a")])

        with pytest.raises(ApplyError):
            apply_operation(
                g,
                DeleteEdgeOp(
                    source_id="a",
                    target_id="missing",
                    slot="primary",
                    resolution=DeleteEdgeResolution.DETACH,
                ),
            )

    def test_slot_that_is_not_wired_to_the_source_is_rejected(self) -> None:
        """Guards against a stale canvas deleting an edge that has moved."""
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        with pytest.raises(ApplyError):
            apply_operation(
                g,
                DeleteEdgeOp(
                    source_id="b",
                    target_id="c",
                    slot="primary",
                    resolution=DeleteEdgeResolution.DETACH,
                ),
            )


class TestCollapse:
    def test_removes_the_combine_and_its_secondary_subtree(self) -> None:
        c = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([c])

        result = apply_operation(
            g,
            DeleteEdgeOp(
                source_id="c",
                target_id="c",
                slot="secondary",
                resolution=DeleteEdgeResolution.COLLAPSE,
            ),
        )

        assert "c" not in g.steps
        assert "b" not in g.steps
        assert g.roots == {"a"}
        assert set(result.dropped_step_ids) == {"b", "c"}
