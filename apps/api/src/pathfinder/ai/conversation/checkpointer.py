from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url

from pathfinder.ai.conversation.serde import build_checkpoint_serde


def to_psycopg_url(database_url: str) -> str:
    """Strip ``+asyncpg`` from a SQLAlchemy URL for psycopg.

    The app uses asyncpg via SQLAlchemy (``postgresql+asyncpg://...``); the
    LangGraph checkpoint store uses psycopg directly. Both speak Postgres,
    but psycopg cannot parse the SQLAlchemy ``+asyncpg`` driver suffix.
    """
    url = make_url(database_url)
    if url.drivername in {"postgresql+asyncpg", "postgresql+psycopg_async"}:
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


@asynccontextmanager
async def lifespan_checkpointer(
    database_url: str,
) -> AsyncIterator[AsyncPostgresSaver]:
    """Open an ``AsyncPostgresSaver`` for the app's lifetime.

    Calls ``setup()`` on entry to create checkpoint tables idempotently.
    Use as: ``async with lifespan_checkpointer(url) as saver: ...``.
    """
    psycopg_url = to_psycopg_url(database_url)
    async with AsyncPostgresSaver.from_conn_string(
        psycopg_url, serde=build_checkpoint_serde()
    ) as saver:
        await saver.setup()
        yield saver
