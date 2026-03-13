"""Health check endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from veupath_chatbot import __version__
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.health import check_database, check_qdrant
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.transport.http.schemas import HealthResponse, SystemConfigResponse
from veupath_chatbot.transport.http.schemas.health import ProviderStatus

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness check - is the service running?"""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(UTC),
    )


@router.get("/health/config", response_model=SystemConfigResponse)
async def system_config() -> SystemConfigResponse:
    """Report whether the system has LLM provider keys configured.

    This is unauthenticated so the frontend can show a setup-required
    screen before asking users to log in.
    """
    settings = get_settings()
    is_mock = settings.chat_provider.strip().lower() == "mock"
    providers = ProviderStatus(
        openai=bool(settings.openai_api_key),
        anthropic=bool(settings.anthropic_api_key),
        google=bool(settings.gemini_api_key),
    )
    return SystemConfigResponse(
        chat_provider=settings.chat_provider,
        llm_configured=is_mock
        or providers.openai
        or providers.anthropic
        or providers.google,
        providers=providers,
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse | JSONResponse:
    """Readiness check - is the service ready to accept requests?

    Checks database connectivity and Qdrant availability (if RAG is enabled).
    Returns 503 if any dependency is unreachable.
    """
    settings = get_settings()
    failures: list[str] = []

    try:
        async with async_session_factory() as session:
            await check_database(session)
    except Exception as e:
        logger.error("Readiness check: database unreachable", error=str(e))
        failures.append("database")

    if settings.rag_enabled:
        try:
            await check_qdrant()
        except Exception as e:
            logger.error("Readiness check: Qdrant unreachable", error=str(e))
            failures.append("qdrant")

    if failures:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "version": __version__,
                "timestamp": datetime.now(UTC).isoformat(),
                "failed_checks": failures,
            },
        )

    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(UTC),
    )
