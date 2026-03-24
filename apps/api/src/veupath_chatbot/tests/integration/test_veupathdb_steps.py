"""Integration tests for VEuPathDB step creation."""

from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX,
    StrategyAPI,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearch,
    WDKSearchConfig,
    WDKSearchResponse,
    WDKStepTree,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock VEuPathDB client."""
    return AsyncMock(spec=VEuPathDBClient)


@pytest.fixture
def strategy_api(mock_client: AsyncMock) -> StrategyAPI:
    """Create strategy API with mock client.

    :param mock_client: Mocked WDK client.

    """
    mock_client.get.return_value = {"userId": "guest"}
    return StrategyAPI(mock_client, user_id="guest")


class TestStrategyAPI:
    """Tests for StrategyAPI."""

    @pytest.mark.asyncio
    async def test_create_step(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating a search step."""
        mock_client.post.return_value = {"id": 12345}
        # _expand_tree_params_to_leaves fetches search details
        mock_client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {"urlSegment": "GenesByGoTerm", "parameters": []},
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )

        result = await strategy_api.create_step(
            NewStepSpec(
                search_name="GenesByGoTerm",
                search_config=WDKSearchConfig(parameters={"GoTerm": "GO:0016301"}),
                custom_name="Kinases",
            ),
            record_type="gene",
        )

        assert result.id == 12345

    @pytest.mark.asyncio
    async def test_create_combined_step(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating a combined step."""
        mock_client.post.return_value = {"id": 12346}
        mock_client.get_searches.return_value = [
            WDKSearch.model_validate(
                {
                    "urlSegment": "boolean_question",
                    "fullName": "InternalQuestions.boolean_question",
                    "displayName": "Boolean",
                    "outputRecordClassName": "gene",
                    "paramNames": ["bq_left_op1", "bq_right_op1", "bq_operator"],
                    "isAnalyzable": True,
                    "isCacheable": True,
                    "groups": [],
                }
            )
        ]
        mock_client.get_search_details.return_value = WDKSearchResponse.model_validate(
            {
                "searchData": {
                    "urlSegment": "boolean_question",
                    "fullName": "InternalQuestions.boolean_question",
                    "displayName": "Boolean",
                    "paramNames": ["bq_left_op1", "bq_right_op1", "bq_operator"],
                    "groups": [],
                    "parameters": [],
                },
                "validation": {"level": "DISPLAYABLE", "isValid": True},
            }
        )

        result = await strategy_api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="INTERSECT",
            record_type="gene",
        )

        assert result.id == 12346

    @pytest.mark.asyncio
    async def test_create_strategy(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating a strategy from step tree."""
        mock_client.post.return_value = {"id": 9999}

        tree = WDKStepTree(
            step_id=100,
            primary_input=WDKStepTree(step_id=10),
            secondary_input=WDKStepTree(step_id=11),
        )

        result = await strategy_api.create_strategy(
            step_tree=tree,
            name="Test Strategy",
            is_saved=True,
        )

        assert result.id == 9999

    @pytest.mark.asyncio
    async def test_create_internal_strategy(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating an internal (Pathfinder-tagged) strategy."""
        mock_client.post.return_value = {"id": 9999}

        tree = WDKStepTree(step_id=100)
        await strategy_api.create_strategy(
            step_tree=tree,
            name="Pathfinder step counts",
            is_internal=True,
        )

        # Verify internal strategy name prefix by checking the last post call
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["name"].startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)
        assert payload["isSaved"] is False
        assert payload["isPublic"] is False


class TestWDKStepTree:
    """Tests for WDKStepTree."""

    def test_simple_tree(self) -> None:
        """Test simple step tree serialization."""
        node = WDKStepTree(step_id=100)
        assert node.model_dump(by_alias=True, exclude_none=True, mode="json") == {
            "stepId": 100
        }

    def test_nested_tree(self) -> None:
        """Test nested step tree serialization."""
        tree = WDKStepTree(
            step_id=100,
            primary_input=WDKStepTree(step_id=10),
            secondary_input=WDKStepTree(step_id=11),
        )

        result = tree.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert result["stepId"] == 100
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        assert primary_input_value["stepId"] == 10
        secondary_input_value = result.get("secondaryInput")
        assert isinstance(secondary_input_value, dict)
        assert secondary_input_value["stepId"] == 11

    def test_deeply_nested_tree(self) -> None:
        """Test deeply nested step tree."""
        tree = WDKStepTree(
            step_id=100,
            primary_input=WDKStepTree(
                step_id=50,
                primary_input=WDKStepTree(step_id=10),
                secondary_input=WDKStepTree(step_id=11),
            ),
        )

        result = tree.model_dump(by_alias=True, exclude_none=True, mode="json")
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        nested_primary_input_value = primary_input_value.get("primaryInput")
        assert isinstance(nested_primary_input_value, dict)
        assert nested_primary_input_value["stepId"] == 10
