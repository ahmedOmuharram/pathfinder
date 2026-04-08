"""Tiers endpoint — exposes tier preset registry to the frontend."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.ai.models.tiers import TIER_PRESETS, PhaseTierConfig, TierPreset
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort, TierName


class PhaseTierResponse(BaseModel):
    """Single phase config in a tier preset."""

    model_id: str = Field(serialization_alias="modelId")
    reasoning_effort: ReasoningEffort = Field(serialization_alias="reasoningEffort")


class TierPresetResponse(BaseModel):
    """Full tier preset with all four phases."""

    discovery: PhaseTierResponse
    planning: PhaseTierResponse
    execution: PhaseTierResponse
    verification: PhaseTierResponse


class TierListResponse(BaseModel):
    """Response for GET /api/v1/tiers."""

    presets: dict[ModelProvider, dict[TierName, TierPresetResponse]]


def _to_response(preset: TierPreset) -> TierPresetResponse:
    def _phase(p: PhaseTierConfig) -> PhaseTierResponse:
        return PhaseTierResponse(model_id=p.model_id, reasoning_effort=p.reasoning_effort)

    return TierPresetResponse(
        discovery=_phase(preset.discovery),
        planning=_phase(preset.planning),
        execution=_phase(preset.execution),
        verification=_phase(preset.verification),
    )


router = APIRouter(prefix="/api/v1", tags=["tiers"])


@router.get("/tiers")
async def list_tiers() -> TierListResponse:
    """Return tier presets grouped by provider."""
    return TierListResponse(
        presets={
            provider: {
                tier_name: _to_response(preset)
                for tier_name, preset in tiers.items()
            }
            for provider, tiers in TIER_PRESETS.items()
        }
    )
