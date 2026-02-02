"""Integration tests for VEuPathDB step creation."""

import pytest
from unittest.mock import AsyncMock

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI, StepTreeNode


@pytest.fixture
def mock_client():
    """Create a mock VEuPathDB client."""
    client = AsyncMock(spec=VEuPathDBClient)
    return client


@pytest.fixture
def strategy_api(mock_client):
    """Create strategy API with mock client."""
    api = StrategyAPI.__new__(StrategyAPI)
    api.client = mock_client
    api.user_id = "guest"
    return api


class TestStrategyAPI:
    """Tests for StrategyAPI."""

    @pytest.mark.asyncio
    async def test_create_step(self, strategy_api, mock_client):
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
    async def test_create_combined_step(self, strategy_api, mock_client):
        """Test creating a combined step."""
        mock_client.post.return_value = {"id": 12346}

        result = await strategy_api.create_combined_step(
            primary_step_id=100,
            secondary_step_id=101,
            boolean_operator="INTERSECT",
        )

        assert result["id"] == 12346
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["searchName"] == "boolean_question"

    @pytest.mark.asyncio
    async def test_create_strategy(self, strategy_api, mock_client):
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


class TestStepTreeNode:
    """Tests for StepTreeNode."""

    def test_simple_tree(self):
        """Test simple step tree serialization."""
        node = StepTreeNode(step_id=100)
        assert node.to_dict() == {"stepId": 100}

    def test_nested_tree(self):
        """Test nested step tree serialization."""
        tree = StepTreeNode(
            step_id=100,
            primary_input=StepTreeNode(step_id=10),
            secondary_input=StepTreeNode(step_id=11),
        )

        result = tree.to_dict()
        assert result["stepId"] == 100
        assert result["primaryInput"]["stepId"] == 10
        assert result["secondaryInput"]["stepId"] == 11

    def test_deeply_nested_tree(self):
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
        assert result["primaryInput"]["primaryInput"]["stepId"] == 10

