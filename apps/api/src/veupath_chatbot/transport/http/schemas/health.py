"""Health request/response DTOs."""

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class ProviderStatus(BaseModel):
    """Per-provider API-key availability."""

    openai: bool
    anthropic: bool
    google: bool
    ollama: bool


class SystemConfigResponse(BaseModel):
    """System configuration status (unauthenticated)."""

    chat_provider: str
    llm_configured: bool
    providers: ProviderStatus
