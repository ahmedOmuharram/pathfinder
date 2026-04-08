"""Schemas for workbench chat endpoints."""

from pydantic import BaseModel, Field

from pathfinder.platform.types import ModelProvider, ReasoningEffort


class WorkbenchChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=200_000)
    site_id: str = Field(alias="siteId")
    provider: ModelProvider | None = Field(default=None)
    model_id: str | None = Field(default=None, alias="model")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None, alias="reasoningEffort"
    )

    model_config = {"populate_by_name": True}


class WorkbenchChatResponse(BaseModel):
    operation_id: str = Field(alias="operationId")
    stream_id: str = Field(alias="streamId")

    model_config = {"populate_by_name": True}
