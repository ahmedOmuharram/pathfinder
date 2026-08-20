"""WDK strategy open/import/sync orchestration."""

from uuid import UUID

from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.control_helpers import (
    cleanup_internal_control_test_strategies,
)
from pathfinder.services.conversations.authz import owned_by_caller
from pathfinder.services.conversations.responses import (
    ConversationResponse,
    build_conversation_summary,
)
from pathfinder.services.strategies.wdk_sync import (
    sync_to_chat,
    upsert_summary_chat,
)
from pathfinder.services.wdk import (
    get_site,
    get_strategy_api,
    is_internal_wdk_strategy_name,
)

logger = get_logger(__name__)


def _require_site_id(site_id: str | None) -> str:
    if not site_id:
        raise ValidationError(
            detail="siteId is required",
            errors=[
                {"path": "siteId", "message": "Required", "code": "INVALID_PARAMETERS"},
            ],
        )
    return site_id


async def open_strategy(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    wdk_strategy_id: int | None,
    site_id: str | None,
    user_id: UUID,
) -> UUID:
    """Open a strategy by local id or WDK strategy id; create a fresh one if neither."""
    conv_repo = ConversationRepository(session)

    if not conversation_id and not wdk_strategy_id:
        conversation = await conv_repo.create(
            user_id=user_id,
            site_id=_require_site_id(site_id),
            name=DEFAULT_STREAM_NAME,
        )
        return conversation.id

    if conversation_id:
        existing = await conv_repo.get_by_id(conversation_id)
        if not existing or not owned_by_caller(existing, user_id):
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND,
                title="Strategy not found",
            )
        return existing.id

    resolved_site = _require_site_id(site_id)
    if wdk_strategy_id is None:
        raise ValidationError(
            detail="wdk_strategy_id is required",
            errors=[
                {
                    "path": "wdk_strategy_id",
                    "message": "Required",
                    "code": "INVALID_PARAMETERS",
                },
            ],
        )
    # Resolving the site is the caller's business, not the upstream service's:
    # an unconfigured siteId raises NotFoundError(SITE_NOT_FOUND). Kept out of
    # the block below so a typo reports 404 instead of "VEuPathDB is down".
    api = get_strategy_api(resolved_site)
    try:
        conversation = await sync_to_chat(
            wdk_id=wdk_strategy_id,
            site_id=resolved_site,
            api=api,
            conv_repo=conv_repo,
            user_id=user_id,
        )
    except AppError:
        logger.exception("WDK fetch failed")
        raise
    except Exception as e:
        logger.exception("WDK fetch failed")
        msg = f"Failed to load WDK strategy: {e}"
        raise WDKError(msg) from e
    return conversation.id


async def sync_all_wdk_strategies(
    session: AsyncSession,
    *,
    site_id: str,
    user_id: UUID,
) -> list[ConversationResponse]:
    """Batch-sync all WDK strategies into the chats table; return the full list."""
    conv_repo = ConversationRepository(session)
    site = get_site(site_id)
    try:
        api = get_strategy_api(site.id)
        wdk_items = await api.list_strategies()
        await cleanup_internal_control_test_strategies(api, wdk_items, site_id=site.id)
    except (AppError, OSError, RuntimeError) as e:
        logger.warning("WDK list failed during sync", site_id=site.id, error=str(e))
        wdk_items = []

    synced_wdk_ids: set[int] = set()
    for item in wdk_items:
        if is_internal_wdk_strategy_name(item.name):
            continue
        synced_wdk_ids.add(item.strategy_id)
        try:
            async with conv_repo.session.begin_nested():
                await upsert_summary_chat(
                    item,
                    conv_repo=conv_repo,
                    user_id=user_id,
                    site_id=site.id,
                )
        except (AppError, OSError, RuntimeError) as e:
            logger.warning(
                "Failed to sync WDK strategy",
                wdk_id=item.strategy_id,
                site_id=site.id,
                error=str(e),
            )

    if wdk_items:
        try:
            async with conv_repo.session.begin_nested():
                pruned = await conv_repo.prune_wdk_orphans(
                    user_id,
                    site.id,
                    synced_wdk_ids,
                )
                if pruned:
                    logger.info(
                        "Pruned orphaned chats",
                        site_id=site.id,
                        pruned_count=pruned,
                    )
        except (AppError, OSError, RuntimeError) as e:
            logger.warning(
                "Failed to prune orphaned chats",
                site_id=site.id,
                error=str(e),
            )

    conversations = await conv_repo.list_conversations(user_id, site_id)
    # Commit so locks release before the background auto-import opens its own
    # session — prevents deadlock between the prune DELETE and the import's
    # concurrent SELECT/UPDATE on the same tables.
    await conv_repo.session.commit()
    return [build_conversation_summary(c, site_id=site_id) for c in conversations]
