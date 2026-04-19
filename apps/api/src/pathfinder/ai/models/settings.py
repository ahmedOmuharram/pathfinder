"""Provider settings. Model IDs are ``"provider:model"`` everywhere — no conversion."""

from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.settings import ModelSettings


def model_provider(model_id: str) -> str:
    """``"openai:gpt-5-mini"`` → ``"openai"``."""
    provider, sep, _ = model_id.partition(":")
    if not sep or not provider:
        msg = f"Model id {model_id!r} is not in 'provider:model' form"
        raise ValueError(msg)
    return provider


_ANTHROPIC_SETTINGS = AnthropicModelSettings(
    anthropic_cache_instructions=True,
    anthropic_cache_tool_definitions=True,
)

_PROVIDER_SETTINGS: dict[str, ModelSettings] = {
    "anthropic": _ANTHROPIC_SETTINGS,
}


def build_model_settings(model_id: str) -> ModelSettings:
    return _PROVIDER_SETTINGS.get(model_provider(model_id), ModelSettings())
