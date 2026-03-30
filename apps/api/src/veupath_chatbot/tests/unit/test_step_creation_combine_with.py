"""Tests for combine_with mode in step creation service.

Tests the auto-combine behavior: when a new step is created and the graph
already has steps, a combine node is automatically inserted to maintain
the single-root invariant.
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.services.strategies.step_creation import (
    StepSpec,
    create_step,
)

from .conftest import make_step_creation_callbacks, make_step_graph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_graph_with_one_leaf() -> tuple[StrategyGraph, PlanStepNode]:
    """Create a graph with a single leaf step, returning (graph, leaf_step)."""
    graph = make_step_graph()
    leaf = PlanStepNode(search_name="GenesByText", parameters={"text_expression": "kinase"})
    graph.steps[leaf.id] = leaf
    graph.roots.add(leaf.id)
    graph.last_step_id = leaf.id
    graph.record_type = "transcript"
    return graph, leaf


# ---------------------------------------------------------------------------
# Empty graph: no combine needed (first step)
# ---------------------------------------------------------------------------


class TestCreateStepEmptyGraph:
    """First step in an empty graph uses add_step (no combine)."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_first_step_no_combine(self, mock_validate: AsyncMock) -> None:
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"text_expression": "kinase"},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.step_id is not None
        # No combine step should be created
        assert result.combine_step is None
        assert result.combine_step_id is None
        # Graph should have exactly 1 step (the leaf)
        assert len(graph.steps) == 1
        assert len(graph.roots) == 1

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_first_step_no_combine_wdk_fields(self, mock_validate: AsyncMock) -> None:
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"text_expression": "kinase"},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.combine_wdk_step_id is None
        assert result.combine_wdk_push_error is None


# ---------------------------------------------------------------------------
# Existing steps + no explicit combine_with_step_id → auto-combine with root
# ---------------------------------------------------------------------------


class TestAutoCompineWithRoot:
    """When graph has steps and no combine_with_step_id, auto-combine with root."""

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_auto_combines_with_root(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.step is not None
        assert result.combine_step is not None
        assert result.combine_step_id is not None
        # The combine step should have the COMBINE search name
        assert result.combine_step.search_name == COMBINE_SEARCH_NAME
        # Default operator is INTERSECT
        assert result.combine_step.operator == CombineOp.INTERSECT
        # Graph should still have exactly 1 root (the combine)
        assert len(graph.roots) == 1
        assert result.combine_step_id in graph.roots

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_auto_combine_primary_is_existing_root(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.combine_step is not None
        # Primary input of the combine should be the original root
        assert result.combine_step.primary_input is leaf
        # Secondary input should be the new step
        assert result.combine_step.secondary_input is result.step

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_auto_combine_graph_has_three_steps(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        """After 3 steps, graph should still have single root with nested combines."""
        graph, _leaf = _make_graph_with_one_leaf()

        # Add second step (auto-combines with first)
        result2 = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result2.error is None
        assert len(graph.roots) == 1

        # Add third step (auto-combines with current root, which is the combine)
        result3 = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByRNASeqPercentile",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result3.error is None
        assert len(graph.roots) == 1
        # The root should be a combine of combine + third step
        assert result3.combine_step is not None
        assert result3.combine_step.search_name == COMBINE_SEARCH_NAME


# ---------------------------------------------------------------------------
# Explicit combine_with_step_id
# ---------------------------------------------------------------------------


class TestExplicitCombineWith:
    """When combine_with_step_id is explicitly provided."""

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_combines_with_specified_step(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                combine_with_step_id=leaf.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.combine_step is not None
        assert result.combine_step.primary_input is leaf
        assert result.combine_step.secondary_input is result.step

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_explicit_combine_with_nonexistent_step_errors(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                combine_with_step_id="nonexistent_step",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is not None


# ---------------------------------------------------------------------------
# Explicit combine_operator
# ---------------------------------------------------------------------------


class TestExplicitCombineOperator:
    """When combine_operator is explicitly set (not default INTERSECT)."""

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_uses_explicit_operator(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                combine_operator="UNION",
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.combine_step is not None
        assert result.combine_step.operator == CombineOp.UNION

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_default_operator_is_intersect(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.combine_step is not None
        assert result.combine_step.operator == CombineOp.INTERSECT


# ---------------------------------------------------------------------------
# WDK push for both leaf and combine
# ---------------------------------------------------------------------------


class TestCombineWithWdkPush:
    """Both leaf and combine steps should be pushed to WDK."""

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(42, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_push_called_for_leaf_and_combine(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        # _push_step_to_wdk should be called twice: once for leaf, once for combine
        assert mock_push.call_count == 2

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(99, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_combine_wdk_step_id_populated(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.combine_wdk_step_id == 99

    @patch("veupath_chatbot.services.strategies.step_creation._push_step_to_wdk")
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_combine_push_error_captured(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        # First call (leaf) succeeds, second call (combine) fails
        mock_push.side_effect = [
            (10, None, None),
            (None, None, "WDK rejected combine"),
        ]

        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.error is None
        assert result.wdk_step_id == 10
        assert result.combine_wdk_push_error == "WDK rejected combine"


# ---------------------------------------------------------------------------
# StepCreationResult fields
# ---------------------------------------------------------------------------


class TestStepCreationResultFields:
    """Verify that StepCreationResult has combine_step and combine_step_id populated."""

    @patch(
        "veupath_chatbot.services.strategies.step_creation._push_step_to_wdk",
        new_callable=AsyncMock,
        return_value=(None, None, None),
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    async def test_result_has_combine_fields(
        self, mock_validate: AsyncMock, mock_push: AsyncMock
    ) -> None:
        graph, _leaf = _make_graph_with_one_leaf()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByGoTerm",
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
            ),
            callbacks=make_step_creation_callbacks(),
        )
        assert result.step is not None
        assert result.step_id is not None
        assert result.combine_step is not None
        assert result.combine_step_id is not None
        # step and combine_step should be different objects
        assert result.step is not result.combine_step
        assert result.step_id != result.combine_step_id
        # The combine step should be in the graph
        assert result.combine_step_id in graph.steps
