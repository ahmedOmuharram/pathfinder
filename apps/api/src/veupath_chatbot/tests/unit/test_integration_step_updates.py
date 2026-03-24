"""Unit tests for StepsMixin: _prepare_search_config, update_step_search_config, update_step_properties."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
)


def _make_client(
    *,
    post_return: object = None,
    put_return: object = None,
    patch_return: object = None,
    get_search_details_return: object = None,
) -> MagicMock:
    """Create a mock VEuPathDB client."""
    client = MagicMock()
    client.post = AsyncMock(return_value=post_return or {"id": 99})
    client.put = AsyncMock(return_value=put_return)
    client.patch = AsyncMock(return_value=patch_return)
    if get_search_details_return is not None:
        client.get_search_details = AsyncMock(return_value=get_search_details_return)
    else:
        # Default: return empty params so tree expansion is a no-op
        search_data = MagicMock()
        search_data.parameters = []
        response = MagicMock()
        response.search_data = search_data
        client.get_search_details = AsyncMock(return_value=response)
    return client


def _make_mixin(
    *,
    user_id: str = "12345",
    post_return: object = None,
    put_return: object = None,
    patch_return: object = None,
    get_search_details_return: object = None,
) -> tuple[StepsMixin, MagicMock]:
    """Create a StepsMixin with a mocked VEuPathDBClient.

    Returns (mixin, client) so tests can inspect mock call_args on the client.
    """
    client = _make_client(
        post_return=post_return,
        put_return=put_return,
        patch_return=patch_return,
        get_search_details_return=get_search_details_return,
    )
    mixin = StepsMixin(client, user_id=user_id)
    # Pre-resolve user id to avoid async resolution
    mixin._session_initialized = True
    mixin._resolved_user_id = user_id
    return mixin, client


# ---------------------------------------------------------------------------
# _prepare_search_config
# ---------------------------------------------------------------------------


class TestPrepareSearchConfig:
    """Tests for the extracted _prepare_search_config helper."""

    @pytest.mark.anyio
    async def test_normalizes_parameters(self) -> None:
        mixin, _client = _make_mixin()
        params, config = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase", "num_param": 42},
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        # Parameters should be normalized to strings
        assert params["text_expression"] == "kinase"
        assert params["num_param"] == "42"
        # Config should contain the normalized parameters
        assert config.parameters == params

    @pytest.mark.anyio
    async def test_no_wdk_weight_when_zero(self) -> None:
        mixin, _client = _make_mixin()
        _params, config = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase"},
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        assert config.wdk_weight == 0

    @pytest.mark.anyio
    async def test_wdk_weight_included_when_nonzero(self) -> None:
        mixin, _client = _make_mixin()
        _params, config = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase"},
            record_type="transcript",
            search_name="GenesByTextSearch",
            wdk_weight=10,
        )
        assert config.wdk_weight == 10

    @pytest.mark.anyio
    async def test_profile_pattern_expansion_triggered(self) -> None:
        """For GenesByOrthologPattern, _expand_profile_pattern_groups should be called."""
        mixin, _client = _make_mixin()
        with patch.object(
            mixin,
            "_expand_profile_pattern_groups",
            new_callable=AsyncMock,
            return_value="%AAAA:Y%BBBB:N%",
        ):
            params, _payload = await mixin._prepare_search_config(
                raw_params={"profile_pattern": "%MAMM:Y%"},
                record_type="transcript",
                search_name="GenesByOrthologPattern",
            )
        assert params["profile_pattern"] == "%AAAA:Y%BBBB:N%"



# ---------------------------------------------------------------------------
# create_step uses _prepare_search_config
# ---------------------------------------------------------------------------


class TestCreateStepUsesPrepare:
    """Verify create_step delegates to _prepare_search_config."""

    @pytest.mark.anyio
    async def test_create_step_calls_prepare(self) -> None:
        mixin, _client = _make_mixin()
        spec = NewStepSpec(
            search_name="GenesByTextSearch",
            search_config=WDKSearchConfig(parameters={"text_expression": "kinase"}),
        )
        result = await mixin.create_step(spec, record_type="transcript")
        assert result.id == 99


# ---------------------------------------------------------------------------
# update_step_search_config
# ---------------------------------------------------------------------------


