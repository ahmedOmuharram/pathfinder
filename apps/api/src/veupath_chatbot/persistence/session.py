"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import InternalError

_state: dict[str, Any] = {"engine": None, "session_factory": None}


def _get_engine() -> AsyncEngine:
    """Lazily create the async engine on first access."""
    if _state["engine"] is not None:
        return _state["engine"]

    settings = get_settings()
    db_url = make_url(settings.database_url)

    if not db_url.drivername.startswith("postgresql"):
        raise InternalError(
            title="Unsupported database configuration",
            detail=(
                "SQLite is no longer supported. Set DATABASE_URL to a PostgreSQL URL, e.g. "
                "'postgresql+asyncpg://postgres:postgres@localhost:5432/pathfinder'."
            ),
        )

    engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _state["engine"] = engine
    return engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily create the session factory on first access."""
    if _state["session_factory"] is not None:
        return _state["session_factory"]

    factory = async_sessionmaker(
        _get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    _state["session_factory"] = factory
    return factory


def async_session_factory() -> AsyncSession:
    """Create a new async session from the lazily-initialized factory."""
    return _get_session_factory()()


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session."""
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _run_alembic_upgrade(connection: object) -> None:
    """Run Alembic migrations synchronously on the given connection."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    """Initialize database — runs Alembic migrations to head."""
    real_engine = _get_engine()
    async with real_engine.begin() as conn:
        await conn.run_sync(_run_alembic_upgrade)


async def close_db() -> None:
    """Close database connections."""
    engine = _state["engine"]
    if engine is not None:
        await engine.dispose()
        _state["engine"] = None
        _state["session_factory"] = None
