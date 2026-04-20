"""Health request/response DTOs."""

from datetime import datetime

from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.readiness import ReadinessState


class HealthResponse(CamelModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class ReadinessResponse(CamelModel):
    """Readiness check response, including per-subsystem detail."""

    status: str
    version: str
    timestamp: datetime
    readiness: ReadinessState
    not_ready: list[str] = Field(default_factory=list)


class ProviderStatus(CamelModel):
    """Per-provider API-key availability."""


    openai: bool
    anthropic: bool
    google: bool
    ollama: bool


class SystemConfigResponse(CamelModel):
    """System configuration status (unauthenticated)."""


    chat_provider: str
    llm_configured: bool
    providers: ProviderStatus
