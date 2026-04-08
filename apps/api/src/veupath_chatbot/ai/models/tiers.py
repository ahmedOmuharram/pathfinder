"""Tier preset registry — maps (provider, tier) to per-phase model configs.

Each cloud provider defines three tiers (quality, balanced, fast) that
auto-populate the four pipeline phases with appropriate model + reasoning
effort pairings.  The frontend fetches these via ``GET /api/v1/tiers``
so it never hardcodes model assignments.
"""

from pydantic import ConfigDict

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort, TierName

__all__ = [
    "TIER_PRESETS",
    "PhaseTierConfig",
    "TierPreset",
    "get_tier_preset",
]


class PhaseTierConfig(CamelModel):
    """Model + reasoning effort for a single pipeline phase."""

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    model_id: str
    reasoning_effort: ReasoningEffort


class TierPreset(CamelModel):
    """Per-phase configuration for all four pipeline phases."""

    model_config = ConfigDict(frozen=True)

    discovery: PhaseTierConfig
    planning: PhaseTierConfig
    execution: PhaseTierConfig
    verification: PhaseTierConfig


_ANTHROPIC: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="anthropic/claude-opus-4-6", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig(model_id="anthropic/claude-haiku-4-5", reasoning_effort="low"),
        planning=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
        execution=PhaseTierConfig(model_id="anthropic/claude-haiku-4-5", reasoning_effort="low"),
        verification=PhaseTierConfig(model_id="anthropic/claude-sonnet-4-6", reasoning_effort="medium"),
    ),
}

_OPENAI: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="openai/gpt-5.4", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="openai/gpt-5.4", reasoning_effort="high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="openai/gpt-5.4", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig(model_id="openai/gpt-4.1-mini", reasoning_effort="low"),
        planning=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
        execution=PhaseTierConfig(model_id="openai/gpt-4.1-mini", reasoning_effort="low"),
        verification=PhaseTierConfig(model_id="openai/gpt-4.1", reasoning_effort="medium"),
    ),
}

_GOOGLE: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="google/gemini-3.1-pro", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="google/gemini-3.1-pro", reasoning_effort="high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
        planning=PhaseTierConfig(model_id="google/gemini-3.1-pro", reasoning_effort="high"),
        execution=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
        verification=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig(model_id="google/gemini-3-flash", reasoning_effort="low"),
        planning=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
        execution=PhaseTierConfig(model_id="google/gemini-3-flash", reasoning_effort="low"),
        verification=PhaseTierConfig(model_id="google/gemini-2.5-pro", reasoning_effort="medium"),
    ),
}


TIER_PRESETS: dict[ModelProvider, dict[TierName, TierPreset]] = {
    "anthropic": _ANTHROPIC,
    "openai": _OPENAI,
    "google": _GOOGLE,
}


def get_tier_preset(provider: ModelProvider, tier: TierName) -> TierPreset | None:
    """Look up a tier preset by provider and tier name.

    Returns ``None`` for providers without presets (e.g. Ollama).
    """
    return TIER_PRESETS.get(provider, {}).get(tier)
