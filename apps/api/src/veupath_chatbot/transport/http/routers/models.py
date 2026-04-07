"""Models endpoint — exposes available LLM models and their status."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.ai.models.catalog import get_model_catalog
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort


class ModelCatalogEntryResponse(BaseModel):
    """A single model in the catalog — for API responses."""

    id: str
    name: str
    provider: ModelProvider
    model: str
    description: str = ""
    supports_reasoning: bool = Field(default=False, serialization_alias="supportsReasoning")
    enabled: bool = True
    context_size: int = Field(default=0, serialization_alias="contextSize")
    default_reasoning_budget: int = Field(default=0, serialization_alias="defaultReasoningBudget")
    input_price: float = Field(default=0.0, serialization_alias="inputPrice")
    cached_input_price: float = Field(default=0.0, serialization_alias="cachedInputPrice")
    output_price: float = Field(default=0.0, serialization_alias="outputPrice")



class ModelListResponse(BaseModel):
    """Response for the /models endpoint."""

    models: list[ModelCatalogEntryResponse]
    default: str
    default_reasoning_effort: ReasoningEffort = Field(
        serialization_alias="defaultReasoningEffort",
    )



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
    models: list[ModelCatalogEntryResponse] = [
        ModelCatalogEntryResponse(
            id=m.id,
            name=m.name,
            provider=m.provider,
            model=m.model,
            supports_reasoning=m.supports_reasoning,
            enabled=_provider_enabled(m.provider),
            context_size=m.context_size,
            default_reasoning_budget=m.default_reasoning_budget,
            description=m.description,
            input_price=m.input_price,
            cached_input_price=m.cached_input_price,
            output_price=m.output_price,
        )
        for m in get_model_catalog()
        if is_mock or m.provider != "mock"
    ]
    return ModelListResponse(
        models=models,
        default=settings.default_model_id,
        default_reasoning_effort=settings.default_reasoning_effort,
    )
