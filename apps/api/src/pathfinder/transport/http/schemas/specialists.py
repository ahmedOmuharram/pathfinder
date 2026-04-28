from uuid import UUID

from pydantic import Field

from pathfinder.ai.specialists.types import SpecialistContext, SpecialistKind
from pathfinder.platform.pydantic_base import CamelModel


class SpecialistEnterRequest(CamelModel):
    arg: str = Field(default="", max_length=4000)
    model_id: str | None = None


class SpecialistEnterResponse(CamelModel):
    message_id: UUID
    kind: SpecialistKind
    model_id: str
    context: SpecialistContext


class SpecialistExitResponse(CamelModel):
    cleared: bool
    message_id: UUID | None = None


class SpecialistStateUpdate(CamelModel):
    """Mid-session swap of a non-context field on the active specialist mode."""

    model_id: str = Field(min_length=1, max_length=128)


class SpecialistStateResponse(CamelModel):
    kind: SpecialistKind
    model_id: str
