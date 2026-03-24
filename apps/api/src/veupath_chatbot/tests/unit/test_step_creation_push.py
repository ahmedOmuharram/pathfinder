"""Tests for WDK push-immediately step creation.

Verifies that create_step() pushes steps to WDK after adding them to the graph,
and stores the WDK step ID on graph.wdk_step_ids.

Step kinds tested:
- Leaf: POST to api.create_step, store WDK ID
- Combine: POST to api.create_combined_step (requires WDK IDs for both inputs)
- Transform: POST to api.create_transform_step (requires WDK ID for input)
- Error handling: WDK failure is non-fatal, step still exists in graph
- Validation: WDK validation is fetched via api.find_step after push

WDK contracts:
- create_step receives NewStepSpec with search_name + WDKSearchConfig
- create_combined_step receives primary/secondary WDK IDs + boolean operator
- create_transform_step receives NewStepSpec + input WDK ID
- Parameters are stringified (WDKSearchConfig.parameters: dict[str, str])
"""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKSearchResponse,
    WDKStep,
)
from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.services.strategies.step_creation import (
    StepSpec,
    create_step,
)

from .conftest import make_step_creation_callbacks, make_step_graph


def _mock_wdk_step(step_id: int, is_valid: bool = True) -> WDKStep:
    """Build a WDKStep with the given ID and validation."""
    return WDKStep.model_validate(
        {
            "id": step_id,
            "searchName": "GenesByText",
            "searchConfig": {"parameters": {}},
            "validation": {"level": "RUNNABLE", "isValid": is_valid},
        }
    )


def _mock_strategy_api(
    create_step_id: int = 100,
    find_step_valid: bool = True,
) -> AsyncMock:
    """Build a mock StrategyAPI with create_step, create_combined_step, create_transform_step, and find_step."""
    api = AsyncMock()
    api.create_step = AsyncMock(
        return_value=WDKIdentifier(id=create_step_id),
    )
    api.create_combined_step = AsyncMock(
        return_value=WDKIdentifier(id=create_step_id),
    )
    api.create_transform_step = AsyncMock(
        return_value=WDKIdentifier(id=create_step_id),
    )
    api.find_step = AsyncMock(
        return_value=_mock_wdk_step(create_step_id, is_valid=find_step_valid),
    )
    return api


# ---------------------------------------------------------------------------
# Leaf step push
# ---------------------------------------------------------------------------


class TestLeafStepPush:
    """Leaf steps (no inputs) are POSTed to WDK via api.create_step."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_leaf_step_pushes_to_wdk(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Leaf step creation pushes to WDK and stores WDK step ID on graph."""
        api = _mock_strategy_api(create_step_id=42)
        mock_get_api.return_value = api
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
        assert result.wdk_step_id == 42
        assert result.wdk_validation is not None
        assert result.wdk_validation.is_valid is True
        assert graph.wdk_step_ids[result.step_id] == 42
        api.create_step.assert_awaited_once()

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_leaf_step_stringifies_parameters(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Parameters with non-string values are converted to strings for WDKSearchConfig."""
        api = _mock_strategy_api(create_step_id=50)
        mock_get_api.return_value = api
        graph = make_step_graph()

        await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"num_value": 42, "bool_value": True},
            ),
            callbacks=make_step_creation_callbacks(),
        )

        call_args = api.create_step.call_args
        spec = call_args[0][0]
        assert spec.search_config.parameters == {
            "num_value": "42",
            "bool_value": "True",
        }

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_leaf_step_skips_none_values(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Parameters with None values are excluded from stringified params."""
        api = _mock_strategy_api(create_step_id=51)
        mock_get_api.return_value = api
        graph = make_step_graph()

        await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"text_expression": "kinase", "excluded": None},
            ),
            callbacks=make_step_creation_callbacks(),
        )

        call_args = api.create_step.call_args
        spec = call_args[0][0]
        assert "excluded" not in spec.search_config.parameters


# ---------------------------------------------------------------------------
# Combine step push
# ---------------------------------------------------------------------------


class TestCombineStepPush:
    """Combine steps require both inputs to have WDK IDs already."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_combine_step_pushes_to_wdk(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Combine step is pushed when both inputs have WDK IDs."""
        api = _mock_strategy_api(create_step_id=300)
        mock_get_api.return_value = api
        graph = make_step_graph()

        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        graph.wdk_step_ids[step_a.id] = 10
        graph.wdk_step_ids[step_b.id] = 20

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="UNION",
            ),
            callbacks=make_step_creation_callbacks(),
        )

        assert result.error is None
        assert result.wdk_step_id == 300
        assert graph.wdk_step_ids[result.step_id] == 300
        api.create_combined_step.assert_awaited_once()
        call_args = api.create_combined_step.call_args
        assert call_args[0][0] == 10  # primary_step_id
        assert call_args[0][1] == 20  # secondary_step_id
        assert call_args[0][2] == "UNION"  # boolean_operator

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_combine_step_skips_push_when_inputs_missing_wdk_ids(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Combine step is NOT pushed if input steps lack WDK IDs (graph only)."""
        api = _mock_strategy_api(create_step_id=301)
        mock_get_api.return_value = api
        graph = make_step_graph()

        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        # Intentionally NOT setting graph.wdk_step_ids for inputs

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                primary_input_step_id=step_a.id,
                secondary_input_step_id=step_b.id,
                operator="INTERSECT",
            ),
            callbacks=make_step_creation_callbacks(),
        )

        assert result.error is None
        assert result.step is not None
        assert result.wdk_step_id is None
        assert result.step_id not in graph.wdk_step_ids
        api.create_combined_step.assert_not_awaited()


# ---------------------------------------------------------------------------
# Transform step push
# ---------------------------------------------------------------------------


class TestTransformStepPush:
    """Transform steps require their input to have a WDK ID."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_transform_step_pushes_to_wdk(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
        mock_get_wdk: AsyncMock,
    ) -> None:
        """Transform step is pushed when input has a WDK ID."""
        api = _mock_strategy_api(create_step_id=200)
        mock_get_api.return_value = api

        # Mock WDK client for transform validation
        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value=WDKSearchResponse.model_validate(
                {
                    "searchData": {
                        "urlSegment": "GenesByOrthologs",
                        "parameters": [
                            {"name": "input_step", "type": "input-step"},
                            {"name": "organism", "type": "string"},
                        ],
                    },
                    "validation": {"level": "DISPLAYABLE", "isValid": True},
                }
            ),
        )
        mock_get_wdk.return_value = mock_client

        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        graph.wdk_step_ids[step_a.id] = 55

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByOrthologs",
                parameters={"organism": '["Plasmodium berghei ANKA"]'},
                primary_input_step_id=step_a.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )

        assert result.error is None
        assert result.wdk_step_id == 200
        assert graph.wdk_step_ids[result.step_id] == 200
        api.create_transform_step.assert_awaited_once()
        call_args = api.create_transform_step.call_args
        assert call_args[0][1] == 55  # input_step_id

    @patch(
        "veupath_chatbot.services.strategies.step_validation.get_wdk_client",
    )
    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_transform_step_skips_push_when_input_missing_wdk_id(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
        mock_get_wdk: AsyncMock,
    ) -> None:
        """Transform step is NOT pushed if input step lacks a WDK ID."""
        api = _mock_strategy_api(create_step_id=201)
        mock_get_api.return_value = api

        mock_client = AsyncMock()
        mock_client.get_search_details = AsyncMock(
            return_value=WDKSearchResponse.model_validate(
                {
                    "searchData": {
                        "urlSegment": "GenesByOrthologs",
                        "parameters": [
                            {"name": "input_step", "type": "input-step"},
                        ],
                    },
                    "validation": {"level": "DISPLAYABLE", "isValid": True},
                }
            ),
        )
        mock_get_wdk.return_value = mock_client

        graph = make_step_graph()
        step_a = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step_a)
        # Intentionally NOT setting graph.wdk_step_ids[step_a.id]

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByOrthologs",
                primary_input_step_id=step_a.id,
            ),
            callbacks=make_step_creation_callbacks(),
        )

        assert result.error is None
        assert result.step is not None
        assert result.wdk_step_id is None
        api.create_transform_step.assert_not_awaited()


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


class TestWDKPushErrorResilience:
    """WDK push failure must be non-fatal: step exists in graph, error is logged."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_wdk_push_failure_does_not_fail_step_creation(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """AppError during WDK push is swallowed; step exists in graph with no WDK ID."""
        api = AsyncMock()
        api.create_step = AsyncMock(
            side_effect=AppError(ErrorCode.WDK_ERROR, "WDK unavailable"),
        )
        mock_get_api.return_value = api
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
        assert result.wdk_step_id is None
        assert result.wdk_validation is None
        assert result.step_id in graph.steps
        assert result.step_id not in graph.wdk_step_ids

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_os_error_during_push_is_nonfatal(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """OSError (e.g. network failure) during WDK push is swallowed."""
        api = AsyncMock()
        api.create_step = AsyncMock(side_effect=OSError("Connection refused"))
        mock_get_api.return_value = api
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
        assert result.wdk_step_id is None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_validation_fetch_failure_returns_none_validation(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """If find_step fails, wdk_step_id is still set but validation is None."""
        api = AsyncMock()
        api.create_step = AsyncMock(return_value=WDKIdentifier(id=77))
        api.find_step = AsyncMock(
            side_effect=AppError(ErrorCode.WDK_ERROR, "find_step failed"),
        )
        mock_get_api.return_value = api
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
        assert result.wdk_step_id == 77
        assert result.wdk_validation is None
        assert graph.wdk_step_ids[result.step_id] == 77


# ---------------------------------------------------------------------------
# StepCreationResult backward compat
# ---------------------------------------------------------------------------


class TestStepCreationResultNewFields:
    """New wdk_step_id and wdk_validation fields default to None."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_error_result_has_none_wdk_fields(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """Error results have wdk_step_id=None and wdk_validation=None."""
        graph = make_step_graph()

        result = await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(),  # missing search_name -> error
            callbacks=make_step_creation_callbacks(),
        )

        assert result.error is not None
        assert result.wdk_step_id is None
        assert result.wdk_validation is None

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_invalid_step_validation_returned(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        """WDK validation with isValid=False is faithfully returned."""
        api = _mock_strategy_api(create_step_id=99, find_step_valid=False)
        mock_get_api.return_value = api
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
        assert result.wdk_step_id == 99
        assert result.wdk_validation is not None
        assert result.wdk_validation.is_valid is False


# ---------------------------------------------------------------------------
# Record type fallback
# ---------------------------------------------------------------------------


class TestRecordTypeFallback:
    """graph.record_type may be None — push uses 'transcript' as fallback."""

    @patch(
        "veupath_chatbot.services.strategies.step_validation.validate_parameters",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.services.strategies.step_wdk_push.get_strategy_api")
    async def test_uses_graph_record_type_when_available(
        self,
        mock_get_api: AsyncMock,
        mock_validate: AsyncMock,
    ) -> None:
        api = _mock_strategy_api(create_step_id=60)
        mock_get_api.return_value = api
        graph = make_step_graph()
        graph.record_type = "gene"

        await create_step(
            graph=graph,
            site_id="plasmodb",
            spec=StepSpec(
                search_name="GenesByText",
                parameters={"text_expression": "kinase"},
            ),
            callbacks=make_step_creation_callbacks(),
        )

        call_args = api.create_step.call_args
        assert call_args.kwargs["record_type"] == "gene"
