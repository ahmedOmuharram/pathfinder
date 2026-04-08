"""Models endpoint — exposes available LLM models and their status."""

from fastapi import APIRouter
from pydantic import ConfigDict

from veupath_chatbot.ai.models.catalog import ModelEntry, get_model_catalog
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import ModelProvider, TierName


class ModelCatalogEntryResponse(ModelEntry):
    """API response model — adds ``enabled`` status per provider configuration."""

    model_config = ConfigDict(frozen=False)

    enabled: bool = True


class ModelListResponse(CamelModel):
    """Response for the /models endpoint."""

    models: list[ModelCatalogEntryResponse]
    default_provider: ModelProvider
    default_tier: TierName


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
    is_mock = settings.chat_provider.strip().lower() == "mock"
    models = [
        ModelCatalogEntryResponse(
            **m.model_dump(),
            enabled=_provider_enabled(m.provider),
        )
        for m in get_model_catalog()
        if is_mock or m.provider != "mock"
    ]
    return ModelListResponse(
        models=models,
        default_provider=settings.default_provider,
        default_tier=settings.default_tier,
    )
