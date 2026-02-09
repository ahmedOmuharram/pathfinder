"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import InternalError

settings = get_settings()
db_url = make_url(settings.database_url)

# SQLite was removed entirely. Enforce Postgres so dev/test/prod behavior matches.
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

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database (create tables if needed)."""
    from veupath_chatbot.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
