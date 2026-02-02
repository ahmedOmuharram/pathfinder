"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from veupath_chatbot import __version__
from veupath_chatbot.transport.http.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness check - is the service running?"""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """Readiness check - is the service ready to accept requests?

    In production, this should check database and cache connectivity.
    """
    # TODO: Add actual health checks for DB, Redis, etc.
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(timezone.utc),
    )

