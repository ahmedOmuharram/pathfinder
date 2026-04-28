"""POST /conversations/{id}/insert-saved — user-driven insert of a saved sub-strategy."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.strategies.insert_saved import (
    insert_saved_into_conversation,
)
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser
from pathfinder.transport.http.routers._authz import (
    get_owned_conversation_or_404,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


CombineOperatorLiteral = Literal[
    "INTERSECT", "UNION", "MINUS", "RMINUS", "LONLY", "RONLY",
]


class InsertSavedRequest(CamelModel):
    target_step_id: str = Field(min_length=1, max_length=64)
    saved_wdk_strategy_id: int
    operator: CombineOperatorLiteral = "INTERSECT"


class InsertSavedResponse(CamelModel):
    wdk_strategy_id: int
    inserted_saved_wdk_strategy_id: int
    inserted_saved_name: str
    combine_step_id: str


@router.post(
    "/{conversation_id:uuid}/insert-saved",
    response_model=InsertSavedResponse,
)
async def insert_saved(
    conversation_id: UUID,
    request: InsertSavedRequest,
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> InsertSavedResponse:
    """Insert a saved WDK strategy as a combine input next to a target step."""
    conversation = await get_owned_conversation_or_404(
        conv_repo, conversation_id, user_id,
    )
    if conversation.strategy_ast is None:
        raise ValidationError(
            title="conversation has no strategy",
            detail="cannot insert into an empty conversation",
        )
    ast = StrategyAst.model_validate(conversation.strategy_ast)
    persisted = PersistedStrategyGraph(
        id=str(conversation_id),
        name=conversation.name,
        strategy_ast=ast,
        wdk_strategy_id=conversation.wdk_strategy_id,
    )
    session = build_strategy_session(site_id=site_id, strategy_graph=persisted)

    result = await insert_saved_into_conversation(
        session=session,
        site_id=site_id,
        conversation_id=conversation_id,
        db_session_factory=async_session_factory,
        target_step_id=request.target_step_id,
        saved_wdk_strategy_id=request.saved_wdk_strategy_id,
        operator=CombineOp(request.operator),
    )
    return InsertSavedResponse(
        wdk_strategy_id=result.wdk_strategy_id,
        inserted_saved_wdk_strategy_id=result.inserted_saved_wdk_strategy_id,
        inserted_saved_name=result.inserted_saved_name,
        combine_step_id=result.combine_step_id,
    )
