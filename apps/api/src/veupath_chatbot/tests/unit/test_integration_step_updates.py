"""Unit tests for StepsMixin: _prepare_search_config, update_step_search_config, update_step_properties."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api.steps import StepsMixin
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKDisplayPreferences,
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
        params, payload = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase", "num_param": 42},
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        # Parameters should be normalized to strings
        assert params["text_expression"] == "kinase"
        assert params["num_param"] == "42"
        # Payload should contain the normalized parameters
        assert payload["parameters"] == params

    @pytest.mark.anyio
    async def test_no_wdk_weight_when_zero(self) -> None:
        mixin, _client = _make_mixin()
        _params, payload = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase"},
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        assert "wdkWeight" not in payload

    @pytest.mark.anyio
    async def test_wdk_weight_included_when_nonzero(self) -> None:
        mixin, _client = _make_mixin()
        _params, payload = await mixin._prepare_search_config(
            raw_params={"text_expression": "kinase"},
            record_type="transcript",
            search_name="GenesByTextSearch",
            wdk_weight=10,
        )
        assert payload["wdkWeight"] == 10

    @pytest.mark.anyio
    async def test_profile_pattern_expansion_triggered(self) -> None:
        """For GenesByOrthologPattern, _expand_profile_pattern_groups should be called."""
        mixin, _client = _make_mixin()
        with patch.object(
            mixin,
            "_expand_profile_pattern_groups",
            new_callable=AsyncMock,
            return_value="%AAAA:Y%BBBB:N%",
        ) as mock_expand:
            params, _payload = await mixin._prepare_search_config(
                raw_params={"profile_pattern": "%MAMM:Y%"},
                record_type="transcript",
                search_name="GenesByOrthologPattern",
            )
            mock_expand.assert_awaited_once_with("transcript", "%MAMM:Y%")
        assert params["profile_pattern"] == "%AAAA:Y%BBBB:N%"

    @pytest.mark.anyio
    async def test_profile_pattern_not_triggered_for_other_searches(self) -> None:
        mixin, _client = _make_mixin()
        with patch.object(
            mixin,
            "_expand_profile_pattern_groups",
            new_callable=AsyncMock,
        ) as mock_expand:
            _params, _payload = await mixin._prepare_search_config(
                raw_params={"profile_pattern": "%MAMM:Y%"},
                record_type="transcript",
                search_name="GenesByTextSearch",
            )
            mock_expand.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_step uses _prepare_search_config
# ---------------------------------------------------------------------------


class TestCreateStepUsesPrepare:
    """Verify create_step delegates to _prepare_search_config."""

    @pytest.mark.anyio
    async def test_create_step_calls_prepare(self) -> None:
        mixin, client = _make_mixin()
        spec = NewStepSpec(
            search_name="GenesByTextSearch",
            search_config=WDKSearchConfig(parameters={"text_expression": "kinase"}),
        )
        result = await mixin.create_step(spec, record_type="transcript")
        assert result.id == 99
        # Verify the client.post was called with normalized params
        call_args = client.post.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["searchName"] == "GenesByTextSearch"
        assert json_payload["searchConfig"]["parameters"]["text_expression"] == "kinase"


# ---------------------------------------------------------------------------
# update_step_search_config
# ---------------------------------------------------------------------------


class TestUpdateStepSearchConfig:
    """Tests for update_step_search_config."""

    @pytest.mark.anyio
    async def test_sends_put_with_search_config(self) -> None:
        mixin, client = _make_mixin()
        config = WDKSearchConfig(parameters={"text_expression": "kinase"})
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        client.put.assert_awaited_once()
        call_args = client.put.call_args
        assert "/users/12345/steps/42/search-config" in call_args.args[0]
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["parameters"]["text_expression"] == "kinase"

    @pytest.mark.anyio
    async def test_normalizes_parameters(self) -> None:
        mixin, client = _make_mixin()
        config = WDKSearchConfig(parameters={"text_expression": "kinase"})
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        call_args = client.put.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        # Values should be strings (normalized)
        assert isinstance(json_payload["parameters"]["text_expression"], str)

    @pytest.mark.anyio
    async def test_includes_wdk_weight_when_nonzero(self) -> None:
        mixin, client = _make_mixin()
        config = WDKSearchConfig(
            parameters={"text_expression": "kinase"},
            wdk_weight=5,
        )
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        call_args = client.put.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["wdkWeight"] == 5

    @pytest.mark.anyio
    async def test_omits_wdk_weight_when_zero(self) -> None:
        mixin, client = _make_mixin()
        config = WDKSearchConfig(
            parameters={"text_expression": "kinase"},
            wdk_weight=0,
        )
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        call_args = client.put.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert "wdkWeight" not in json_payload

    @pytest.mark.anyio
    async def test_user_id_override(self) -> None:
        mixin, client = _make_mixin()
        config = WDKSearchConfig(parameters={"text_expression": "kinase"})
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
            user_id="99999",
        )
        call_args = client.put.call_args
        assert "/users/99999/steps/42/search-config" in call_args.args[0]

    @pytest.mark.anyio
    async def test_returns_none(self) -> None:
        mixin, _client = _make_mixin()
        config = WDKSearchConfig(parameters={"text_expression": "kinase"})
        await mixin.update_step_search_config(
            step_id=42,
            search_config=config,
            record_type="transcript",
            search_name="GenesByTextSearch",
        )
        # update_step_search_config returns None (204 No Content)


# ---------------------------------------------------------------------------
# update_step_properties
# ---------------------------------------------------------------------------


class TestUpdateStepProperties:
    """Tests for update_step_properties."""

    @pytest.mark.anyio
    async def test_sends_patch_with_custom_name(self) -> None:
        mixin, client = _make_mixin()
        spec = PatchStepSpec(custom_name="My Step")
        await mixin.update_step_properties(step_id=42, spec=spec)
        client.patch.assert_awaited_once()
        call_args = client.patch.call_args
        assert "/users/12345/steps/42" in call_args.args[0]
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["customName"] == "My Step"

    @pytest.mark.anyio
    async def test_sends_patch_with_expanded(self) -> None:
        mixin, client = _make_mixin()
        spec = PatchStepSpec(expanded=True, expanded_name="Expanded View")
        await mixin.update_step_properties(step_id=42, spec=spec)
        call_args = client.patch.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["expanded"] is True
        assert json_payload["expandedName"] == "Expanded View"

    @pytest.mark.anyio
    async def test_sends_patch_with_display_preferences(self) -> None:
        mixin, client = _make_mixin()
        prefs = WDKDisplayPreferences(column_selection=["gene_id", "product"])
        spec = PatchStepSpec(display_preferences=prefs)
        await mixin.update_step_properties(step_id=42, spec=spec)
        call_args = client.patch.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert json_payload["displayPreferences"]["columnSelection"] == [
            "gene_id",
            "product",
        ]

    @pytest.mark.anyio
    async def test_excludes_none_fields(self) -> None:
        """PatchStepSpec with only custom_name should NOT send expanded=null."""
        mixin, client = _make_mixin()
        spec = PatchStepSpec(custom_name="Only Name")
        await mixin.update_step_properties(step_id=42, spec=spec)
        call_args = client.patch.call_args
        json_payload: dict[str, Any] = call_args.kwargs["json"]
        assert "customName" in json_payload
        assert "expanded" not in json_payload
        assert "expandedName" not in json_payload
        assert "displayPreferences" not in json_payload

    @pytest.mark.anyio
    async def test_user_id_override(self) -> None:
        mixin, client = _make_mixin()
        spec = PatchStepSpec(custom_name="Test")
        await mixin.update_step_properties(step_id=42, spec=spec, user_id="77777")
        call_args = client.patch.call_args
        assert "/users/77777/steps/42" in call_args.args[0]

    @pytest.mark.anyio
    async def test_returns_none(self) -> None:
        mixin, _client = _make_mixin()
        spec = PatchStepSpec(custom_name="Test")
        await mixin.update_step_properties(step_id=42, spec=spec)
        # update_step_properties returns None (204 No Content)
