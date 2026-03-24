"""Tests for WDK-compliant filter operations via answerSpec.viewFilters.

WDK does NOT have dedicated filter endpoints. Filters are managed through
the step's answerSpec.viewFilters array via GET/PATCH on the step resource.
"""

from unittest.mock import AsyncMock, MagicMock

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.strategy_api.filters import FilterMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKFilterValue

# ---------------------------------------------------------------------------
# Client-level tests: get_step_view_filters / update_step_view_filters
# ---------------------------------------------------------------------------


class TestClientGetStepViewFilters:
    """client.get_step_view_filters extracts viewFilters from step GET."""

    async def test_returns_view_filters_from_step(self) -> None:
        client = VEuPathDBClient.__new__(VEuPathDBClient)
        step_response = {
            "id": 42,
            "searchName": "GenesByTextSearch",
            "searchConfig": {
                "parameters": {},
                "viewFilters": [
                    {"name": "filter1", "value": {"min": 0}, "disabled": False}
                ],
            },
        }
        client.get = AsyncMock(return_value=step_response)
        result = await client.get_step_view_filters("12345", 42)
        assert len(result) == 1
        assert isinstance(result[0], WDKFilterValue)
        assert result[0].name == "filter1"
        assert result[0].value == {"min": 0}
        assert result[0].disabled is False


class TestClientUpdateStepViewFilters:
    """client.update_step_view_filters PATCHes answerSpec.viewFilters."""

    async def test_patches_step_with_view_filters(self) -> None:
        client = VEuPathDBClient.__new__(VEuPathDBClient)
        client.patch = AsyncMock(return_value={})
        filters = [
            WDKFilterValue(name="f1", value={"min": 0}, disabled=False),
        ]
        await client.update_step_view_filters("12345", 42, filters)
        call_args = client.patch.call_args
        assert call_args.args[0] == "/users/12345/steps/42"
        payload = call_args.kwargs["json"]
        assert payload == {
            "answerSpec": {
                "viewFilters": [
                    {"name": "f1", "value": {"min": 0}, "disabled": False},
                ],
            },
        }

    async def test_patches_with_empty_filters(self) -> None:
        client = VEuPathDBClient.__new__(VEuPathDBClient)
        client.patch = AsyncMock(return_value={})
        await client.update_step_view_filters("12345", 42, [])
        call_args = client.patch.call_args
        assert call_args.args[0] == "/users/12345/steps/42"
        assert call_args.kwargs["json"] == {"answerSpec": {"viewFilters": []}}


# ---------------------------------------------------------------------------
# FilterMixin tests: list, set, delete via viewFilters
# ---------------------------------------------------------------------------


def _make_filter_mixin() -> tuple[object, MagicMock]:
    """Create a FilterMixin instance with a mock client."""
    client = MagicMock()
    client.get_step_view_filters = AsyncMock(return_value=[])
    client.update_step_view_filters = AsyncMock(return_value={})
    mixin = FilterMixin(client, user_id="12345")
    mixin._session_initialized = True
    return mixin, client


class TestFilterMixinList:
    """FilterMixin.list_step_filters delegates to client.get_step_view_filters."""

    async def test_list_returns_view_filters(self) -> None:
        mixin, client = _make_filter_mixin()
        expected = [
            WDKFilterValue(name="f1", value={"min": 0}, disabled=False),
        ]
        client.get_step_view_filters.return_value = expected
        result = await mixin.list_step_filters(step_id=42)
        assert result == expected


class TestFilterMixinSet:
    """FilterMixin.set_step_filter adds/updates a filter in viewFilters."""

    async def test_adds_new_filter(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = []
        await mixin.set_step_filter(
            step_id=42,
            filter_name="ranked",
            value={"values": ["yes"]},
        )
        call_args = client.update_step_view_filters.call_args
        filters = call_args.args[2]
        assert len(filters) == 1
        assert isinstance(filters[0], WDKFilterValue)
        assert filters[0].name == "ranked"
        assert filters[0].value == {"values": ["yes"]}
        assert filters[0].disabled is False

    async def test_updates_existing_filter(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = [
            WDKFilterValue(name="ranked", value={"values": ["no"]}, disabled=False),
            WDKFilterValue(name="other", value={}, disabled=False),
        ]
        await mixin.set_step_filter(
            step_id=42,
            filter_name="ranked",
            value={"values": ["yes"]},
            disabled=True,
        )
        call_args = client.update_step_view_filters.call_args
        filters = call_args.args[2]
        assert len(filters) == 2
        ranked = next(f for f in filters if f.name == "ranked")
        assert ranked.value == {"values": ["yes"]}
        assert ranked.disabled is True
        other = next(f for f in filters if f.name == "other")
        assert other.value == {}


class TestFilterMixinDelete:
    """FilterMixin.delete_step_filter removes a filter from viewFilters."""

    async def test_removes_filter(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = [
            WDKFilterValue(name="ranked", value=5, disabled=False),
            WDKFilterValue(name="other", value={}, disabled=False),
        ]
        await mixin.delete_step_filter(step_id=42, filter_name="ranked")
        call_args = client.update_step_view_filters.call_args
        filters = call_args.args[2]
        assert len(filters) == 1
        assert filters[0].name == "other"

    async def test_delete_nonexistent_filter_is_noop(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = [
            WDKFilterValue(name="existing", value=1, disabled=False),
        ]
        await mixin.delete_step_filter(step_id=42, filter_name="nonexistent")
        call_args = client.update_step_view_filters.call_args
        filters = call_args.args[2]
        assert len(filters) == 1
        assert filters[0].name == "existing"

    async def test_delete_from_empty_filters(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = []
        await mixin.delete_step_filter(step_id=42, filter_name="any")
        call_args = client.update_step_view_filters.call_args
        filters = call_args.args[2]
        assert filters == []
