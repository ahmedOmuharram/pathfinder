"""Central model catalog — single source of truth for available LLM models.

Each entry carries enough metadata for the frontend to render a grouped
dropdown and for the backend to validate per-request overrides.

Cloud models are hardcoded.  Ollama (local) models are loaded from an
optional YAML file pointed to by ``OLLAMA_MODELS_CONFIG``.
"""

from dataclasses import dataclass
from functools import lru_cache

import yaml

from veupath_chatbot.platform.config import _REPO_ROOT
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort

__all__ = [
    "ModelEntry",
    "ModelProvider",
    "ReasoningEffort",
    "build_reasoning_hyperparams",
    "get_model_catalog",
    "get_model_entry",
]

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
    # Ollama models generally don't support reasoning effort params.
    "ollama": {"none": {}, "low": {}, "medium": {}, "high": {}},
    # Mock engine ignores reasoning effort.
    "mock": {"none": {}, "low": {}, "medium": {}, "high": {}},
}


def build_reasoning_hyperparams(
    provider: ModelProvider,
    effort: ReasoningEffort | None,
    *,
    budget_override: int | None = None,
) -> dict[str, object]:
    """Return provider-specific hyperparams that implement *effort*.

    :param provider: Model provider.
    :param effort: Reasoning effort (default: None).
    :param budget_override: Custom reasoning token budget (overrides effort map).
    :returns: Dict of provider-specific hyperparameters, or empty dict.
    """
    if effort is None:
        return {}
    effort_map = _EFFORT_MAPS.get(provider, {})
    params = dict(effort_map.get(effort, {}))
    if budget_override is not None and budget_override > 0:
        if provider == "anthropic":
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_override}
        elif provider == "google":
            params["thinking_config"] = {"thinking_budget": budget_override}
    return params


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """A single model in the catalog."""

    id: str  # e.g. "openai/gpt-5"
    name: str  # human-readable display name
    provider: ModelProvider
    model: str  # provider-native model ID (e.g. "gpt-5")
    description: str = ""
    supports_reasoning: bool = False
    context_size: int = 0  # known context window; 0 = use engine default
    default_reasoning_budget: int = 0  # default reasoning token budget
    input_price: float = 0.0  # USD per 1M input tokens
    cached_input_price: float = 0.0  # USD per 1M cached input tokens
    output_price: float = 0.0  # USD per 1M output tokens


# Cloud models — always present.
_CLOUD_MODELS: tuple[ModelEntry, ...] = (
    # OpenAI
    ModelEntry(
        id="openai/gpt-4.1",
        name="GPT-4.1",
        provider="openai",
        model="gpt-4.1",
        description="Default workhorse — 1M context",
        context_size=1_047_576,
        input_price=2.00,
        cached_input_price=0.50,
        output_price=8.00,
    ),
    ModelEntry(
        id="openai/gpt-4.1-mini",
        name="GPT-4.1 Mini",
        provider="openai",
        model="gpt-4.1-mini",
        description="Fast and cheap with full context",
        context_size=1_047_576,
        input_price=0.20,
        cached_input_price=0.10,
        output_price=0.80,
    ),
    ModelEntry(
        id="openai/gpt-4.1-nano",
        name="GPT-4.1 Nano",
        provider="openai",
        model="gpt-4.1-nano",
        description="Ultra-cheap for simple tasks",
        context_size=1_047_576,
        input_price=0.05,
        cached_input_price=0.025,
        output_price=0.20,
    ),
    ModelEntry(
        id="openai/gpt-5",
        name="GPT-5",
        provider="openai",
        model="gpt-5",
        description="Smartest OpenAI model",
        supports_reasoning=True,
        context_size=400_000,
        input_price=1.25,
        cached_input_price=0.125,
        output_price=10.00,
    ),
    ModelEntry(
        id="openai/gpt-5-mini",
        name="GPT-5 Mini",
        provider="openai",
        model="gpt-5-mini",
        description="Smart and budget-friendly",
        supports_reasoning=True,
        context_size=400_000,
        input_price=0.125,
        cached_input_price=0.025,
        output_price=1.00,
    ),
    ModelEntry(
        id="openai/gpt-5-nano",
        name="GPT-5 Nano",
        provider="openai",
        model="gpt-5-nano",
        description="Ultra-cheap, smaller context",
        supports_reasoning=True,
        context_size=400_000,
        input_price=0.05,
        cached_input_price=0.005,
        output_price=0.40,
    ),
    ModelEntry(
        id="openai/gpt-5.4",
        name="GPT-5.4",
        provider="openai",
        model="gpt-5.4",
        description="Latest flagship — 1.1M context",
        supports_reasoning=True,
        context_size=1_100_000,
        input_price=2.50,
        cached_input_price=0.25,
        output_price=15.00,
    ),
    ModelEntry(
        id="openai/o3",
        name="o3",
        provider="openai",
        model="o3",
        description="Reasoning-focused",
        supports_reasoning=True,
        context_size=200_000,
        input_price=2.00,
        cached_input_price=0.50,
        output_price=8.00,
    ),
    ModelEntry(
        id="openai/o4-mini",
        name="o4 Mini",
        provider="openai",
        model="o4-mini",
        description="Cheap reasoning",
        supports_reasoning=True,
        context_size=200_000,
        input_price=1.10,
        cached_input_price=0.275,
        output_price=4.40,
    ),
    # Anthropic
    ModelEntry(
        id="anthropic/claude-opus-4-6",
        name="Claude Opus 4.6",
        provider="anthropic",
        model="claude-opus-4-6",
        description="Most capable Anthropic model",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=5.00,
        cached_input_price=0.50,
        output_price=25.00,
    ),
    ModelEntry(
        id="anthropic/claude-sonnet-4-6",
        name="Claude Sonnet 4.6",
        provider="anthropic",
        model="claude-sonnet-4-6",
        description="Balanced speed and intelligence",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=3.00,
        cached_input_price=0.30,
        output_price=15.00,
    ),
    ModelEntry(
        id="anthropic/claude-haiku-4-5",
        name="Claude Haiku 4.5",
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        description="Fastest Anthropic model",
        supports_reasoning=True,
        context_size=200_000,
        default_reasoning_budget=8192,
        input_price=1.00,
        cached_input_price=0.10,
        output_price=5.00,
    ),
    # Google
    ModelEntry(
        id="google/gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider="google",
        model="gemini-2.5-pro",
        description="Best Google — deep reasoning",
        supports_reasoning=True,
        context_size=1_048_576,
        default_reasoning_budget=8192,
        input_price=1.25,
        cached_input_price=0.125,
        output_price=10.00,
    ),
    ModelEntry(
        id="google/gemini-3.1-pro",
        name="Gemini 3.1 Pro",
        provider="google",
        model="gemini-3.1-pro-preview",
        description="Latest Google flagship",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=2.00,
        cached_input_price=0.20,
        output_price=12.00,
    ),
    # Mock (deterministic E2E testing)
    ModelEntry(
        id="mock/deterministic",
        name="Mock (deterministic)",
        provider="mock",
        model="deterministic",
        description="Deterministic mock for E2E testing — no LLM calls",
        context_size=128_000,
    ),
)


def _load_ollama_models() -> tuple[ModelEntry, ...]:
    """Load Ollama model entries from the YAML config file.

    YAML format (``ollama_models.yaml``)::

        models:
          - model: llama3
            name: Llama 3
          - model: mistral
            name: Mistral 7B
          - model: qwen3
            name: Qwen 3
    """
    path = _REPO_ROOT / "ollama_models.yaml"
    if not path.is_file():
        return ()

    with path.open() as f:
        data = yaml.safe_load(f)

    if not data:
        return ()

    entries: list[ModelEntry] = []
    seen: set[str] = set()
    for item in data.get("models", []):
        model_name = item.get("model", "")
        if not model_name or model_name in seen:
            continue
        display = item.get("name", model_name)
        thinking = bool(item.get("thinking", False))
        context_size = item.get("context_size")
        entries.append(
            ModelEntry(
                id=f"ollama/{model_name}",
                name=f"{display} (local)",
                provider="ollama",
                model=model_name,
                supports_reasoning=thinking,
                context_size=int(context_size) if context_size else 0,
            )
        )
        seen.add(model_name)

    return tuple(entries)


@lru_cache
def get_model_catalog() -> tuple[ModelEntry, ...]:
    """Return the full model catalog (cloud + local)."""
    return _CLOUD_MODELS + _load_ollama_models()


def _build_index() -> dict[str, ModelEntry]:
    return {m.id: m for m in get_model_catalog()}


def get_model_entry(model_id: str) -> ModelEntry | None:
    """Look up a model by catalog ID.

    :param model_id: Model identifier (e.g. ``openai/gpt-5``).
    :returns: Model entry if found, otherwise None.
    """
    return _build_index().get(model_id)
