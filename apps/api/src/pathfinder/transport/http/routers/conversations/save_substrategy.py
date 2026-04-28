"""POST /conversations/{id}/save-substrategy — clone a subtree to a new WDK saved strategy."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.platform.errors import (
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.strategies.save_substrategy import (
    save_subtree_as_strategy,
)
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser
from pathfinder.transport.http.routers._authz import (
    get_owned_conversation_or_404,
)
from pathfinder.transport.http.schemas import (
    SaveSubstrategyRequest,
    SaveSubstrategyResponse,
)


class SavedStrategyConsumerCounts(CamelModel):
    """Map of WDK strategy id -> number of conversations that import it."""

    counts: dict[int, int]

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post(
    "/{conversation_id:uuid}/save-substrategy",
    response_model=SaveSubstrategyResponse,
)
async def save_substrategy(
    conversation_id: UUID,
    request: SaveSubstrategyRequest,
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> SaveSubstrategyResponse:
    """Save a subtree of the active strategy as a new WDK saved strategy.

    The cloned subtree is pushed to WDK as fresh steps under a new strategy
    with ``isSaved=true``. The source conversation is not modified — the
    caller is expected to insert the saved strategy back via a combine step
    on a follow-up turn (which will set ``imported_saved_strategy_ids`` on
    the source conversation as the deletion guard).
    """
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    if conversation.strategy_ast is None:
        raise ValidationError(
            title="conversation has no strategy",
            detail="cannot save substrategy from an empty conversation",
        )

    ast = StrategyAst.model_validate(conversation.strategy_ast)
    persisted = PersistedStrategyGraph(
        id=str(conversation_id),
        name=conversation.name,
        strategy_ast=ast,
        wdk_strategy_id=conversation.wdk_strategy_id,
    )
    session = build_strategy_session(site_id=site_id, strategy_graph=persisted)
    graph = session.get_graph(None)
    if graph is None or request.step_id not in graph.steps:
        raise NotFoundError(
            code=ErrorCode.STEP_NOT_FOUND,
            title="step not found",
            detail=(
                f"step {request.step_id!r} not found in conversation "
                f"{conversation_id}"
            ),
        )

    result = await save_subtree_as_strategy(
        session=session,
        site_id=site_id,
        source_step_id=request.step_id,
        name=request.name,
        description=request.description,
    )
    return SaveSubstrategyResponse(
        wdk_strategy_id=result.wdk_strategy_id,
        name=result.name,
        description=result.description,
        record_type=result.record_type,
        root_step_id=result.root_step_id,
    )


@router.get(
    "/saved-strategy-consumers",
    response_model=SavedStrategyConsumerCounts,
)
async def get_saved_strategy_consumer_counts(
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> SavedStrategyConsumerCounts:
    """Count how many conversations consume each saved strategy.

    Returned map only includes ids with consumers; absent ids have 0.
    """
    counts = await conv_repo.count_consumers_per_saved_strategy(user_id, site_id)
    return SavedStrategyConsumerCounts(counts=counts)
