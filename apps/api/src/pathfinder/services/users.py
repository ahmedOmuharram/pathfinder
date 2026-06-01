"""User account service — wraps ``UserRepository`` for transport callers."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.repositories.user import UserRepository


async def get_or_create_user_id(session: AsyncSession, external_id: str) -> UUID:
    """Resolve (or create) the internal user for ``external_id`` and return its id."""
    user = await UserRepository(session).get_or_create_by_external_id(external_id)
    return user.id


async def ensure_user_exists(session: AsyncSession, user_id: UUID) -> None:
    """Persist the authenticated user's row if missing (FK integrity)."""
    await UserRepository(session).get_or_create(user_id)
