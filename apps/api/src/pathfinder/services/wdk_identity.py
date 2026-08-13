"""Durable per-user WDK identity for requests without a browser token.

WDK answers an uncredentialed request as a new guest, so every container
would otherwise hold its own. One guest token is minted and persisted per
PathFinder user, and every path uses it.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.integrations.veupathdb.auth_login import mint_guest_token
from pathfinder.persistence.repositories.user import UserRepository
from pathfinder.platform.config import get_settings
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def ensure_wdk_identity(session: AsyncSession, user_id: UUID) -> None:
    """Guarantee ``veupathdb_auth_token_ctx`` carries a WDK identity.

    No-op when the request already has a token (real VEuPathDB login).
    Otherwise reuses the user's persisted guest token, minting one from WDK
    on first need. Fails open: an unreachable WDK leaves the ctx unset and
    downstream calls behave as before (per-jar ephemeral guest).
    """
    if veupathdb_auth_token_ctx.get():
        logger.debug("WDK identity: request token present", user_id=str(user_id))
        return

    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        logger.debug("WDK identity: unknown user", user_id=str(user_id))
        return

    token = user.wdk_guest_token
    minted = False
    if not token:
        token = await mint_guest_token(get_settings().veupathdb_default_site)
        if not token:
            logger.warning(
                "Failed to mint WDK guest token; proceeding unauthenticated",
                user_id=str(user_id),
            )
            return
        await repo.set_wdk_guest_token(user_id, token)
        minted = True

    veupathdb_auth_token_ctx.set(token)
    logger.info(
        "WDK guest identity attached",
        user_id=str(user_id),
        minted=minted,
    )
