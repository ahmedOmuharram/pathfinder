"""Shared DTOs for per-user pipeline configuration.

Lives in ``platform`` so both the HTTP layer and the services layer can
import the same shape without crossing the services->transport boundary.
"""

from __future__ import annotations

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import (
    ModelProvider,
    PipelinePhase,
    ReasoningEffort,
    TierName,
)


class PhaseConfigPayload(CamelModel):
    model_id: str
    reasoning_effort: ReasoningEffort


class PipelineConfigPayload(CamelModel):
    """Per-phase model + effort, plus the picker's provider/tier state."""

    provider: ModelProvider
    tier: TierName
    phases: dict[PipelinePhase, PhaseConfigPayload]
