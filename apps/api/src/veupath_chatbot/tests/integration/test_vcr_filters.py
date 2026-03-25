"""VCR-backed integration tests for WDK filter operations.

Tests filter CRUD via answerSpec.viewFilters on real WDK step resources.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_filters.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_filters.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKFilterValue
from veupath_chatbot.tests.conftest import create_taxon_step, materialize_step


class TestClientGetStepViewFilters:
    """client.get_step_view_filters extracts viewFilters from step GET."""

    @pytest.mark.vcr
    async def test_returns_view_filters_from_step(
        self, wdk_api: StrategyAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        uid = await wdk_api._get_user_id(None)

        result = await wdk_api.client.get_step_view_filters(uid, step.id)

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, WDKFilterValue)


class TestFilterMixinList:
    """FilterMixin.list_step_filters delegates to client.get_step_view_filters."""

    @pytest.mark.vcr
    async def test_list_returns_view_filters(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        result = await wdk_api.list_step_filters(step_id=step.id)

        assert isinstance(result, list)


class TestFilterMixinSet:
    """FilterMixin.set_step_filter adds/updates a filter in viewFilters."""

    @pytest.mark.vcr
    async def test_adds_new_filter(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        await wdk_api.set_step_filter(
            step_id=step.id,
            filter_name="matched_transcript_filter_array",
            value={"values": ["Y"]},
        )

        filters = await wdk_api.list_step_filters(step_id=step.id)
        assert any(f.name == "matched_transcript_filter_array" for f in filters)


class TestFilterMixinDelete:
    """FilterMixin.delete_step_filter removes a filter from viewFilters."""

    @pytest.mark.vcr
    async def test_removes_filter(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        await wdk_api.set_step_filter(
            step_id=step.id,
            filter_name="matched_transcript_filter_array",
            value={"values": ["Y"]},
        )

        # Verify filter was set
        filters_before = await wdk_api.list_step_filters(step_id=step.id)
        assert any(
            f.name == "matched_transcript_filter_array" for f in filters_before
        )

        # Delete should not crash
        await wdk_api.delete_step_filter(
            step_id=step.id,
            filter_name="matched_transcript_filter_array",
        )

    @pytest.mark.vcr
    async def test_delete_nonexistent_filter_is_noop(
        self, wdk_api: StrategyAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        await wdk_api.delete_step_filter(
            step_id=step.id,
            filter_name="nonexistent_filter",
        )

        filters = await wdk_api.list_step_filters(step_id=step.id)
        assert isinstance(filters, list)
