"""Tests for ResponsesOpenAIEngine — Responses API without forced encrypted reasoning."""

from unittest.mock import patch

import pytest

from veupath_chatbot.ai.engines.responses_openai import ResponsesOpenAIEngine


def _fake_openai_init(self, *args, **kwargs):
    """Fake OpenAIEngine.__init__ that sets minimal required attrs."""
    self.model = kwargs.get("model", args[0] if args else "unknown")
    self.api_type = kwargs.get("api_type", "responses")


@pytest.fixture
def _patch_openai_init():
    """Prevent actual OpenAI client construction during tests."""
    with patch("kani.engines.openai.OpenAIEngine.__init__", _fake_openai_init):
        yield


def _make_engine(model: str):
    """Build a ResponsesOpenAIEngine with a patched parent __init__."""
    with patch("kani.engines.openai.OpenAIEngine.__init__", _fake_openai_init):
        engine = ResponsesOpenAIEngine(model=model)
    return engine


# ---------------------------------------------------------------------------
# api_type defaults
# ---------------------------------------------------------------------------


class TestApiTypeDefault:
    """api_type should default to 'responses'."""

    def test_defaults_to_responses(self, _patch_openai_init):
        engine = ResponsesOpenAIEngine(model="gpt-4.1")
        assert engine.api_type == "responses"

    def test_explicit_api_type_preserved(self, _patch_openai_init):
        engine = ResponsesOpenAIEngine(model="gpt-4.1", api_type="chat")
        assert engine.api_type == "chat"


# ---------------------------------------------------------------------------
# _prepare_request: stripping reasoning.encrypted_content
# ---------------------------------------------------------------------------

_TRANSLATED: list[dict] = [{"role": "user", "content": "hi"}]
_TOOLS = None


class TestPrepareRequestNonReasoningModels:
    """Non-reasoning models must have reasoning.encrypted_content stripped."""

    @pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
    def test_strips_reasoning_encrypted_content(self, model):
        engine = _make_engine(model)
        parent_kwargs = {
            "include": ["reasoning.encrypted_content", "usage"],
            "model": model,
        }

        with patch(
            "kani.engines.openai.OpenAIEngine._prepare_request",
            return_value=(parent_kwargs, _TRANSLATED, _TOOLS),
        ):
            kwargs, translated, tools = engine._prepare_request([], [])

        assert "reasoning.encrypted_content" not in kwargs.get("include", [])
        assert "usage" in kwargs["include"]

    @pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"])
    def test_removes_include_key_when_empty(self, model):
        engine = _make_engine(model)
        parent_kwargs = {
            "include": ["reasoning.encrypted_content"],
            "model": model,
        }

        with patch(
            "kani.engines.openai.OpenAIEngine._prepare_request",
            return_value=(parent_kwargs, _TRANSLATED, _TOOLS),
        ):
            kwargs, _, _ = engine._prepare_request([], [])

        assert "include" not in kwargs

    @pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4.1-mini"])
    def test_no_include_key_no_crash(self, model):
        engine = _make_engine(model)
        parent_kwargs = {"model": model}

        with patch(
            "kani.engines.openai.OpenAIEngine._prepare_request",
            return_value=(parent_kwargs, _TRANSLATED, _TOOLS),
        ):
            kwargs, _, _ = engine._prepare_request([], [])

        assert "include" not in kwargs


class TestPrepareRequestReasoningModels:
    """Reasoning models must keep reasoning.encrypted_content."""

    @pytest.mark.parametrize(
        "model", ["o3", "o3-mini", "o4-mini", "gpt-5", "o1-preview"]
    )
    def test_keeps_reasoning_encrypted_content(self, model):
        engine = _make_engine(model)
        parent_kwargs = {
            "include": ["reasoning.encrypted_content", "usage"],
            "model": model,
        }

        with patch(
            "kani.engines.openai.OpenAIEngine._prepare_request",
            return_value=(parent_kwargs, _TRANSLATED, _TOOLS),
        ):
            kwargs, _, _ = engine._prepare_request([], [])

        assert "reasoning.encrypted_content" in kwargs["include"]
        assert "usage" in kwargs["include"]

    @pytest.mark.parametrize("model", ["o3", "o4-mini", "gpt-5"])
    def test_no_include_key_stays_absent(self, model):
        engine = _make_engine(model)
        parent_kwargs = {"model": model}

        with patch(
            "kani.engines.openai.OpenAIEngine._prepare_request",
            return_value=(parent_kwargs, _TRANSLATED, _TOOLS),
        ):
            kwargs, _, _ = engine._prepare_request([], [])

        assert "include" not in kwargs


# ---------------------------------------------------------------------------
# _supports_reasoning flag
# ---------------------------------------------------------------------------


class TestSupportsReasoningFlag:
    """_supports_reasoning should be set based on model prefix."""

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("gpt-4.1", False),
            ("gpt-4.1-mini", False),
            ("gpt-4.1-nano", False),
            ("o3", True),
            ("o3-mini", True),
            ("o4-mini", True),
            ("gpt-5", True),
            ("o1-preview", True),
        ],
    )
    def test_supports_reasoning(self, model, expected):
        engine = _make_engine(model)
        assert engine._supports_reasoning is expected
