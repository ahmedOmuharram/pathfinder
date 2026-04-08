"""Tests for provider-aware model settings factory."""

from pathfinder.ai.models.settings import build_model_settings


def test_anthropic_model_gets_cache_settings() -> None:
    settings = build_model_settings("anthropic:claude-sonnet-4-6")
    assert settings.get("anthropic_cache_instructions") is True
    assert settings.get("anthropic_cache_tool_definitions") is True


def test_openai_model_gets_empty_settings() -> None:
    settings = build_model_settings("openai:gpt-5")
    assert settings == {}


def test_google_model_gets_empty_settings() -> None:
    settings = build_model_settings("google:gemini-3.1-pro")
    assert settings == {}


def test_ollama_model_gets_empty_settings() -> None:
    settings = build_model_settings("ollama:llama3")
    assert settings == {}


def test_mock_model_gets_empty_settings() -> None:
    settings = build_model_settings("mock/deterministic")
    assert settings == {}


def test_unknown_prefix_gets_empty_settings() -> None:
    settings = build_model_settings("unknown:model")
    assert settings == {}
