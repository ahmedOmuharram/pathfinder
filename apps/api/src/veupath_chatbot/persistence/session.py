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


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependency to get database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database (create tables if needed).

    Also applies additive schema changes (indexes, columns) that
    ``create_all`` skips on existing tables.
    """
    from sqlalchemy import text

    from veupath_chatbot.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Additive migrations — safe to re-run (IF NOT EXISTS).

        # Deduplicate rows before creating the unique index.
        # Keeps the most recently updated row for each (user_id, wdk_strategy_id) pair.
        await conn.execute(
            text(
                "DELETE FROM strategies "
                "WHERE id IN ("
                "  SELECT id FROM ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "      PARTITION BY user_id, wdk_strategy_id "
                "      ORDER BY updated_at DESC"
                "    ) AS rn"
                "    FROM strategies"
                "    WHERE wdk_strategy_id IS NOT NULL"
                "  ) sub WHERE rn > 1"
                ")"
            )
        )

        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_strategies_user_wdk "
                "ON strategies (user_id, wdk_strategy_id) "
                "WHERE wdk_strategy_id IS NOT NULL"
            )
        )


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
