"""Models endpoint — exposes available LLM models and their status."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.ai.model_catalog import MODEL_CATALOG, ModelProvider
from veupath_chatbot.platform.config import get_settings

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
    }
    return bool(key_map.get(provider, ""))


@router.get("/models")
async def list_models() -> dict[str, object]:
    """Return available models grouped by provider.

    Models whose provider has no API key are returned with ``enabled: false``
    so the frontend can render them as disabled in the picker.
    """
    settings = get_settings()
    models = [
        {
            "id": m.id,
            "name": m.name,
            "provider": m.provider,
            "model": m.model,
            "supportsReasoning": m.supports_reasoning,
            "enabled": _provider_enabled(m.provider),
        }
        for m in MODEL_CATALOG
    ]
    return {
        "models": models,
        "default": settings.default_model_id,
        "defaultReasoningEffort": settings.default_reasoning_effort,
    }
