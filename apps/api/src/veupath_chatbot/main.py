"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from veupath_chatbot import __version__
from veupath_chatbot.integrations.vectorstore.bootstrap import ensure_rag_collections
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    close_all_qdrant_stores,
)
from veupath_chatbot.integrations.veupathdb.factory import close_all_clients
from veupath_chatbot.integrations.veupathdb.site_search import close_site_search_client
from veupath_chatbot.jobs.rag_startup import start_rag_startup_ingestion_background
from veupath_chatbot.persistence.session import close_db, init_db
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import (
    request_base_url_ctx,
    request_id_ctx,
    veupathdb_auth_token_ctx,
)
from veupath_chatbot.platform.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
)
from veupath_chatbot.platform.logging import get_logger, setup_logging
from veupath_chatbot.platform.redis import close_redis, init_redis
from veupath_chatbot.platform.security import limiter
from veupath_chatbot.transport.http.routers import (
    chat,
    control_sets,
    evaluation,
    experiments,
    exports,
    gene_sets,
    health,
    internal,
    models,
    operations,
    sites,
    strategies,
    tools,
    user_data,
    veupathdb_auth,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler."""
    settings = get_settings()

    # Startup
    setup_logging()
    logger.info(
        "Starting Pathfinder API",
        version=__version__,
        env=settings.api_env,
    )

    # Initialize database
    # For local Docker and first-run developer setups, we create tables automatically.
    # (Alembic migrations are not supported.)
    await init_db()
    await init_redis()

    # Mark any operations left "active" from a previous process as failed.
    # This handles the Docker-rebuild / crash case where the producer task
    # died without marking the operation complete.
    from veupath_chatbot.persistence.repositories.stream import StreamRepository
    from veupath_chatbot.persistence.session import async_session_factory

    async with async_session_factory() as session:
        repo = StreamRepository(session)
        orphaned = await repo.list_active_operations()
        for op in orphaned:
            await repo.fail_operation(op.operation_id)
            logger.info(
                "Marked orphaned operation as failed", operation_id=op.operation_id
            )
        if orphaned:
            await session.commit()

    try:
        await ensure_rag_collections()
    except Exception as exc:  # pragma: no cover
        # Do not fail API startup if Qdrant is unavailable or misconfigured.
        logger.warning("Failed to ensure RAG collections", error=str(exc))
    try:
        await start_rag_startup_ingestion_background()
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to start RAG startup ingestion", error=str(exc))

    yield

    # Shutdown
    logger.info("Shutting down Pathfinder API")
    await close_all_qdrant_stores()
    await close_all_clients()
    await close_site_search_client()
    await close_redis()
    await close_db()


def _wire_ai_dependencies() -> None:
    """Wire AI-layer implementations into service-layer modules.

    This is the composition root: the only place that links the AI
    layer's concrete implementations to the service layer's injected
    slots.  Keeps services free of direct ``veupath_chatbot.ai`` imports.
    """
    from veupath_chatbot.ai.agents.experiment import ExperimentAssistantAgent
    from veupath_chatbot.ai.agents.factory import (
        create_agent,
        create_engine,
        resolve_effective_model_id,
    )
    from veupath_chatbot.services.chat import orchestrator
    from veupath_chatbot.services.experiment import ai_analysis_tools, assistant

    # When chat_provider is "mock", override the default model to use MockEngine.
    # This makes the REAL agent use a deterministic engine — all downstream
    # systems (WDK, DB, Redis, gene sets, auto-build) still run real.
    settings = get_settings()
    if settings.chat_provider.strip().lower() == "mock":
        settings.default_model_id = "mock/deterministic"

    orchestrator.configure(
        create_agent_fn=create_agent,
        resolve_model_id_fn=resolve_effective_model_id,
    )
    assistant.configure(
        create_engine_fn=create_engine,
        experiment_agent_cls=ExperimentAssistantAgent,
    )
    ai_analysis_tools.configure(
        experiment_agent_cls=ExperimentAssistantAgent,
    )

    # Workbench chat orchestrator
    from uuid import UUID

    from kani import ChatMessage

    from veupath_chatbot.ai.agents.workbench import WorkbenchAgent
    from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort
    from veupath_chatbot.services import workbench_chat

    def _create_workbench_agent(
        site_id: str,
        experiment_id: str,
        user_id: UUID | None = None,
        system_prompt: str = "",
        chat_history: list[ChatMessage] | None = None,
        provider_override: ModelProvider | None = None,
        model_override: str | None = None,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> WorkbenchAgent:
        engine = create_engine(
            provider_override=provider_override,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
        )
        return WorkbenchAgent(
            engine=engine,
            site_id=site_id,
            experiment_id=experiment_id,
            user_id=user_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )

    workbench_chat.orchestrator.configure(
        create_workbench_agent_fn=_create_workbench_agent,
        resolve_model_id_fn=resolve_effective_model_id,
    )


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    _wire_ai_dependencies()
    settings = get_settings()

    app = FastAPI(
        title="Pathfinder API",
        description="VEuPathDB Strategy Builder Chatbot API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-VEUPATHDB-AUTH",
            "X-VEUPATHDB-AUTHORIZATION",
        ],
    )

    # Rate limiter (slowapi)
    app.state.limiter = limiter

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(
        request: StarletteRequest,
        call_next: Callable[[StarletteRequest], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request_id_ctx.set(request_id)
        veupathdb_auth_token_ctx.set(
            request.headers.get("X-VEUPATHDB-AUTH")
            or request.headers.get("X-VEUPATHDB-AUTHORIZATION")
            or request.cookies.get("Authorization")
        )
        # Capture the frontend origin for constructing full download URLs.
        origin = (
            request.headers.get("Origin")
            or request.headers.get("Referer", "").rstrip("/").rsplit("/api/", 1)[0]
            or (settings.cors_origins[0] if settings.cors_origins else None)
        )
        request_base_url_ctx.set(origin)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Exception handlers
    app.add_exception_handler(
        AppError,
        cast(
            Callable[[StarletteRequest, Exception], Awaitable[Response]],
            app_error_handler,
        ),
    )
    app.add_exception_handler(
        HTTPException,
        cast(
            Callable[[StarletteRequest, Exception], Awaitable[Response]],
            http_exception_handler,
        ),
    )
    app.add_exception_handler(
        RateLimitExceeded,
        cast(
            Callable[[StarletteRequest, Exception], Awaitable[Response]],
            lambda request, exc: Response(
                content=str(exc.detail),
                status_code=429,
                headers={"Retry-After": "60"},
            ),
        ),
    )

    # Routers
    app.include_router(health.router)
    app.include_router(sites.router)
    app.include_router(models.router)
    app.include_router(tools.router)
    app.include_router(chat.router)
    app.include_router(strategies.router)
    app.include_router(experiments.router)
    app.include_router(control_sets.router)
    app.include_router(veupathdb_auth.router)
    app.include_router(operations.router)
    app.include_router(gene_sets.router)
    app.include_router(exports.router)
    app.include_router(internal.router)
    app.include_router(user_data.router)
    app.include_router(evaluation.router)

    # Dev-only routes (e2e / local dev with mock chat provider).
    if settings.chat_provider.strip().lower() == "mock":
        from veupath_chatbot.transport.http.routers import dev

        app.include_router(dev.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "veupath_chatbot.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=bool(settings.is_development),
    )
