"""Smoke test: verify the wdk_api fixture provides a real StrategyAPI."""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI


@pytest.mark.vcr
async def test_wdk_api_can_get_record_types(wdk_api: StrategyAPI) -> None:
    """The wdk_api fixture returns a working StrategyAPI backed by VCR cassettes."""
    result = await wdk_api.client.get_record_types()
    assert isinstance(result, list)
    assert len(result) > 0
