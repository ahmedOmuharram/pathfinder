"""Central model catalog — single source of truth for available LLM models.

Each entry carries enough metadata for the frontend to render a grouped
dropdown and for the backend to validate per-request overrides.

Cloud models are hardcoded.  Ollama (local) models are loaded from an
optional YAML file pointed to by ``OLLAMA_MODELS_CONFIG``.
"""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from pathfinder.platform.config import _REPO_ROOT
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import ModelProvider

__all__ = [
    "ModelEntry",
    "ModelProvider",
    "get_model_catalog",
    "get_model_entry",
]


class ModelEntry(CamelModel):
    """Catalog entry.

    Construct via :meth:`entry` — it splits the ``"provider:model"`` id
    into the required ``provider`` and ``model_name`` wire fields so the
    frontend treats them as non-optional.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    supports_reasoning: bool = False
    context_size: int = 0
    default_reasoning_budget: int = 0
    input_price: float = 0.0
    cached_input_price: float = 0.0
    output_price: float = 0.0
    is_provider_smallest: bool = False
    provider: ModelProvider
    model_name: str

    @model_validator(mode="before")
    @classmethod
    def _derive_from_id(cls, data: Any) -> Any:
        if (
            isinstance(data, dict)
            and isinstance(data.get("id"), str)
            and ":" in data["id"]
        ):
            provider, model_name = data["id"].split(":", 1)
            data.setdefault("provider", provider)
            data.setdefault("model_name", model_name)
        return data

    @classmethod
    def entry(cls, **kwargs: Any) -> "ModelEntry":
        """Build a ModelEntry from kwargs, routing through the validator."""
        return cls.model_validate(kwargs)


# Cloud models — always present.
_CLOUD_MODELS: tuple[ModelEntry, ...] = (
    # OpenAI
    ModelEntry.entry(
        id="openai:gpt-4.1",
        name="GPT-4.1",
        description="Default workhorse — 1M context",
        context_size=1_047_576,
        input_price=2.00,
        cached_input_price=0.50,
        output_price=8.00,
    ),
    ModelEntry.entry(
        id="openai:gpt-4.1-mini",
        name="GPT-4.1 Mini",
        description="Fast and cheap with full context",
        context_size=1_047_576,
        input_price=0.20,
        cached_input_price=0.10,
        output_price=0.80,
    ),
    ModelEntry.entry(
        id="openai:gpt-4.1-nano",
        name="GPT-4.1 Nano",
        description="Ultra-cheap for simple tasks",
        context_size=1_047_576,
        input_price=0.05,
        cached_input_price=0.025,
        output_price=0.20,
        is_provider_smallest=True,
    ),
    ModelEntry.entry(
        id="openai:gpt-5",
        name="GPT-5",
        description="Smartest OpenAI model",
        supports_reasoning=True,
        context_size=400_000,
        input_price=1.25,
        cached_input_price=0.125,
        output_price=10.00,
    ),
    ModelEntry.entry(
        id="openai:gpt-5-mini",
        name="GPT-5 Mini",
        description="Smart and budget-friendly",
        supports_reasoning=True,
        context_size=400_000,
        input_price=0.125,
        cached_input_price=0.025,
        output_price=1.00,
    ),
    ModelEntry.entry(
        id="openai:gpt-5-nano",
        name="GPT-5 Nano",
        description="Ultra-cheap, smaller context",
        supports_reasoning=True,
        context_size=400_000,
        input_price=0.05,
        cached_input_price=0.005,
        output_price=0.40,
    ),
    ModelEntry.entry(
        id="openai:gpt-5.4",
        name="GPT-5.4",
        description="Latest flagship — 1.1M context",
        supports_reasoning=True,
        context_size=1_100_000,
        input_price=2.50,
        cached_input_price=0.25,
        output_price=15.00,
    ),
    ModelEntry.entry(
        id="openai:gpt-5.4-mini",
        name="GPT-5.4 Mini",
        description="Fast and cheap with flagship context",
        supports_reasoning=True,
        context_size=1_100_000,
        input_price=0.25,
        cached_input_price=0.025,
        output_price=2.00,
    ),
    ModelEntry.entry(
        id="openai:gpt-5.4-nano",
        name="GPT-5.4 Nano",
        description="Ultra-cheap with flagship context",
        supports_reasoning=True,
        context_size=1_100_000,
        input_price=0.05,
        cached_input_price=0.005,
        output_price=0.40,
    ),
    ModelEntry.entry(
        id="openai:o3",
        name="o3",
        description="Reasoning-focused",
        supports_reasoning=True,
        context_size=200_000,
        input_price=2.00,
        cached_input_price=0.50,
        output_price=8.00,
    ),
    ModelEntry.entry(
        id="openai:o4-mini",
        name="o4 Mini",
        description="Cheap reasoning",
        supports_reasoning=True,
        context_size=200_000,
        input_price=1.10,
        cached_input_price=0.275,
        output_price=4.40,
    ),
    # Anthropic
    ModelEntry.entry(
        id="anthropic:claude-opus-4-7",
        name="Claude Opus 4.7",
        description="Most capable Anthropic model",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=5.00,
        cached_input_price=0.50,
        output_price=25.00,
    ),
    ModelEntry.entry(
        id="anthropic:claude-opus-4-6",
        name="Claude Opus 4.6",
        description="Prior-generation Opus",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=5.00,
        cached_input_price=0.50,
        output_price=25.00,
    ),
    ModelEntry.entry(
        id="anthropic:claude-sonnet-4-6",
        name="Claude Sonnet 4.6",
        description="Balanced speed and intelligence",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=3.00,
        cached_input_price=0.30,
        output_price=15.00,
    ),
    ModelEntry.entry(
        id="anthropic:claude-haiku-4-5",
        name="Claude Haiku 4.5",
        description="Fastest Anthropic model",
        supports_reasoning=True,
        context_size=200_000,
        default_reasoning_budget=8192,
        input_price=1.00,
        cached_input_price=0.10,
        output_price=5.00,
        is_provider_smallest=True,
    ),
    # Google
    ModelEntry.entry(
        id="google:gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        description="Best Google — deep reasoning",
        supports_reasoning=True,
        context_size=1_048_576,
        default_reasoning_budget=8192,
        input_price=1.25,
        cached_input_price=0.125,
        output_price=10.00,
    ),
    ModelEntry.entry(
        id="google:gemini-3.1-pro",
        name="Gemini 3.1 Pro",
        description="Latest Google flagship",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=2.00,
        cached_input_price=0.20,
        output_price=12.00,
    ),
    ModelEntry.entry(
        id="google:gemini-3-flash",
        name="Gemini 3 Flash",
        description="Fast and capable",
        supports_reasoning=True,
        context_size=1_000_000,
        default_reasoning_budget=8192,
        input_price=0.50,
        cached_input_price=0.05,
        output_price=3.00,
    ),
    ModelEntry.entry(
        id="google:gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        description="Budget reasoning model",
        supports_reasoning=True,
        context_size=1_048_576,
        default_reasoning_budget=8192,
        input_price=0.10,
        cached_input_price=0.01,
        output_price=0.40,
        is_provider_smallest=True,
    ),
    # Mock (deterministic E2E testing)
    ModelEntry.entry(
        id="mock:deterministic",
        name="Mock (deterministic)",
        description="Deterministic mock for E2E testing — no LLM calls",
        context_size=128_000,
        is_provider_smallest=True,
    ),
)


class _OllamaYamlItem(BaseModel):
    """A single entry in ``ollama_models.yaml``."""

    model_config = ConfigDict(extra="ignore")

    model: str = ""
    name: str = ""
    thinking: bool = False
    context_size: int = 0


class _OllamaYamlConfig(BaseModel):
    """Top-level structure of ``ollama_models.yaml``."""

    model_config = ConfigDict(extra="ignore")

    models: list[_OllamaYamlItem] = []


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

    config = _OllamaYamlConfig.model_validate(data)
    entries: list[ModelEntry] = []
    seen: set[str] = set()
    for item in config.models:
        if not item.model or item.model in seen:
            continue
        display = item.name or item.model
        entries.append(
            ModelEntry.entry(
                id=f"ollama:{item.model}",
                name=f"{display} (local)",
                supports_reasoning=item.thinking,
                context_size=item.context_size,
                is_provider_smallest=not entries,
            )
        )
        seen.add(item.model)

    return tuple(entries)


@lru_cache
def get_model_catalog() -> tuple[ModelEntry, ...]:
    """Return the full model catalog (cloud + local)."""
    return _CLOUD_MODELS + _load_ollama_models()


@lru_cache
def _build_index() -> dict[str, ModelEntry]:
    return {m.id: m for m in get_model_catalog()}


def get_model_entry(model_id: str) -> ModelEntry | None:
    """Look up a model by catalog ID.

    :param model_id: Model identifier (e.g. ``openai:gpt-4.1-mini``).
    :returns: Model entry if found, otherwise None.
    """
    return _build_index().get(model_id)


def get_smallest_model(provider: ModelProvider) -> ModelEntry:
    """Return the provider's smallest (cheapest, fastest) model.

    Used for utility tasks such as conversation-title generation where
    quality matters less than latency and cost. Exactly one entry per
    provider must be marked ``is_provider_smallest=True``.

    :raises LookupError: if no smallest entry is marked for the provider.
    """
    for entry in get_model_catalog():
        if entry.provider == provider and entry.is_provider_smallest:
            return entry
    msg = f"No is_provider_smallest=True entry for provider={provider!r}"
    raise LookupError(msg)
