"""Integration tests for VEuPathDB step creation."""

from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX,
    StepTreeNode,
    StrategyAPI,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock VEuPathDB client."""
    client = AsyncMock(spec=VEuPathDBClient)
    return client


@pytest.fixture
def strategy_api(mock_client: AsyncMock) -> StrategyAPI:
    """Create strategy API with mock client."""
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

        result = await strategy_api.create_step(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={"GoTerm": "GO:0016301"},
            custom_name="Kinases",
        )

        assert result["id"] == 12345
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/users/guest/steps" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_combined_step(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating a combined step."""
        mock_client.post.return_value = {"id": 12346}
        mock_client.get_searches.return_value = [{"urlSegment": "boolean_question"}]
        mock_client.get_search_details.return_value = {
            "searchData": {"paramNames": ["bq_left_op1", "bq_right_op1", "bq_operator"]}
        }

        result = await strategy_api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="INTERSECT",
            record_type="gene",
        )

        assert result["id"] == 12346
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["searchName"] == "boolean_question"

    @pytest.mark.asyncio
    async def test_create_strategy(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating a strategy from step tree."""
        mock_client.post.return_value = {"strategyId": 9999}

        tree = StepTreeNode(
            step_id=100,
            primary_input=StepTreeNode(step_id=10),
            secondary_input=StepTreeNode(step_id=11),
        )

        result = await strategy_api.create_strategy(
            step_tree=tree,
            name="Test Strategy",
        )

        assert result["strategyId"] == 9999
        call_args = mock_client.post.call_args
        assert "/users/guest/strategies" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["name"] == "Test Strategy"
        assert payload["isSaved"] is True

    @pytest.mark.asyncio
    async def test_create_internal_strategy(
        self, strategy_api: StrategyAPI, mock_client: AsyncMock
    ) -> None:
        """Test creating an internal (Pathfinder-tagged) strategy."""
        mock_client.post.return_value = {"strategyId": 9999}

        tree = StepTreeNode(step_id=100)
        await strategy_api.create_strategy(
            step_tree=tree,
            name="Pathfinder step counts",
            is_internal=True,
        )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["name"].startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)
        assert payload["isSaved"] is False
        assert payload["isPublic"] is False


class TestStepTreeNode:
    """Tests for StepTreeNode."""

    def test_simple_tree(self) -> None:
        """Test simple step tree serialization."""
        node = StepTreeNode(step_id=100)
        assert node.to_dict() == {"stepId": 100}

    def test_nested_tree(self) -> None:
        """Test nested step tree serialization."""
        tree = StepTreeNode(
            step_id=100,
            primary_input=StepTreeNode(step_id=10),
            secondary_input=StepTreeNode(step_id=11),
        )

        result = tree.to_dict()
        assert result["stepId"] == 100
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        assert primary_input_value["stepId"] == 10
        secondary_input_value = result.get("secondaryInput")
        assert isinstance(secondary_input_value, dict)
        assert secondary_input_value["stepId"] == 11

    def test_deeply_nested_tree(self) -> None:
        """Test deeply nested step tree."""
        tree = StepTreeNode(
            step_id=100,
            primary_input=StepTreeNode(
                step_id=50,
                primary_input=StepTreeNode(step_id=10),
                secondary_input=StepTreeNode(step_id=11),
            ),
        )

        result = tree.to_dict()
        primary_input_value = result.get("primaryInput")
        assert isinstance(primary_input_value, dict)
        nested_primary_input_value = primary_input_value.get("primaryInput")
        assert isinstance(nested_primary_input_value, dict)
        assert nested_primary_input_value["stepId"] == 10
