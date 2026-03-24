"""Unit tests for veupath_chatbot.integrations.veupathdb.strategy_api.base.

Tests StrategyAPIBase: initialization, _normalize_parameters, _ensure_session.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase


def _make_base(user_id: str = "current") -> tuple[StrategyAPIBase, MagicMock]:
    """Create a StrategyAPIBase with a mock client."""
    client = MagicMock()
    client.get = AsyncMock()
    base = StrategyAPIBase(client, user_id=user_id)
    return base, client


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    """Verify constructor state."""

    def test_default_user_id_is_current(self) -> None:
        client = MagicMock()
        base = StrategyAPIBase(client)
        assert base._resolved_user_id == "current"
        assert base._initial_user_id == "current"

    def test_custom_user_id(self) -> None:
        client = MagicMock()
        base = StrategyAPIBase(client, user_id="12345")
        assert base._resolved_user_id == "12345"
        assert base._initial_user_id == "12345"

    def test_session_not_initialized(self) -> None:
        client = MagicMock()
        base = StrategyAPIBase(client)
        assert base._session_initialized is False

    def test_caches_initialized_empty(self) -> None:
        client = MagicMock()
        base = StrategyAPIBase(client)
        assert base._boolean_search_cache == {}
        assert base._answer_param_cache == {}


# ---------------------------------------------------------------------------
# _normalize_parameters
# ---------------------------------------------------------------------------


class TestNormalizeParameters:
    """WDK requires all param values as strings; empty values are omitted."""

    def test_string_values_pass_through(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({"text_expression": "kinase"})
        assert result == {"text_expression": "kinase"}

    def test_int_values_converted(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({"hard_floor": 10})
        assert result == {"hard_floor": "10"}

    def test_float_values_converted(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({"pvalue": 0.05})
        assert result == {"pvalue": "0.05"}

    def test_bool_values_converted(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({"flag": True})
        assert result == {"flag": "true"}

    def test_list_values_json_encoded(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({"organism": ["Plasmodium falciparum 3D7"]})
        assert result == {"organism": '["Plasmodium falciparum 3D7"]'}

    def test_none_value_becomes_empty_and_is_omitted(self) -> None:
        """None normalizes to '' which is empty, so the key is dropped."""
        base, _ = _make_base()
        result = base._normalize_parameters({"optional_param": None})
        assert result == {}

    def test_empty_string_is_kept(self) -> None:
        """Explicit empty strings are kept — the caller set the param intentionally."""
        base, _ = _make_base()
        result = base._normalize_parameters({"hard_floor": ""})
        assert result == {"hard_floor": ""}

    def test_whitespace_only_is_kept_as_empty(self) -> None:
        """Whitespace-only strings are kept (the value was an explicit str)."""
        base, _ = _make_base()
        result = base._normalize_parameters({"param": "   "})
        assert result == {"param": ""}

    def test_keep_empty_preserves_specified_params(self) -> None:
        """AnswerParams must be kept as '' even when empty.
        Regular empty strings are also kept (explicit str values)."""
        base, _ = _make_base()
        result = base._normalize_parameters(
            {"answer_param": "", "regular_param": ""},
            keep_empty={"answer_param"},
        )
        assert result == {"answer_param": "", "regular_param": ""}

    def test_keep_empty_with_none_value(self) -> None:
        """None values are always dropped (even if in keep_empty)."""
        base, _ = _make_base()
        result = base._normalize_parameters(
            {"answer_param": None},
            keep_empty={"answer_param"},
        )
        assert result == {}

    def test_none_parameters_returns_empty(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters(None)
        assert result == {}

    def test_empty_parameters_returns_empty(self) -> None:
        base, _ = _make_base()
        result = base._normalize_parameters({})
        assert result == {}

    def test_mixed_parameters(self) -> None:
        """Realistic scenario with different param types."""
        base, _ = _make_base()
        result = base._normalize_parameters(
            {
                "organism": ["Plasmodium falciparum 3D7"],
                "text_expression": "kinase",
                "hard_floor": 10,
                "optional": None,
                "empty": "",
            }
        )
        assert "organism" in result
        assert "text_expression" in result
        assert "hard_floor" in result
        assert "optional" not in result
        assert "empty" in result  # explicit str values are kept


# ---------------------------------------------------------------------------
# _ensure_session
# ---------------------------------------------------------------------------


class TestEnsureSession:
    """Session resolution: resolves 'current' to a numeric WDK user ID."""

    async def test_resolves_current_user_id(self) -> None:
        base, _ = _make_base()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value="98765",
        ):
            await base._ensure_session()
        assert base._resolved_user_id == "98765"
        assert base._session_initialized is True

    async def test_does_not_resolve_when_already_initialized(self) -> None:
        base, _ = _make_base()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value="98765",
        ):
            await base._ensure_session()
            await base._ensure_session()
        # Second call should not overwrite the resolved user ID
        assert base._resolved_user_id == "98765"
        assert base._session_initialized is True

    async def test_does_not_resolve_when_user_id_not_current(self) -> None:
        """If user_id is already a concrete ID, skip resolution."""
        base, _ = _make_base(user_id="12345")
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value="99999",
        ):
            await base._ensure_session()
        # Should keep the original user ID, not replace with resolved value
        assert base._resolved_user_id == "12345"

    async def test_keeps_current_when_resolve_returns_none(self) -> None:
        base, _ = _make_base()
        with patch(
            "veupath_chatbot.integrations.veupathdb.strategy_api.base.resolve_wdk_user_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await base._ensure_session()
        assert base._resolved_user_id == "current"
        assert base._session_initialized is True
