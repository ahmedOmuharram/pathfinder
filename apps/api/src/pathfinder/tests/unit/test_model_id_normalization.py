"""Tests for model ID normalization in phase_runner.resolve_model()."""

import os
from unittest.mock import patch

from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel

from pathfinder.services.chat.streaming.phase_runner import resolve_model

_FAKE_KEYS = {
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "OPENAI_API_KEY": "test-openai-key",
    "GEMINI_API_KEY": "test-gemini-key",
    "GOOGLE_API_KEY": "test-google-key",
}


def test_slash_format_normalized_to_colon() -> None:
    """Catalog slash IDs (openai/gpt-4.1) become colon IDs for pydantic-ai."""
    with patch.dict(os.environ, _FAKE_KEYS):
        result = resolve_model("openai/gpt-4.1")
    assert isinstance(result, FallbackModel)
    primary = result.models[0]
    assert primary.model_id == "openai:gpt-4.1"


def test_colon_format_passes_through() -> None:
    """Already-colon IDs pass through unchanged."""
    with patch.dict(os.environ, _FAKE_KEYS):
        result = resolve_model("anthropic:claude-sonnet-4-6")
    assert isinstance(result, FallbackModel)


def test_mock_format_returns_function_model() -> None:
    """Mock IDs bypass normalization entirely."""
    result = resolve_model("mock/deterministic")
    assert isinstance(result, FunctionModel)


def test_fallback_chain_populated_for_known_provider() -> None:
    """Known providers get cross-provider fallback chains."""
    with patch.dict(os.environ, _FAKE_KEYS):
        result = resolve_model("anthropic/claude-sonnet-4-6")
    assert isinstance(result, FallbackModel)
    assert len(result.models) > 1
