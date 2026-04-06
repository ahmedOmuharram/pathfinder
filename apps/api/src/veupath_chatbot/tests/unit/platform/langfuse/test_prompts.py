"""Tests for Langfuse prompt management with local fallback."""

from unittest.mock import MagicMock, patch

import pytest

from veupath_chatbot.platform.langfuse.prompts import load_prompt, seed_prompts


class TestLoadPromptLocalFallback:
    """When Langfuse is disabled (returns None), prompts load from local files."""

    def test_loads_system_prompt_from_local(self) -> None:
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=None,
        ):
            result = load_prompt("system")
        assert len(result) > 100
        assert "VEuPathDB" in result

    def test_loads_safety_prompt_from_local(self) -> None:
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=None,
        ):
            result = load_prompt("safety")
        assert len(result) > 0

    def test_loads_site_hints_prompt_from_local(self) -> None:
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=None,
        ):
            result = load_prompt("site-hints")
        assert len(result) > 0

    def test_loads_workbench_prompt_from_local(self) -> None:
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=None,
        ):
            result = load_prompt("workbench")
        assert len(result) > 0


class TestLoadPromptLangfuseError:
    """When Langfuse client raises a caught error, falls back to local."""

    def test_falls_back_on_langfuse_api_error(self) -> None:
        mock_client = MagicMock()
        mock_client.get_prompt.side_effect = OSError("connection refused")
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            result = load_prompt("system")
        assert len(result) > 100

    def test_falls_back_on_value_error(self) -> None:
        mock_client = MagicMock()
        mock_client.get_prompt.side_effect = ValueError("bad arg")
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            result = load_prompt("system")
        assert len(result) > 100


class TestLoadPromptFromLangfuse:
    """When Langfuse client succeeds, returns its content."""

    def test_uses_langfuse_when_available(self) -> None:
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "langfuse prompt content"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            result = load_prompt("system")
        assert result == "langfuse prompt content"
        mock_client.get_prompt.assert_called_once_with("system", label="production")

    def test_custom_label(self) -> None:
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "staging content"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            result = load_prompt("system", label="staging")
        assert result == "staging content"
        mock_client.get_prompt.assert_called_once_with("system", label="staging")


class TestLoadPromptUnknownName:
    """Unknown prompt names raise ValueError."""

    def test_raises_value_error(self) -> None:
        with (
            patch(
                "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
                return_value=None,
            ),
            pytest.raises(ValueError, match="nonexistent"),
        ):
            load_prompt("nonexistent")


class TestSeedPrompts:
    """seed_prompts uploads local files to Langfuse."""

    def test_noop_when_langfuse_disabled(self) -> None:
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=None,
        ):
            seed_prompts()  # Should not raise

    def test_seeds_missing_prompts(self) -> None:
        mock_client = MagicMock()
        # get_prompt raises for all names (they don't exist yet)
        mock_client.get_prompt.side_effect = ValueError("not found")
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            seed_prompts()

        assert mock_client.create_prompt.call_count == 4

    def test_skips_existing_prompts(self) -> None:
        mock_client = MagicMock()
        # get_prompt succeeds for all (prompts already exist)
        mock_client.get_prompt.return_value = MagicMock()
        with patch(
            "veupath_chatbot.platform.langfuse.prompts.get_langfuse",
            return_value=mock_client,
        ):
            seed_prompts()

        mock_client.create_prompt.assert_not_called()
