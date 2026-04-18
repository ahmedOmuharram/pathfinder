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

from pathfinder import __version__
from pathfinder.ai.capabilities.piguard import warm_up_piguard
from pathfinder.ai.conversation.checkpointer import lifespan_checkpointer
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.orchestration.observability import (
    setup_observability,
    shutdown_observability,
)
from pathfinder.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.factory import close_all_clients
from pathfinder.persistence.session import (
    close_db,
    get_engine,
    init_db,
)
from pathfinder.platform.config import get_settings
from pathfinder.platform.context import (
    request_base_url_ctx,
    request_id_ctx,
    veupathdb_auth_token_ctx,
)
from pathfinder.platform.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
)
from pathfinder.platform.logging import get_logger, setup_logging
from pathfinder.platform.readiness import get_readiness, reset_readiness
from pathfinder.platform.security import csrf_middleware, limiter
from pathfinder.services.catalog.semantic_index import warm_up_model
from pathfinder.transport.http.routers import (
    _stream_parts_schemas,
    chat,
    checkpoints,
    control_sets,
    conversations,
    dev,
    evaluation,
    experiments,
    exports,
    feedback,
    gene_sets,
    health,
    internal,
    labels,
    memories,
    models,
    sites,
    streaming_schema,
    tasks,
    tiers,
    user_data,
    veupathdb_auth,
)

logger = get_logger(__name__)


async def _warm_up_subsystems() -> None:
    """Load models and preload catalogs, marking readiness per subsystem.

    Runs after DB init. Each step is best-effort: a failure flips the
    subsystem's readiness flag and keeps ``/health/ready`` returning 503
    with the per-subsystem detail.
    """
    readiness = get_readiness()
    try:
        logger.info("[warm-up] Loading embedding model")
        warm_up_model()
        readiness.mark_ready("embedding_model")
    except (AppError, OSError, RuntimeError, ValueError) as e:
        logger.exception("[warm-up] Embedding model failed")
        readiness.mark_failed("embedding_model", str(e))

    try:
        logger.info("[warm-up] Loading PIGuard ONNX model")
        warm_up_piguard()
        readiness.mark_ready("piguard")
    except (AppError, OSError, RuntimeError) as e:
        logger.exception("[warm-up] PIGuard failed")
        readiness.mark_failed("piguard", str(e))

    try:
        logger.info("[warm-up] Preloading discovery catalogs (all sites)")
        await get_discovery_service().preload_all()
    except (AppError, OSError, RuntimeError):
        logger.exception("[warm-up] Discovery preload raised")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler."""
    settings = get_settings()
    setup_logging()
    logger.info("Starting Pathfinder API", version=__version__, env=settings.api_env)

    readiness = get_readiness()

    try:
        await init_db()
        readiness.mark_ready("database")
    except (AppError, OSError, RuntimeError) as e:
        readiness.mark_failed("database", str(e))
        raise

    # Observability + Langfuse prompt seed after DB is ready.
    setup_observability(app=app, db_engine=get_engine())
    from pathfinder.platform.langfuse.prompts import seed_prompts  # noqa: PLC0415

    seed_prompts()

    await _warm_up_subsystems()

    from pathfinder.jobs.app import procrastinate_app  # noqa: PLC0415
    from pathfinder.platform.notify_dispatcher import (  # noqa: PLC0415
        lifespan_notify_dispatcher,
    )
    async with (
        lifespan_checkpointer(settings.database_url) as checkpointer,
        lifespan_memory_store(settings.database_url) as memory_store,
        procrastinate_app.open_async(),
        lifespan_notify_dispatcher(settings.database_url) as notify_dispatcher,
    ):
        app.state.compiled_graph = build_graph(checkpointer=checkpointer)
        app.state.memory_store = memory_store
        app.state.notify_dispatcher = notify_dispatcher
        readiness.mark_ready("graph_checkpointer")

        from pathfinder.platform.tasks import spawn  # noqa: PLC0415
        from pathfinder.services.export.sweeper import (  # noqa: PLC0415
            run_sweeper_loop,
        )
        export_sweeper_task = spawn(run_sweeper_loop(), name="export-sweeper")

        yield

        logger.info("Shutting down Pathfinder API")

        if export_sweeper_task is not None:
            export_sweeper_task.cancel()

    reset_readiness()
    await close_all_clients()
    await close_db()
    shutdown_observability()
    from pathfinder.platform.langfuse.client import (  # noqa: PLC0415
        shutdown_langfuse,
    )

    shutdown_langfuse()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
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
            "X-Requested-With",
            "X-VEUPATHDB-AUTH",
            "X-VEUPATHDB-AUTHORIZATION",
        ],
    )

    # Rate limiter (slowapi)
    app.state.limiter = limiter

    # CSRF protection — require X-Requested-With on state-changing requests.
    # Registered after CORSMiddleware so OPTIONS preflight passes through.
    app.middleware("http")(csrf_middleware)

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
            "Callable[[StarletteRequest, Exception], Awaitable[Response]]",
            app_error_handler,
        ),
    )
    app.add_exception_handler(
        HTTPException,
        cast(
            "Callable[[StarletteRequest, Exception], Awaitable[Response]]",
            http_exception_handler,
        ),
    )
    app.add_exception_handler(
        RateLimitExceeded,
        cast(
            "Callable[[StarletteRequest, Exception], Awaitable[Response]]",
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
    app.include_router(tiers.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(experiments.router)
    app.include_router(control_sets.router)
    app.include_router(veupathdb_auth.router)
    app.include_router(gene_sets.router)
    app.include_router(exports.router)
    app.include_router(feedback.router)
    app.include_router(internal.router)
    app.include_router(_stream_parts_schemas.router)
    app.include_router(streaming_schema.router)
    app.include_router(user_data.router)
    app.include_router(evaluation.router)
    app.include_router(memories.router)
    app.include_router(tasks.router)
    app.include_router(checkpoints.router)
    app.include_router(labels.router)

    # Dev-only routes (e2e / local dev with mock chat provider).
    if settings.chat_provider.strip().lower() == "mock":
        app.include_router(dev.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "pathfinder.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=bool(settings.is_development),
    )
