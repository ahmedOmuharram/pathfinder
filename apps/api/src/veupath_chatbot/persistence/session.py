"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import InternalError

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Lazily create the async engine on first access."""
    global _engine
    if _engine is not None:
        return _engine

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

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily create the session factory on first access."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    _session_factory = async_sessionmaker(
        _get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _session_factory


def get_engine() -> AsyncEngine:
    """Get the lazily-initialized async engine."""
    return _get_engine()


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


async def init_db() -> None:
    """Initialize database — creates all tables from ORM models."""
    from veupath_chatbot.persistence.models import Base

    real_engine = _get_engine()
    async with real_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
