"""Central model catalog — single source of truth for available LLM models.

Each entry carries enough metadata for the frontend to render a grouped
dropdown and for the backend to validate per-request overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModelProvider = Literal["openai", "anthropic", "google"]
ReasoningEffort = Literal["none", "low", "medium", "high"]

# OpenAI reasoning models (gpt-5*, o1, o3, o4) use the flat
# ``reasoning_effort`` param accepted by ``chat.completions.create()``.
_OPENAI_EFFORT_MAP: dict[ReasoningEffort, dict[str, object]] = {
    "none": {"reasoning_effort": "none"},
    "low": {"reasoning_effort": "low"},
    "medium": {},  # server default
    "high": {"reasoning_effort": "high"},
}

# Anthropic extended thinking uses ``thinking`` param with a budget.
_ANTHROPIC_EFFORT_MAP: dict[ReasoningEffort, dict[str, object]] = {
    "none": {},
    "low": {"thinking": {"type": "enabled", "budget_tokens": 1024}},
    "medium": {"thinking": {"type": "enabled", "budget_tokens": 8192}},
    "high": {"thinking": {"type": "enabled", "budget_tokens": 32768}},
}

# Google Gemini 2.5 uses ``thinking_config`` passed directly to
# ``GenerateContentConfig`` (not nested under ``generation_config``).
# A budget of 0 disables thinking; -1 = automatic (server decides).
_GOOGLE_EFFORT_MAP: dict[ReasoningEffort, dict[str, object]] = {
    "none": {"thinking_config": {"thinking_budget": 0}},
    "low": {"thinking_config": {"thinking_budget": 1024}},
    "medium": {"thinking_config": {"thinking_budget": 8192}},
    "high": {"thinking_config": {"thinking_budget": 24576}},
}

_EFFORT_MAPS: dict[ModelProvider, dict[ReasoningEffort, dict[str, object]]] = {
    "openai": _OPENAI_EFFORT_MAP,
    "anthropic": _ANTHROPIC_EFFORT_MAP,
    "google": _GOOGLE_EFFORT_MAP,
}


def build_reasoning_hyperparams(
    provider: ModelProvider,
    effort: ReasoningEffort | None,
) -> dict[str, object]:
    """Return provider-specific hyperparams that implement *effort*.

    :param provider: Model provider.
    :param effort: Reasoning effort (default: None).
    :returns: Dict of provider-specific hyperparameters, or empty dict.
    """
    if effort is None:
        return {}
    effort_map = _EFFORT_MAPS.get(provider, {})
    return dict(effort_map.get(effort, {}))


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """A single model in the catalog."""

    id: str  # e.g. "openai/gpt-5"
    name: str  # human-readable display name
    provider: ModelProvider
    model: str  # provider-native model ID (e.g. "gpt-5")
    supports_reasoning: bool = False


# Ordered list; the frontend renders them in this order, grouped by provider.
MODEL_CATALOG: tuple[ModelEntry, ...] = (
    # OpenAI
    ModelEntry(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider="openai",
        model="gpt-4o",
        supports_reasoning=False,
    ),
    ModelEntry(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        provider="openai",
        model="gpt-4o-mini",
        supports_reasoning=False,
    ),
    ModelEntry(
        id="openai/gpt-5",
        name="GPT-5",
        provider="openai",
        model="gpt-5",
        supports_reasoning=True,
    ),
    ModelEntry(
        id="openai/o3",
        name="o3",
        provider="openai",
        model="o3",
        supports_reasoning=True,
    ),
    # Anthropic
    ModelEntry(
        id="anthropic/claude-sonnet-4-0",
        name="Claude Sonnet 4",
        provider="anthropic",
        model="claude-sonnet-4-0",
        supports_reasoning=True,
    ),
    ModelEntry(
        id="anthropic/claude-opus-4",
        name="Claude Opus 4",
        provider="anthropic",
        model="claude-opus-4-0",
        supports_reasoning=True,
    ),
    # Google
    ModelEntry(
        id="google/gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider="google",
        model="gemini-2.5-pro",
        supports_reasoning=True,
    ),
    ModelEntry(
        id="google/gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider="google",
        model="gemini-2.5-flash",
        supports_reasoning=True,
    ),
)

# O(1) lookup by catalog ``id``.
_CATALOG_INDEX: dict[str, ModelEntry] = {m.id: m for m in MODEL_CATALOG}


def get_model_entry(model_id: str) -> ModelEntry | None:
    """Look up a model by catalog ID.

    :param model_id: Model identifier (e.g. ``openai/gpt-5``).
    :returns: Model entry if found, otherwise None.
    """
    return _CATALOG_INDEX.get(model_id)
