import pytest
from pydantic_ai.models import infer_model
from pydantic_ai.models.openai import OpenAIResponsesModel

from pathfinder.ai.models.settings import build_model_settings, model_provider


class TestModelProvider:
    def test_openai(self) -> None:
        assert model_provider("openai:gpt-4.1-mini") == "openai"

    def test_anthropic(self) -> None:
        assert model_provider("anthropic:claude-opus-4-6") == "anthropic"

    def test_google(self) -> None:
        assert model_provider("google:gemini-2.5-pro") == "google"


class TestOpenAIIdsResolveToResponsesApi:
    """We hand pydantic-ai our stable ``openai:`` ids unchanged. That is only
    correct because pydantic-ai v2 resolves a bare ``openai:`` prefix to the
    Responses API (v1 resolved it to Chat Completions, which is why a rewrite
    shim used to exist here). Pin the assumption so a regression is loud."""

    def test_bare_openai_prefix_is_the_responses_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        assert isinstance(infer_model("openai:gpt-5-mini"), OpenAIResponsesModel)

    def test_holds_across_the_catalog_openai_families(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        for model in ("gpt-4.1", "gpt-5", "gpt-5.4", "o3", "o4-mini"):
            assert isinstance(infer_model(f"openai:{model}"), OpenAIResponsesModel)


class TestBuildModelSettings:
    def test_anthropic_enables_caching(self) -> None:
        data = dict(build_model_settings("anthropic:claude-opus-4-6"))
        assert data["anthropic_cache_instructions"] is True
        assert data["anthropic_cache_tool_definitions"] is True
        assert data["anthropic_cache_messages"] is True

    def test_anthropic_caching_composes_with_thinking(self) -> None:
        data = dict(build_model_settings("anthropic:claude-opus-4-6", thinking="high"))
        assert data["anthropic_cache_instructions"] is True
        assert data["thinking"] == "high"

    def test_openai_thinking_applied(self) -> None:
        data = dict(build_model_settings("openai:gpt-5.4", thinking="high"))
        assert data["thinking"] == "high"

    def test_openai_caching_is_automatic_no_flags(self) -> None:
        # OpenAI prompt caching is automatic; we don't set anthropic flags on it.
        data = dict(build_model_settings("openai:gpt-4.1-mini"))
        assert "anthropic_cache_instructions" not in data

    def test_google_thinking_applied(self) -> None:
        data = dict(build_model_settings("google:gemini-2.5-pro", thinking="medium"))
        assert data["thinking"] == "medium"

    def test_thinking_none_omitted(self) -> None:
        data = dict(build_model_settings("openai:gpt-4.1-mini", thinking="none"))
        assert "thinking" not in data

    def test_thinking_default_omitted(self) -> None:
        data = dict(build_model_settings("openai:gpt-4.1-mini"))
        assert "thinking" not in data
