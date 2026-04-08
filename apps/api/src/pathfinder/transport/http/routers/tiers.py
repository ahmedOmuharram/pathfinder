"""Tiers endpoint — exposes tier preset registry to the frontend."""

from fastapi import APIRouter

from pathfinder.ai.models.tiers import TIER_PRESETS, TierPreset
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import ModelProvider, TierName


class TierListResponse(CamelModel):
    """Response for GET /api/v1/tiers."""

    presets: dict[ModelProvider, dict[TierName, TierPreset]]


router = APIRouter(prefix="/api/v1", tags=["tiers"])


@router.get("/tiers")
async def list_tiers() -> TierListResponse:
    """Return tier presets grouped by provider."""
    return TierListResponse(presets=TIER_PRESETS)
