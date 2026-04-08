"""Provider-aware model settings factory.

Single source of truth for provider-specific ``ModelSettings``.  Detects
the provider from the model ID prefix and returns the appropriate
settings with provider-specific optimizations (Anthropic caching, etc.).

Reasoning (thinking) is NOT handled here -- it is a cross-provider
concern handled by the ``Thinking`` capability on each agent.
"""

from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.settings import ModelSettings


def _detect_provider(model_id: str) -> str:
    """Extract the provider prefix from a pydantic-ai model ID.

    ``"anthropic:claude-sonnet-4-6"``  ->  ``"anthropic"``
    ``"mock/deterministic"``           ->  ``"mock"``
    ``"openai:gpt-5"``                ->  ``"openai"``
    """
    if ":" in model_id:
        return model_id.split(":", 1)[0]
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return model_id


# Anthropic benefits from instruction + tool definition caching (90% cost
# savings on cache reads).  Other providers either don't support it or
# handle it automatically.
_ANTHROPIC_SETTINGS = AnthropicModelSettings(
    anthropic_cache_instructions=True,
    anthropic_cache_tool_definitions=True,
)

_PROVIDER_SETTINGS: dict[str, ModelSettings] = {
    "anthropic": _ANTHROPIC_SETTINGS,
}


def build_model_settings(model_id: str) -> ModelSettings:
    """Return provider-specific model settings for *model_id*.

    Returns an empty ``ModelSettings`` when the provider needs no special
    settings.  The caller can always pass the result to
    ``agent.override(model_settings=...)``.
    """
    provider = _detect_provider(model_id)
    return _PROVIDER_SETTINGS.get(provider, ModelSettings())
