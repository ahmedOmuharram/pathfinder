"""Tier preset registry — maps (provider, tier) to per-phase model configs.

Each cloud provider defines three tiers (quality, balanced, fast) that
auto-populate the four pipeline phases with appropriate model + reasoning
effort pairings.  The frontend fetches these via ``GET /api/v1/tiers``
so it never hardcodes model assignments.
"""

from dataclasses import dataclass

from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort, TierName

__all__ = [
    "TIER_PRESETS",
    "PhaseTierConfig",
    "TierPreset",
    "get_tier_preset",
]


@dataclass(frozen=True, slots=True)
class PhaseTierConfig:
    """Model + reasoning effort for a single pipeline phase."""

    model_id: str
    reasoning_effort: ReasoningEffort


@dataclass(frozen=True, slots=True)
class TierPreset:
    """Per-phase configuration for all four pipeline phases."""

    discovery: PhaseTierConfig
    planning: PhaseTierConfig
    execution: PhaseTierConfig
    verification: PhaseTierConfig


_ANTHROPIC: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
        planning=PhaseTierConfig("anthropic/claude-opus-4-6", "high"),
        execution=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
        verification=PhaseTierConfig("anthropic/claude-opus-4-6", "high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
        planning=PhaseTierConfig("anthropic/claude-opus-4-6", "high"),
        execution=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
        verification=PhaseTierConfig("anthropic/claude-sonnet-4-6", "high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig("anthropic/claude-haiku-4-5", "low"),
        planning=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
        execution=PhaseTierConfig("anthropic/claude-haiku-4-5", "low"),
        verification=PhaseTierConfig("anthropic/claude-sonnet-4-6", "medium"),
    ),
}

_OPENAI: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig("openai/gpt-4.1", "medium"),
        planning=PhaseTierConfig("openai/gpt-5.4", "high"),
        execution=PhaseTierConfig("openai/gpt-4.1", "medium"),
        verification=PhaseTierConfig("openai/gpt-5.4", "high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig("openai/gpt-4.1", "medium"),
        planning=PhaseTierConfig("openai/gpt-5.4", "high"),
        execution=PhaseTierConfig("openai/gpt-4.1", "medium"),
        verification=PhaseTierConfig("openai/gpt-4.1", "high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig("openai/gpt-4.1-mini", "low"),
        planning=PhaseTierConfig("openai/gpt-4.1", "medium"),
        execution=PhaseTierConfig("openai/gpt-4.1-mini", "low"),
        verification=PhaseTierConfig("openai/gpt-4.1", "medium"),
    ),
}

_GOOGLE: dict[TierName, TierPreset] = {
    "quality": TierPreset(
        discovery=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
        planning=PhaseTierConfig("google/gemini-3.1-pro", "high"),
        execution=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
        verification=PhaseTierConfig("google/gemini-3.1-pro", "high"),
    ),
    "balanced": TierPreset(
        discovery=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
        planning=PhaseTierConfig("google/gemini-3.1-pro", "high"),
        execution=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
        verification=PhaseTierConfig("google/gemini-2.5-pro", "high"),
    ),
    "fast": TierPreset(
        discovery=PhaseTierConfig("google/gemini-3-flash", "low"),
        planning=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
        execution=PhaseTierConfig("google/gemini-3-flash", "low"),
        verification=PhaseTierConfig("google/gemini-2.5-pro", "medium"),
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
