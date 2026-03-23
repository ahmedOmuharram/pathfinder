"""Health-check probes for external dependencies."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)


async def check_database(session: AsyncSession) -> bool:
    """Return ``True`` if the database responds to a simple query."""
    await session.execute(text("SELECT 1"))
    return True
