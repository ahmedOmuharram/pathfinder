from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.capabilities.security import scan_user_input
from pathfinder.ai.conversation._turn_helpers import (
    _ensure_chat_row,
    _persist_user_message,
)
from pathfinder.ai.conversation.event_stream import iter_sse, latest_event
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.vercel_adapter import VERCEL_AI_DSP_HEADERS
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.jobs.tasks import run_chat_turn_job
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
)
from pathfinder.persistence.repositories.message import MessagesRepository
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


async def _is_approval_reply(
    session: AsyncSession, conversation_id: UUID,
) -> bool:
    """Return True when the previous assistant message halted on an
    AWAITING_USER phase outcome — the user's current reply is plausibly
    a pure approval / denial of a submitted plan.
    """
    conversation = await ConversationRepository(session).get_by_id(
        conversation_id,
    )
    if conversation is None:
        return False
    last = await MessagesRepository(session).get_latest_by_role(
        conversation_id=conversation_id, role="assistant",
    )
    if last is None:
        return False
    parts = last.parts or []
    for part in parts:
        if part.get("type") == "data-supervisor-decision":
            decision = part.get("data") or {}
            if decision.get("to") == "end":
                return True
    return False


async def dispatch(
    *,
    body: ChatRequestBody,
    session: AsyncSession,
    user_id: UUID,
) -> Response:
    """Scan user input, persist it, enqueue a turn job, tail the event stream."""
    await _ensure_chat_row(
        session,
        body.conversation_id,
        user_id=user_id,
        site_id=body.site_id,
        experiment_id=body.experiment_id,
    )

    is_approval = await _is_approval_reply(session, body.conversation_id)
    scan_user_input(body.last_user_text, is_approval_reply=is_approval)

    await _persist_user_message(session, body)
    await session.commit()

    baseline = await latest_event(body.conversation_id)
    after = baseline[0] if baseline is not None else 0

    turn_id = uuid4()
    payload = ChatTurnPayload.from_context(
        body=body, user_id=user_id, turn_id=turn_id,
    )
    await run_chat_turn_job.defer_async(
        payload=payload.model_dump(mode="json", by_alias=True),
    )

    return StreamingResponse(
        iter_sse(conversation_id=body.conversation_id, after=after),
        media_type="text/event-stream",
        headers=dict(VERCEL_AI_DSP_HEADERS),
    )


__all__ = ["ChatRequestBody", "dispatch"]
