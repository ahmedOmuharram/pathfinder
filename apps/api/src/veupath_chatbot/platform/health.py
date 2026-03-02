"""Health-check probes for external dependencies."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)


async def check_database(session: AsyncSession) -> bool:
    """Return ``True`` if the database responds to a simple query."""
    await session.execute(text("SELECT 1"))
    return True


async def check_qdrant() -> bool:
    """Return ``True`` if Qdrant is reachable and lists collections."""
    settings = get_settings()
    from qdrant_client import AsyncQdrantClient

    client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=5,
    )
    try:
        await client.get_collections()
        return True
    finally:
        await client.close()
