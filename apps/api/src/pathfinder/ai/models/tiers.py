"""Tier preset registry — maps (provider, tier) to per-phase model configs.

Each cloud provider defines tiers that auto-populate the pipeline phases with
appropriate model + reasoning effort pairings. The frontend fetches these via
``GET /api/v1/tiers`` so it never hardcodes model assignments, and
``resolve_phase_model`` applies the configured tier at runtime as the fallback
beneath an explicit per-phase user pick.

A preset names the roles it covers; the lookup below takes a role as a plain
string, so a role the preset omits falls back to that agent's compile-time
model.
"""

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import ModelProvider, ReasoningEffort, TierName
from pydantic import ConfigDict

__all__ = [
    "TIER_PRESETS",
    "PhaseTierConfig",
    "TierPreset",
    "get_tier_preset",
    "resolve_phase_tier_config",
]


class PhaseTierConfig(CamelModel):
    """Model + reasoning effort for a single pipeline phase."""

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    model_id: str
    reasoning_effort: ReasoningEffort


class TierPreset(CamelModel):
    """Per-phase configuration for every pipeline phase."""

    # The field names are the product's role names, so this model is the one
    # place that binds a role to its configuration.

    model_config = ConfigDict(frozen=True)

    lead: PhaseTierConfig
    frame: PhaseTierConfig
    execution: PhaseTierConfig
    verification: PhaseTierConfig

    def for_role(self, role: str) -> PhaseTierConfig | None:
        """The config this preset carries for ``role``, or ``None`` when the
        preset does not cover it."""
        by_role: dict[str, PhaseTierConfig] = {
            "lead": self.lead,
            "frame": self.frame,
            "execution": self.execution,
            "verification": self.verification,
        }
        return by_role.get(role)


def _uniform(model_id: str, effort: ReasoningEffort) -> TierPreset:
    """A preset that runs every phase on one model at one effort."""
    cfg = PhaseTierConfig(model_id=model_id, reasoning_effort=effort)
    return TierPreset(lead=cfg, frame=cfg, execution=cfg, verification=cfg)


def _split(
    *,
    reasoning_model: str,
    reasoning_effort: ReasoningEffort,
    execution_model: str,
    execution_effort: ReasoningEffort,
) -> TierPreset:
    """Spend on the phases that reason (lead, frame, verification) and run the
    mechanical WDK step-building phase on the cheaper model."""
    thinker = PhaseTierConfig(
        model_id=reasoning_model, reasoning_effort=reasoning_effort
    )
    worker = PhaseTierConfig(
        model_id=execution_model, reasoning_effort=execution_effort
    )
    return TierPreset(
        lead=thinker, frame=thinker, execution=worker, verification=thinker
    )


_OPENAI: dict[TierName, TierPreset] = {
    "quality": _split(
        reasoning_model="openai:gpt-5.6-sol",
        reasoning_effort="high",
        execution_model="openai:gpt-5.6-terra",
        execution_effort="medium",
    ),
    "balanced": _split(
        reasoning_model="openai:gpt-5.6-terra",
        reasoning_effort="medium",
        execution_model="openai:gpt-5.6-luna",
        execution_effort="medium",
    ),
    "default": _uniform("openai:gpt-5.6-luna", "medium"),
    "fast": _uniform("openai:gpt-5.6-luna", "low"),
}

_ANTHROPIC: dict[TierName, TierPreset] = {
    "quality": _split(
        reasoning_model="anthropic:claude-opus-5",
        reasoning_effort="high",
        execution_model="anthropic:claude-sonnet-5",
        execution_effort="medium",
    ),
    "balanced": _split(
        reasoning_model="anthropic:claude-sonnet-5",
        reasoning_effort="medium",
        execution_model="anthropic:claude-haiku-4-5",
        execution_effort="medium",
    ),
    "default": _uniform("anthropic:claude-sonnet-5", "medium"),
    "fast": _uniform("anthropic:claude-haiku-4-5", "low"),
}

_GOOGLE: dict[TierName, TierPreset] = {
    "quality": _split(
        reasoning_model="google:gemini-3.1-pro-preview",
        reasoning_effort="high",
        execution_model="google:gemini-3.6-flash",
        execution_effort="medium",
    ),
    "balanced": _split(
        reasoning_model="google:gemini-3.6-flash",
        reasoning_effort="medium",
        execution_model="google:gemini-3.5-flash-lite",
        execution_effort="medium",
    ),
    "default": _uniform("google:gemini-3.6-flash", "medium"),
    "fast": _uniform("google:gemini-3.5-flash-lite", "low"),
}

TIER_PRESETS: dict[ModelProvider, dict[TierName, TierPreset]] = {
    "openai": _OPENAI,
    "anthropic": _ANTHROPIC,
    "google": _GOOGLE,
}


def get_tier_preset(provider: ModelProvider, tier: TierName) -> TierPreset | None:
    """The preset for ``(provider, tier)``, or ``None`` when unconfigured.

    ``custom`` is deliberately unconfigured: it means the user pinned models
    per phase, so there is no preset to apply.
    """
    return TIER_PRESETS.get(provider, {}).get(tier)


def resolve_phase_tier_config(
    provider: ModelProvider,
    tier: TierName,
    role: str,
) -> PhaseTierConfig | None:
    """The configured model + effort for one phase, or ``None`` when the tier
    does not cover this provider or this role (caller falls back to the
    agent's own model)."""
    preset = get_tier_preset(provider, tier)
    if preset is None:
        return None
    return preset.for_role(role)
