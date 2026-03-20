"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.strategies.

Tests StrategiesMixin: create_strategy, get_strategy, list_strategies,
update_strategy, set_saved, delete_strategy.
"""

from unittest.mock import AsyncMock, MagicMock

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX,
)
from veupath_chatbot.integrations.veupathdb.strategy_api.strategies import (
    StrategiesMixin,
)


def _make_mixin(user_id: str = "12345") -> tuple[StrategiesMixin, MagicMock]:
    """Create StrategiesMixin with a mock client, pre-initialized session."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    mixin = StrategiesMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


def _step_tree() -> StepTreeNode:
    """Simple step tree for testing."""
    return StepTreeNode(step_id=1)


def _binary_step_tree() -> StepTreeNode:
    """Binary step tree: combine(step1, step2) -> step3."""
    left = StepTreeNode(step_id=1)
    right = StepTreeNode(step_id=2)
    return StepTreeNode(step_id=3, primary_input=left, secondary_input=right)


# ---------------------------------------------------------------------------
# create_strategy
# ---------------------------------------------------------------------------


class TestCreateStrategy:
    """Strategy creation."""

    async def test_basic_creation(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        result = await mixin.create_strategy(
            step_tree=_step_tree(),
            name="My Strategy",
        )

        assert result["id"] == 500
        call_args = client.post.call_args
        assert "/users/12345/strategies" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["name"] == "My Strategy"
        assert payload["isPublic"] is False
        assert payload["isSaved"] is False
        assert payload["stepTree"] == {"stepId": 1}

    async def test_with_description(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_step_tree(),
            name="Test",
            description="A test strategy",
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["description"] == "A test strategy"

    async def test_public_and_saved(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_step_tree(),
            name="Public Strategy",
            is_public=True,
            is_saved=True,
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["isPublic"] is True
        assert payload["isSaved"] is True

    async def test_internal_strategy_is_tagged(self) -> None:
        """Internal strategies get the __pathfinder_internal__: prefix."""
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_step_tree(),
            name="step_counts",
            is_internal=True,
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["name"].startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)
        assert "step_counts" in payload["name"]
        # Internal strategies are never public or saved
        assert payload["isPublic"] is False
        assert payload["isSaved"] is False

    async def test_internal_overrides_public_and_saved(self) -> None:
        """Even if caller passes is_public=True, internal forces False."""
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_step_tree(),
            name="helper",
            is_internal=True,
            is_public=True,
            is_saved=True,
        )

        payload = client.post.call_args.kwargs["json"]
        assert payload["isPublic"] is False
        assert payload["isSaved"] is False

    async def test_binary_step_tree_serialization(self) -> None:
        """Verify complex step tree serializes correctly."""
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_binary_step_tree(),
            name="Binary",
        )

        payload = client.post.call_args.kwargs["json"]
        tree = payload["stepTree"]
        assert tree["stepId"] == 3
        assert tree["primaryInput"]["stepId"] == 1
        assert tree["secondaryInput"]["stepId"] == 2

    async def test_no_description_omits_key(self) -> None:
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(step_tree=_step_tree(), name="Test")

        payload = client.post.call_args.kwargs["json"]
        assert "description" not in payload


# ---------------------------------------------------------------------------
# get_strategy
# ---------------------------------------------------------------------------


class TestGetStrategy:
    """Strategy retrieval."""

    async def test_get_by_id(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = {
            "strategyId": 500,
            "name": "My Strategy",
            "rootStepId": 1,
        }

        result = await mixin.get_strategy(500)
        client.get.assert_awaited_once_with("/users/12345/strategies/500")
        assert result["strategyId"] == 500


# ---------------------------------------------------------------------------
# list_strategies
# ---------------------------------------------------------------------------


class TestListStrategies:
    """Strategy listing."""

    async def test_list_returns_array(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = [
            {"strategyId": 500, "name": "Strategy A"},
            {"strategyId": 501, "name": "Strategy B"},
        ]

        result = await mixin.list_strategies()
        client.get.assert_awaited_once_with("/users/12345/strategies")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# update_strategy
# ---------------------------------------------------------------------------


class TestUpdateStrategy:
    """Strategy updates (step tree and/or name)."""

    async def test_update_step_tree(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = {"strategyId": 500, "name": "Updated"}

        new_tree = _binary_step_tree()
        await mixin.update_strategy(500, step_tree=new_tree)

        client.put.assert_awaited_once()
        put_path = client.put.call_args.args[0]
        assert "/strategies/500/step-tree" in put_path
        put_payload = client.put.call_args.kwargs["json"]
        assert put_payload["stepTree"]["stepId"] == 3

    async def test_update_name(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = {"strategyId": 500, "name": "New Name"}

        await mixin.update_strategy(500, name="New Name")

        client.patch.assert_awaited_once()
        patch_path = client.patch.call_args.args[0]
        assert "/strategies/500" in patch_path
        patch_payload = client.patch.call_args.kwargs["json"]
        assert patch_payload["name"] == "New Name"

    async def test_update_both(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = {"strategyId": 500}

        await mixin.update_strategy(500, step_tree=_step_tree(), name="Both")

        client.put.assert_awaited_once()
        client.patch.assert_awaited_once()

    async def test_update_nothing_just_fetches(self) -> None:
        """If neither step_tree nor name is provided, just fetch the strategy."""
        mixin, client = _make_mixin()
        client.get.return_value = {"strategyId": 500}

        await mixin.update_strategy(500)

        client.put.assert_not_awaited()
        client.patch.assert_not_awaited()
        client.get.assert_awaited_once()


# ---------------------------------------------------------------------------
# set_saved
# ---------------------------------------------------------------------------


class TestSetSaved:
    """Toggle the isSaved flag."""

    async def test_set_saved_true(self) -> None:
        mixin, client = _make_mixin()
        await mixin.set_saved(500, is_saved=True)
        client.patch.assert_awaited_once_with(
            "/users/12345/strategies/500",
            json={"isSaved": True},
        )

    async def test_set_saved_false(self) -> None:
        mixin, client = _make_mixin()
        await mixin.set_saved(500, is_saved=False)
        payload = client.patch.call_args.kwargs["json"]
        assert payload["isSaved"] is False


# ---------------------------------------------------------------------------
# delete_strategy
# ---------------------------------------------------------------------------


class TestDeleteStrategy:
    """Strategy deletion."""

    async def test_delete(self) -> None:
        mixin, client = _make_mixin()
        await mixin.delete_strategy(500)
        client.delete.assert_awaited_once_with("/users/12345/strategies/500")
