"""Undo endpoint — revert a chat turn and all subsequent turns."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.undo import undo_turn
from veupath_chatbot.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class UndoRequest(BaseModel):
    """Request body for the undo endpoint."""

    entry_id: str = Field(alias="entryId")


class UndoResponse(BaseModel):
    """Response body for the undo endpoint."""

    message_count: int = Field(alias="messageCount")
    strategy: JSONObject | None = None
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")

    model_config = {"populate_by_name": True}


@router.post("/{stream_id}/undo")
async def undo(
    stream_id: UUID,
    body: UndoRequest,
    user_id: CurrentUser,
    session: DBSession,
) -> UndoResponse:
    """Undo a chat turn and all subsequent turns.

    Truncates the conversation from the given Redis entry ID onward,
    rebuilds the strategy projection, and syncs WDK.
    """
    result = await undo_turn(
        stream_id=stream_id,
        entry_id=body.entry_id,
        user_id=user_id,
        session=session,
    )
    return UndoResponse(
        message_count=result.message_count,
        strategy=result.strategy,
        wdk_strategy_id=result.wdk_strategy_id,
    )
