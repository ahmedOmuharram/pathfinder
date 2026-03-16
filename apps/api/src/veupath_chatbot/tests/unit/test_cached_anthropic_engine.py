"""Tests for CachedAnthropicEngine — prompt caching via cache_control."""

from unittest.mock import patch

from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine

_TRANSLATED: list[dict] = [{"role": "user", "content": "hello"}]


class TestSystemPromptCaching:
    """System prompts should be wrapped with cache_control."""

    def test_wraps_system_string_with_cache_control(self):
        parent_kwargs = {
            "system": "You are a helpful assistant",
            "model": "claude-4-opus",
        }
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, translated = CachedAnthropicEngine._prepare_request([], [])

        assert isinstance(kwargs["system"], list)
        assert len(kwargs["system"]) == 1
        block = kwargs["system"][0]
        assert block["type"] == "text"
        assert block["text"] == "You are a helpful assistant"
        assert block["cache_control"] == {"type": "ephemeral"}
        assert translated == _TRANSLATED

    def test_no_system_key_no_crash(self):
        parent_kwargs = {"model": "claude-4-opus"}
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, translated = CachedAnthropicEngine._prepare_request([], [])

        assert "system" not in kwargs
        assert translated == _TRANSLATED

    def test_empty_system_string_not_wrapped(self):
        parent_kwargs = {"system": "", "model": "claude-4-opus"}
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, translated = CachedAnthropicEngine._prepare_request([], [])

        # Empty string is falsy, so isinstance check + truthiness should skip it
        assert kwargs["system"] == ""

    def test_system_already_list_not_double_wrapped(self):
        """If parent somehow returns a list, it should NOT be re-wrapped."""
        existing = [
            {
                "type": "text",
                "text": "already wrapped",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        parent_kwargs = {"system": existing, "model": "claude-4-opus"}
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, _ = CachedAnthropicEngine._prepare_request([], [])

        # Since system is a list (not a string), isinstance(system_text, str) is False
        assert kwargs["system"] is existing

    def test_system_none_not_wrapped(self):
        parent_kwargs = {"system": None, "model": "claude-4-opus"}
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, _ = CachedAnthropicEngine._prepare_request([], [])

        assert kwargs["system"] is None

    def test_preserves_other_kwargs(self):
        parent_kwargs = {
            "system": "You are an assistant",
            "model": "claude-4-opus",
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        with patch.object(
            CachedAnthropicEngine.__mro__[1],
            "_prepare_request",
            return_value=(parent_kwargs, _TRANSLATED),
        ):
            kwargs, _ = CachedAnthropicEngine._prepare_request([], [])

        assert kwargs["model"] == "claude-4-opus"
        assert kwargs["max_tokens"] == 1024
        assert kwargs["temperature"] == 0.7
        assert isinstance(kwargs["system"], list)
