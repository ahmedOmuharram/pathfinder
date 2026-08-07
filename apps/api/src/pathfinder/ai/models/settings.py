"""Per-provider model settings resolution.

The stable ``provider:model`` id is what pydantic-ai infers from directly:
since pydantic-ai v2 a bare ``openai:`` prefix already means the Responses API,
so no name rewriting happens anywhere.

``build_model_settings`` returns the provider-correct ``ModelSettings`` (prompt
caching + reasoning effort), composed so caching is never clobbered by the
per-request thinking effort.
"""

from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.settings import ModelSettings

from pathfinder.platform.types import ReasoningEffort


def model_provider(model_id: str) -> str:
    """``"openai:gpt-5.6-luna"`` -> ``"openai"``."""
    provider, sep, _ = model_id.partition(":")
    if not sep or not provider:
        msg = f"Model id {model_id!r} is not in 'provider:model' form"
        raise ValueError(msg)
    return provider


def build_model_settings(
    model_id: str,
    *,
    thinking: ReasoningEffort | None = None,
) -> ModelSettings:
    """Provider-correct settings for ``model_id``.

    Anthropic prompt caching is opt-in, so we enable instruction, tool, and
    message caching. OpenAI and Google cache automatically, so they only carry
    the reasoning effort. ``thinking`` is the cross-provider reasoning setting
    and is applied for ``low``/``medium``/``high`` (``none`` and ``None`` omit
    it so the model uses its default).
    """
    settings: ModelSettings
    if model_provider(model_id) == "anthropic":
        settings = AnthropicModelSettings(
            anthropic_cache_instructions=True,
            anthropic_cache_tool_definitions=True,
            anthropic_cache_messages=True,
        )
    else:
        settings = ModelSettings()
    if thinking is not None and thinking != "none":
        settings["thinking"] = thinking
    return settings
