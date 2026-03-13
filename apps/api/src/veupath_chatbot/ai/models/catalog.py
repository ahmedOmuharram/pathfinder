"""Central model catalog — single source of truth for available LLM models.

Each entry carries enough metadata for the frontend to render a grouped
dropdown and for the backend to validate per-request overrides.

Cloud models are hardcoded.  Ollama (local) models are loaded from an
optional YAML file pointed to by ``OLLAMA_MODELS_CONFIG``.
"""

from dataclasses import dataclass
from functools import lru_cache

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
    supports_reasoning: bool = False
    context_size: int = 0  # known context window; 0 = use engine default
    default_reasoning_budget: int = (
        0  # default reasoning token budget at "medium" effort
    )


# Cloud models — always present.
_CLOUD_MODELS: tuple[ModelEntry, ...] = (
    # OpenAI
    ModelEntry(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider="openai",
        model="gpt-4o",
        context_size=128_000,
    ),
    ModelEntry(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        provider="openai",
        model="gpt-4o-mini",
        context_size=128_000,
    ),
    ModelEntry(
        id="openai/gpt-5",
        name="GPT-5",
        provider="openai",
        model="gpt-5",
        supports_reasoning=True,
        context_size=400_000,
    ),
    ModelEntry(
        id="openai/o3",
        name="o3",
        provider="openai",
        model="o3",
        supports_reasoning=True,
        context_size=200_000,
    ),
    # Anthropic
    ModelEntry(
        id="anthropic/claude-sonnet-4-0",
        name="Claude Sonnet 4",
        provider="anthropic",
        model="claude-sonnet-4-0",
        supports_reasoning=True,
        context_size=200_000,
        default_reasoning_budget=8192,
    ),
    ModelEntry(
        id="anthropic/claude-opus-4",
        name="Claude Opus 4",
        provider="anthropic",
        model="claude-opus-4-0",
        supports_reasoning=True,
        context_size=200_000,
        default_reasoning_budget=8192,
    ),
    # Google
    ModelEntry(
        id="google/gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider="google",
        model="gemini-2.5-pro",
        supports_reasoning=True,
        context_size=1_048_576,
        default_reasoning_budget=8192,
    ),
    ModelEntry(
        id="google/gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider="google",
        model="gemini-2.5-flash",
        supports_reasoning=True,
        context_size=1_048_576,
        default_reasoning_budget=8192,
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
    from veupath_chatbot.platform.config import _REPO_ROOT

    path = _REPO_ROOT / "ollama_models.yaml"
    if not path.is_file():
        return ()

    import yaml

    with path.open() as f:
        data = yaml.safe_load(f)

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


# Backwards-compat alias.
MODEL_CATALOG = _CLOUD_MODELS


def _build_index() -> dict[str, ModelEntry]:
    return {m.id: m for m in get_model_catalog()}


def get_model_entry(model_id: str) -> ModelEntry | None:
    """Look up a model by catalog ID.

    :param model_id: Model identifier (e.g. ``openai/gpt-5``).
    :returns: Model entry if found, otherwise None.
    """
    return _build_index().get(model_id)
