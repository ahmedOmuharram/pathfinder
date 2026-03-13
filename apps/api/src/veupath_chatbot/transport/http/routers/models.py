"""Models endpoint — exposes available LLM models and their status."""

from typing import TypedDict

from fastapi import APIRouter

from veupath_chatbot.ai.models.catalog import get_model_catalog
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort


class _ModelItem(TypedDict):
    id: str
    name: str
    provider: ModelProvider
    model: str
    supportsReasoning: bool
    enabled: bool
    contextSize: int
    defaultReasoningBudget: int


class ModelListResponse(TypedDict):
    models: list[_ModelItem]
    default: str
    defaultReasoningEffort: ReasoningEffort


router = APIRouter(prefix="/api/v1", tags=["models"])


def _provider_enabled(provider: ModelProvider) -> bool:
    """Check whether a model provider has its API key configured.

    :param provider: Model provider.
    :returns: True if the provider is enabled, False otherwise.
    """
    settings = get_settings()
    key_map: dict[ModelProvider, str] = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google": settings.gemini_api_key,
        "ollama": settings.ollama_base_url,
    }
    return bool(key_map.get(provider, ""))


@router.get("/models")
async def list_models() -> ModelListResponse:
    """Return available models grouped by provider.

    Models whose provider has no API key are returned with ``enabled: false``
    so the frontend can render them as disabled in the picker.
    """
    settings = get_settings()
    models: list[_ModelItem] = [
        _ModelItem(
            id=m.id,
            name=m.name,
            provider=m.provider,
            model=m.model,
            supportsReasoning=m.supports_reasoning,
            enabled=_provider_enabled(m.provider),
            contextSize=m.context_size,
            defaultReasoningBudget=m.default_reasoning_budget,
        )
        for m in get_model_catalog()
    ]
    return {
        "models": models,
        "default": settings.default_model_id,
        "defaultReasoningEffort": settings.default_reasoning_effort,
    }
