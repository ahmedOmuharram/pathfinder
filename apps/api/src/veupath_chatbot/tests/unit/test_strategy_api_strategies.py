"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.strategies.

Tests StrategiesMixin: create_strategy, get_strategy, list_strategies,
update_strategy, set_saved, delete_strategy, get_duplicated_step_tree.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from veupath_chatbot.domain.strategy.ast import StepTreeNode
from veupath_chatbot.integrations.veupathdb.strategy_api.helpers import (
    PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX,
)
from veupath_chatbot.integrations.veupathdb.strategy_api.strategies import (
    StrategiesMixin,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKIdentifier,
    WDKStepTree,
    WDKStrategyDetails,
    WDKStrategySummary,
)
from veupath_chatbot.platform.errors import DataParsingError


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


def _strategy_details_dict(
    strategy_id: int = 500,
    name: str = "My Strategy",
    root_step_id: int = 1,
) -> dict[str, object]:
    """Minimal valid WDK strategy details dict for model_validate."""
    return {
        "strategyId": strategy_id,
        "name": name,
        "rootStepId": root_step_id,
        "stepTree": {"stepId": root_step_id},
    }


def _strategy_summary_dict(
    strategy_id: int = 500,
    name: str = "Strategy A",
    root_step_id: int = 1,
) -> dict[str, object]:
    """Minimal valid WDK strategy summary dict for model_validate."""
    return {
        "strategyId": strategy_id,
        "name": name,
        "rootStepId": root_step_id,
    }


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

        assert isinstance(result, WDKIdentifier)
        assert result.id == 500
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

    async def test_explicit_user_id(self) -> None:
        """Explicit user_id is used in the URL instead of resolved one."""
        mixin, client = _make_mixin()
        client.post.return_value = {"id": 500}

        await mixin.create_strategy(
            step_tree=_step_tree(),
            name="Test",
            user_id="99999",
        )

        call_args = client.post.call_args
        assert "/users/99999/strategies" in call_args.args[0]


# ---------------------------------------------------------------------------
# get_strategy
# ---------------------------------------------------------------------------


class TestGetStrategy:
    """Strategy retrieval."""

    async def test_get_by_id(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500, "My Strategy")

        result = await mixin.get_strategy(500)
        client.get.assert_awaited_once_with("/users/12345/strategies/500")
        assert isinstance(result, WDKStrategyDetails)
        assert result.strategy_id == 500
        assert result.name == "My Strategy"

    async def test_get_raises_on_invalid_response(self) -> None:
        """DataParsingError when WDK returns non-strategy data."""
        mixin, client = _make_mixin()
        client.get.return_value = {"unexpected": "data"}

        with pytest.raises(DataParsingError):
            await mixin.get_strategy(500)

    async def test_get_with_explicit_user_id(self) -> None:
        """Explicit user_id is used in the URL."""
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500, "My Strategy")

        await mixin.get_strategy(500, user_id="77777")
        client.get.assert_awaited_once_with("/users/77777/strategies/500")


# ---------------------------------------------------------------------------
# list_strategies
# ---------------------------------------------------------------------------


class TestListStrategies:
    """Strategy listing."""

    async def test_list_returns_typed_summaries(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = [
            _strategy_summary_dict(500, "Strategy A"),
            _strategy_summary_dict(501, "Strategy B"),
        ]

        result = await mixin.list_strategies()
        client.get.assert_awaited_once_with("/users/12345/strategies")
        assert len(result) == 2
        assert all(isinstance(s, WDKStrategySummary) for s in result)
        assert result[0].strategy_id == 500
        assert result[1].strategy_id == 501

    async def test_list_returns_empty_for_non_list(self) -> None:
        """Non-list response returns empty list instead of crashing."""
        mixin, client = _make_mixin()
        client.get.return_value = {"error": "something"}

        result = await mixin.list_strategies()
        assert result == []

    async def test_list_skips_invalid_items(self) -> None:
        """Invalid items in the list are silently skipped."""
        mixin, client = _make_mixin()
        client.get.return_value = [
            _strategy_summary_dict(500, "Good"),
            {"broken": True},  # Missing required fields
            _strategy_summary_dict(501, "Also Good"),
        ]

        result = await mixin.list_strategies()
        assert len(result) == 2
        assert result[0].strategy_id == 500
        assert result[1].strategy_id == 501

    async def test_list_with_explicit_user_id(self) -> None:
        """Explicit user_id is used in the URL."""
        mixin, client = _make_mixin()
        client.get.return_value = []

        await mixin.list_strategies(user_id="88888")
        client.get.assert_awaited_once_with("/users/88888/strategies")


# ---------------------------------------------------------------------------
# update_strategy
# ---------------------------------------------------------------------------


class TestUpdateStrategy:
    """Strategy updates (step tree and/or name)."""

    async def test_update_step_tree(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500, "Updated")

        new_tree = _binary_step_tree()
        result = await mixin.update_strategy(500, step_tree=new_tree)

        client.put.assert_awaited_once()
        put_path = client.put.call_args.args[0]
        assert "/strategies/500/step-tree" in put_path
        put_payload = client.put.call_args.kwargs["json"]
        assert put_payload["stepTree"]["stepId"] == 3
        assert isinstance(result, WDKStrategyDetails)

    async def test_update_name(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500, "New Name")

        result = await mixin.update_strategy(500, name="New Name")

        client.patch.assert_awaited_once()
        patch_path = client.patch.call_args.args[0]
        assert "/strategies/500" in patch_path
        patch_payload = client.patch.call_args.kwargs["json"]
        assert patch_payload["name"] == "New Name"
        assert isinstance(result, WDKStrategyDetails)

    async def test_update_both(self) -> None:
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500)

        result = await mixin.update_strategy(500, step_tree=_step_tree(), name="Both")

        client.put.assert_awaited_once()
        client.patch.assert_awaited_once()
        assert isinstance(result, WDKStrategyDetails)

    async def test_update_nothing_just_fetches(self) -> None:
        """If neither step_tree nor name is provided, just fetch the strategy."""
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500)

        result = await mixin.update_strategy(500)

        client.put.assert_not_awaited()
        client.patch.assert_not_awaited()
        client.get.assert_awaited_once()
        assert isinstance(result, WDKStrategyDetails)

    async def test_update_with_explicit_user_id(self) -> None:
        """Explicit user_id is used in all URLs."""
        mixin, client = _make_mixin()
        client.get.return_value = _strategy_details_dict(500)

        await mixin.update_strategy(500, name="Test", user_id="66666")

        patch_path = client.patch.call_args.args[0]
        assert "/users/66666/" in patch_path
        get_path = client.get.call_args.args[0]
        assert "/users/66666/" in get_path


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

    async def test_set_saved_with_explicit_user_id(self) -> None:
        mixin, client = _make_mixin()
        await mixin.set_saved(500, is_saved=True, user_id="55555")
        path = client.patch.call_args.args[0]
        assert "/users/55555/strategies/500" in path


# ---------------------------------------------------------------------------
# delete_strategy
# ---------------------------------------------------------------------------


class TestDeleteStrategy:
    """Strategy deletion."""

    async def test_delete(self) -> None:
        mixin, client = _make_mixin()
        await mixin.delete_strategy(500)
        client.delete.assert_awaited_once_with("/users/12345/strategies/500")

    async def test_delete_with_explicit_user_id(self) -> None:
        mixin, client = _make_mixin()
        await mixin.delete_strategy(500, user_id="44444")
        client.delete.assert_awaited_once_with("/users/44444/strategies/500")


# ---------------------------------------------------------------------------
# get_duplicated_step_tree
# ---------------------------------------------------------------------------


class TestGetDuplicatedStepTree:
    """Duplicated step tree retrieval."""

    async def test_unwraps_step_tree_wrapper(self) -> None:
        """WDK returns {'stepTree': {...}}, method unwraps it."""
        mixin, client = _make_mixin()
        client.post.return_value = {
            "stepTree": {"stepId": 100, "primaryInput": {"stepId": 50}},
        }

        result = await mixin.get_duplicated_step_tree(200)

        assert isinstance(result, WDKStepTree)
        assert result.step_id == 100
        assert result.primary_input is not None
        assert result.primary_input.step_id == 50
        client.post.assert_awaited_once_with(
            "/users/12345/strategies/200/duplicated-step-tree",
            json={},
        )

    async def test_handles_raw_tree_response(self) -> None:
        """Some WDK versions may return the tree directly without wrapper."""
        mixin, client = _make_mixin()
        client.post.return_value = {"stepId": 100}

        result = await mixin.get_duplicated_step_tree(200)

        assert isinstance(result, WDKStepTree)
        assert result.step_id == 100

    async def test_with_explicit_user_id(self) -> None:
        """Explicit user_id is used in the URL."""
        mixin, client = _make_mixin()
        client.post.return_value = {"stepTree": {"stepId": 100}}

        await mixin.get_duplicated_step_tree(200, user_id="33333")

        path = client.post.call_args.args[0]
        assert "/users/33333/" in path

    async def test_binary_tree_structure(self) -> None:
        """Full binary tree with primary + secondary inputs."""
        mixin, client = _make_mixin()
        client.post.return_value = {
            "stepTree": {
                "stepId": 300,
                "primaryInput": {"stepId": 100},
                "secondaryInput": {"stepId": 200},
            },
        }

        result = await mixin.get_duplicated_step_tree(999)

        assert result.step_id == 300
        assert result.primary_input is not None
        assert result.primary_input.step_id == 100
        assert result.secondary_input is not None
        assert result.secondary_input.step_id == 200
