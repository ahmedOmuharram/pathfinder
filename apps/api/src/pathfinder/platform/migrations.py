"""Brings the database schema to the latest revision at startup."""

from alembic import command
from alembic.config import Config
from assistant_core.platform.db import get_engine


def _run_alembic_upgrade(connection: object) -> None:
    """Run the migrations synchronously on a connection."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    """Initialize the database by migrating to the latest revision."""
    async with get_engine().begin() as conn:
        await conn.run_sync(_run_alembic_upgrade)
