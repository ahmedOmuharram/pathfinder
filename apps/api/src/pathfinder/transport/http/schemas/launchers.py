from uuid import UUID

from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel


class OptimizeLaunchRequest(CamelModel):
    step_id: int
    param_keys: list[str] = Field(min_length=1, max_length=20)
    criterion: str = Field(min_length=1, max_length=2000)
    budget: int = Field(default=20, ge=1, le=100)
    model_id: str | None = None


class OptimizeLaunchResponse(CamelModel):
    task_id: UUID
    message_id: UUID
