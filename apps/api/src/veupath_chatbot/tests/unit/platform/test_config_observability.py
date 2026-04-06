"""Tests for observability-related settings fields."""

from veupath_chatbot.platform.config import Settings


def test_signoz_endpoint_defaults_to_none():
    s = Settings(api_secret_key="x" * 32)
    assert s.signoz_otel_endpoint is None


def test_signoz_endpoint_from_env(monkeypatch):
    monkeypatch.setenv("SIGNOZ_OTEL_ENDPOINT", "http://collector:4317")
    s = Settings(api_secret_key="x" * 32)
    assert s.signoz_otel_endpoint == "http://collector:4317"


def test_langfuse_settings_defaults():
    s = Settings(api_secret_key="x" * 32)
    assert s.langfuse_secret_key == ""
    assert s.langfuse_public_key == ""
    assert s.langfuse_host == "http://localhost:3100"


def test_langfuse_settings_from_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse:3000")
    s = Settings(api_secret_key="x" * 32)
    assert s.langfuse_secret_key == "sk-lf-test"
    assert s.langfuse_public_key == "pk-lf-test"
    assert s.langfuse_host == "http://langfuse:3000"
