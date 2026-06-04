"""Model-name + per-provider settings resolution.

Two concerns share one stable id (``provider:model``):

1. ``to_pydantic_ai_model_name`` — the name handed to pydantic-ai for
   inference. Everything else (catalog, pricing, persisted user prefs, the
   ``agent.model`` readback used for cost attribution) keeps the stable
   ``openai:`` id.
2. ``build_model_settings`` — the provider-correct ``ModelSettings`` (prompt
   caching + reasoning effort), composed so caching is never clobbered by the
   per-request thinking effort.
"""

from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.settings import ModelSettings

from pathfinder.platform.types import ReasoningEffort


def model_provider(model_id: str) -> str:
    """``"openai:gpt-5-mini"`` → ``"openai"``."""
    provider, sep, _ = model_id.partition(":")
    if not sep or not provider:
        msg = f"Model id {model_id!r} is not in 'provider:model' form"
        raise ValueError(msg)
    return provider


def to_pydantic_ai_model_name(model_id: str) -> str:
    """Translate our stable id to the name pydantic-ai should infer.

    REVERT IN v2: in pydantic-ai v1, bare ``openai:`` resolves to the Chat
    Completions API; v2 flips it to the Responses API by default. Until then
    we rewrite ``openai:`` → ``openai-responses:`` so OpenAI runs use the
    Responses API. When upgrading to v2, delete this rewrite (bare ``openai:``
    will already mean Responses) and pass model ids through unchanged.
    """
    provider, _, rest = model_id.partition(":")
    if provider == "openai":
        return f"openai-responses:{rest}"
    return model_id


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
