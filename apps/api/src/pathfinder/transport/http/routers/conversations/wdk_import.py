"""WDK-backed strategy endpoints (open/import/sync/list) — thin transport."""

from fastapi import APIRouter, BackgroundTasks

from pathfinder.services.conversations.responses import ConversationResponse
from pathfinder.services.conversations.wdk_import import (
    open_strategy as open_strategy_service,
)
from pathfinder.services.conversations.wdk_import import (
    sync_all_wdk_strategies as sync_all_wdk_strategies_service,
)
from pathfinder.services.strategies.auto_import import (
    background_auto_import_gene_sets,
)
from pathfinder.transport.http.deps import CurrentUser, DBSession, RequiredSiteIdQuery
from pathfinder.transport.http.schemas import (
    OpenConversationRequest,
    OpenConversationResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("/open", response_model=OpenConversationResponse)
async def open_strategy(
    request: OpenConversationRequest,
    session: DBSession,
    user_id: CurrentUser,
) -> OpenConversationResponse:
    """Open a strategy by local id or WDK strategy id."""
    conversation_id = await open_strategy_service(
        session,
        conversation_id=request.conversation_id,
        wdk_strategy_id=request.wdk_strategy_id,
        site_id=request.site_id,
        user_id=user_id,
    )
    # Commit before the response: the caller reads this id back immediately,
    # and the session dependency commits only after the response is sent.
    await session.commit()
    return OpenConversationResponse(conversation_id=conversation_id)


@router.post("/sync-wdk", response_model=list[ConversationResponse])
async def sync_all_wdk_strategies(
    site_id: RequiredSiteIdQuery,
    session: DBSession,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
) -> list[ConversationResponse]:
    """Batch-sync all WDK strategies into the conversations and return the list."""
    conversations = await sync_all_wdk_strategies_service(
        session,
        site_id=site_id,
        user_id=user_id,
    )
    background_tasks.add_task(
        background_auto_import_gene_sets,
        site_id=site_id,
        user_id=user_id,
    )
    return conversations
