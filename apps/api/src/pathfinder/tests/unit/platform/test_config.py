import pytest

from pathfinder.platform.config import Settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "api_env": "test",
        "api_secret_key": "pathfinder-test-secret-key-1234567890",
        "database_url": "postgresql+asyncpg://postgres:postgres@db:5432/pathfinder",
        "redis_url": "redis://redis:6379/0",
        "chat_provider": "mock",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "gemini_api_key": "",
        "ollama_base_url": "",
        "langfuse_host": "",
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_mock_provider_is_rejected_outside_development() -> None:
    with pytest.raises(
        ValueError,
        match="PATHFINDER_CHAT_PROVIDER=mock is only allowed",
    ):
        make_settings(api_env="production", chat_provider="mock")


def test_non_mock_mode_requires_real_model_backend() -> None:
    with pytest.raises(ValueError, match="configured model backend"):
        make_settings(chat_provider="default")


def test_ollama_configuration_counts_as_model_backend() -> None:
    settings = make_settings(
        chat_provider="default",
        ollama_base_url="http://ollama:11434/v1",
    )
    assert settings.has_llm_configuration is True


def test_partial_langfuse_configuration_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY "
            "must be set together"
        ),
    ):
        make_settings(langfuse_host="http://langfuse:3000")


def test_secret_must_be_long_enough() -> None:
    with pytest.raises(
        ValueError,
        match="API_SECRET_KEY must be at least 32 characters",
    ):
        make_settings(api_secret_key="too-short")


def test_empty_env_value_is_ignored_for_complex_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "")

    settings = Settings(
        _env_file=None,
        api_env="test",
        api_secret_key="pathfinder-test-secret-key-1234567890",
        database_url="postgresql+asyncpg://postgres:postgres@db:5432/pathfinder",
        redis_url="redis://redis:6379/0",
        chat_provider="mock",
        openai_api_key="",
        anthropic_api_key="",
        gemini_api_key="",
        ollama_base_url="",
        langfuse_host="",
        langfuse_public_key="",
        langfuse_secret_key="",
    )

    assert settings.cors_origins == ["http://localhost:3000"]


def test_chat_provider_must_be_explicit() -> None:
    with pytest.raises(
        ValueError,
        match="PATHFINDER_CHAT_PROVIDER must be set explicitly",
    ):
        make_settings(chat_provider="")
