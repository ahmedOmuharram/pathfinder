"""WDK-backed strategy endpoints (open/import/sync/list)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query
from shared_py.defaults import DEFAULT_STREAM_NAME

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
from pathfinder.services.strategies.auto_import import (
    background_auto_import_gene_sets,
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
from pathfinder.transport.http.deps import (
    ConversationRepo,
    CurrentUser,
)
from pathfinder.transport.http.schemas import (
    ConversationResponse,
    OpenConversationRequest,
    OpenConversationResponse,
)

from ._shared import build_conversation_summary

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])
logger = get_logger(__name__)


@router.post("/open", response_model=OpenConversationResponse)
async def open_strategy(
    request: OpenConversationRequest,
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> OpenConversationResponse:
    """Open a strategy by local id or WDK strategy id."""
    if not request.conversation_id and not request.wdk_strategy_id:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[
                    {
                        "path": "siteId",
                        "message": "Required",
                        "code": "INVALID_PARAMETERS",
                    }
                ],
            )
        conversation = await conv_repo.create(
            user_id=user_id,
            site_id=request.site_id,
            name=DEFAULT_STREAM_NAME,
        )
        return OpenConversationResponse(conversation_id=conversation.id)

    if request.conversation_id:
        existing = await conv_repo.get_by_id(request.conversation_id)
        if not existing or existing.user_id != user_id:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        return OpenConversationResponse(conversation_id=existing.id)

    if not request.site_id:
        raise ValidationError(
            detail="siteId is required",
            errors=[
                {
                    "path": "siteId",
                    "message": "Required",
                    "code": "INVALID_PARAMETERS",
                }
            ],
        )
    if request.wdk_strategy_id is None:
        raise ValidationError(
            detail="wdk_strategy_id is required",
            errors=[
                {
                    "path": "wdk_strategy_id",
                    "message": "Required",
                    "code": "INVALID_PARAMETERS",
                }
            ],
        )
    try:
        api = get_strategy_api(request.site_id)
        conversation = await sync_to_chat(
            wdk_id=request.wdk_strategy_id,
            site_id=request.site_id,
            api=api,
            conv_repo=conv_repo,
            user_id=user_id,
        )
    except WDKError as e:
        logger.exception("WDK fetch failed", error=str(e))
        raise
    except Exception as e:
        logger.exception("WDK fetch failed", error=str(e))
        msg = f"Failed to load WDK strategy: {e}"
        raise WDKError(msg) from e

    return OpenConversationResponse(conversation_id=conversation.id)


@router.post("/sync-wdk", response_model=list[ConversationResponse])
async def sync_all_wdk_strategies(
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
) -> list[ConversationResponse]:
    """Batch-sync all WDK strategies into the chats table and return the full list."""
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
                    user_id, site.id, synced_wdk_ids
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

    # Commit the session so all locks are released before the background task
    # opens its own session — prevents deadlock between the prune DELETE and
    # the auto-import's concurrent SELECT/UPDATE on the same tables.
    await conv_repo.session.commit()

    background_tasks.add_task(
        background_auto_import_gene_sets, site_id=site.id, user_id=user_id
    )

    return [build_conversation_summary(c, site_id=site_id) for c in conversations]
