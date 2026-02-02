"""SQLAlchemy async engine and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from veupath_chatbot.platform.config import get_settings

settings = get_settings()
db_url = make_url(settings.database_url)
is_sqlite = db_url.drivername.startswith("sqlite")

engine_options: dict[str, object] = {
    "echo": settings.is_development,
    "pool_pre_ping": True,
}
if is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine_options["poolclass"] = NullPool
else:
    engine_options["pool_size"] = 5
    engine_options["max_overflow"] = 10

engine = create_async_engine(settings.database_url, **engine_options)

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


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session."""
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

    if is_sqlite and db_url.database and db_url.database != ":memory:":
        db_path = Path(db_url.database)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        if is_sqlite:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await conn.exec_driver_sql("PRAGMA busy_timeout=5000")
        await conn.run_sync(Base.metadata.create_all)
        if is_sqlite:
            await _ensure_sqlite_schema(conn)


async def _ensure_sqlite_schema(conn) -> None:
    """Best-effort migrations for sqlite development DBs."""
    strategy_info = await conn.exec_driver_sql("PRAGMA table_info(strategies)")
    strategy_columns = {row[1] for row in strategy_info.fetchall()}
    if "title" not in strategy_columns:
        await conn.exec_driver_sql(
            "ALTER TABLE strategies ADD COLUMN title VARCHAR(255)"
        )
    if "messages" not in strategy_columns:
        await conn.exec_driver_sql(
            "ALTER TABLE strategies ADD COLUMN messages JSON"
        )
    if "thinking" not in strategy_columns:
        await conn.exec_driver_sql(
            "ALTER TABLE strategies ADD COLUMN thinking JSON"
        )


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()

