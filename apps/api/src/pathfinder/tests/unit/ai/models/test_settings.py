from pathfinder.ai.models.settings import (
    build_model_settings,
    model_provider,
    to_pydantic_ai_model_name,
)


class TestModelProvider:
    def test_openai(self) -> None:
        assert model_provider("openai:gpt-4.1-mini") == "openai"

    def test_anthropic(self) -> None:
        assert model_provider("anthropic:claude-opus-4-6") == "anthropic"

    def test_google(self) -> None:
        assert model_provider("google:gemini-2.5-pro") == "google"


class TestToPydanticAiModelName:
    """v1-only shim: bare ``openai:`` resolves to Chat Completions in
    pydantic-ai v1, so we rewrite it to ``openai-responses:``. In v2 bare
    ``openai:`` resolves to Responses by default and this rewrite MUST be
    deleted (see the function docstring)."""

    def test_openai_rewritten_to_responses(self) -> None:
        assert to_pydantic_ai_model_name("openai:gpt-4.1") == "openai-responses:gpt-4.1"

    def test_openai_preserves_model_segment(self) -> None:
        for model in ("gpt-4.1-mini", "gpt-4o-mini", "gpt-5.4", "o3", "o4-mini"):
            assert (
                to_pydantic_ai_model_name(f"openai:{model}")
                == f"openai-responses:{model}"
            )

    def test_anthropic_unchanged(self) -> None:
        assert (
            to_pydantic_ai_model_name("anthropic:claude-opus-4-6")
            == "anthropic:claude-opus-4-6"
        )

    def test_google_unchanged(self) -> None:
        assert (
            to_pydantic_ai_model_name("google:gemini-2.5-pro")
            == "google:gemini-2.5-pro"
        )

    def test_mock_unchanged(self) -> None:
        assert to_pydantic_ai_model_name("mock:lead") == "mock:lead"

    def test_idempotent_on_responses(self) -> None:
        assert (
            to_pydantic_ai_model_name("openai-responses:gpt-4.1")
            == "openai-responses:gpt-4.1"
        )

    def test_bare_string_unchanged(self) -> None:
        assert to_pydantic_ai_model_name("gpt-4.1") == "gpt-4.1"


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
