"""POST /conversations/{id}/insert-saved — user-driven insert of a saved sub-strategy."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import Field

from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.conversations.service import ConversationService
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


CombineOperatorLiteral = Literal[
    "INTERSECT",
    "UNION",
    "MINUS",
    "RMINUS",
    "LONLY",
    "RONLY",
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
    session: DBSession,
    user_id: CurrentUser,
) -> InsertSavedResponse:
    """Insert a saved WDK strategy as a combine input next to a target step."""
    result = await ConversationService(session).insert_saved(
        conversation_id,
        user_id,
        site_id=site_id,
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
