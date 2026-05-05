from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.strategy.operations import GraphOperation
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.session import _get_session_factory
from pathfinder.platform.errors import ErrorCode, NotFoundError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.strategies.commit import apply_and_commit
from pathfinder.services.strategies.session_factory import (
    build_strategy_session,
)
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser
from pathfinder.transport.http.routers._authz import (
    get_owned_conversation_or_404,
)
from pathfinder.transport.http.routers.conversations._shared import (
    build_conversation_response,
)
from pathfinder.transport.http.schemas.conversations import ConversationResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


class ApplyOperationRequest(CamelModel):
    op: GraphOperation


@router.post(
    "/{strategyId:uuid}/operations",
    response_model=ConversationResponse,
)
async def apply_operation_endpoint(
    strategyId: UUID,
    request: ApplyOperationRequest,
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> ConversationResponse:
    """Apply a single graph operation through the unified commit pipeline."""
    conversation = await get_owned_conversation_or_404(
        conv_repo, strategyId, user_id,
    )
    if not conversation.strategy_ast:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy AST missing",
        )

    persisted = PersistedStrategyGraph(
        id=str(strategyId),
        name=conversation.name,
        strategy_ast=StrategyAst.model_validate(conversation.strategy_ast),
        wdk_strategy_id=conversation.wdk_strategy_id,
    )
    session = build_strategy_session(
        site_id=site_id, strategy_graph=persisted,
    )

    session_maker = _get_session_factory()
    deps = AgentDeps(
        site_id=site_id,
        strategy_session=session,
        conversation_id=strategyId,
        db_session_factory=session_maker,
    )

    await apply_and_commit(deps=deps, op=request.op)

    refreshed = await conv_repo.get_by_id(strategyId)
    if refreshed is None:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy not found after commit",
        )
    return build_conversation_response(refreshed)
