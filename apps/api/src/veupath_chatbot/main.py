"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from veupath_chatbot import __version__
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import request_id_ctx, veupathdb_auth_token_ctx
from veupath_chatbot.platform.errors import AppError, app_error_handler, http_exception_handler
from veupath_chatbot.platform.logging import get_logger, setup_logging
from veupath_chatbot.persistence.session import close_db, init_db
from veupath_chatbot.integrations.veupathdb.factory import close_all_clients

from veupath_chatbot.transport.http.routers import (
    chat,
    health,
    plans,
    results,
    sites,
    steps,
    strategies,
    veupathdb_auth,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    if settings.database_url.startswith("sqlite"):
        await init_db()

    yield

    # Shutdown
    logger.info("Shutting down Pathfinder API")
    await close_all_clients()
    await close_db()


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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request_id_ctx.set(request_id)
        veupathdb_auth_token_ctx.set(
            request.headers.get("X-VEUPATHDB-AUTH")
            or request.headers.get("X-VEUPATHDB-AUTHORIZATION")
            or request.cookies.get("Authorization")
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Routers
    app.include_router(health.router)
    app.include_router(sites.router)
    app.include_router(chat.router)
    app.include_router(plans.router)
    app.include_router(strategies.router)
    app.include_router(steps.router)
    app.include_router(results.router)
    app.include_router(veupathdb_auth.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "veupath_chatbot.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
    )

