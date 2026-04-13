"""Health request/response DTOs."""

from datetime import datetime

from pydantic import BaseModel, Field

from pathfinder.platform.readiness import ReadinessState


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    """Readiness check response, including per-subsystem detail."""

    status: str
    version: str
    timestamp: datetime
    readiness: ReadinessState
    not_ready: list[str] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    """Per-provider API-key availability."""

    model_config = {"populate_by_name": True}

    openai: bool
    anthropic: bool
    google: bool
    ollama: bool


class SystemConfigResponse(BaseModel):
    """System configuration status (unauthenticated)."""

    model_config = {"populate_by_name": True}

    chat_provider: str = Field(alias="chatProvider")
    llm_configured: bool = Field(alias="llmConfigured")
    providers: ProviderStatus
