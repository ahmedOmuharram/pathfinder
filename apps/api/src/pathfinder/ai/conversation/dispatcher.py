from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.capabilities.security import scan_user_input
from pathfinder.ai.conversation.event_stream import (
    iter_sse,
    latest_turn_boundary,
)
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.conversation.ui_message_reducer import user_message_chunk
from pathfinder.ai.conversation.vercel_adapter import VERCEL_AI_DSP_HEADERS
from pathfinder.ai.graph.stream_events import turn_status_event
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.jobs.tasks import run_chat_turn_job
from pathfinder.persistence.models import ConversationEvent
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    MessagesRepository,
)
from pathfinder.platform.db import async_session_factory
from pathfinder.services.conversations.begin import begin_conversation


async def _cancel_in_flight_prior_turn(conversation_id: UUID) -> None:
    async with async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(
                ConversationEvent.conversation_id == conversation_id,
                ConversationEvent.task_id.is_(None),
            )
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
    if row is None:
        return
    if row.chunk.get("type") == "done":
        return
    if row.turn_id is None:
        return
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    await repo.request_cancel(
        conversation_id=conversation_id,
        turn_id=row.turn_id,
    )


async def dispatch(
    *,
    body: ChatRequestBody,
    session: AsyncSession,
    user_id: UUID,
) -> Response:
    """Scan user input, persist it, enqueue a turn job, tail the event stream.

    Two trigger modes:
    - Normal turn: ``messages[-1]`` is a user message → persist + chunk it.
    - Approval resume: SDK v6 fired the request after
      ``chat.addToolApprovalResponse`` (no new user message) — skip the
      user-message persistence and chunk; the worker reads
      ``state.approval_responses`` from the request body and resumes the
      deferred tool.
    """
    await begin_conversation(
        session=session,
        conversation_id=body.conversation_id,
        user_id=user_id,
        site_id=body.site_id,
        experiment_id=body.experiment_id,
    )

    if not body.is_approval_resume:
        await _cancel_in_flight_prior_turn(body.conversation_id)
        await scan_user_input(body.last_user_text)

        await MessagesRepository(session).insert_message(
            message_id=body.last_user_message_id,
            conversation_id=body.conversation_id,
            role="user",
            metadata={"siteId": body.site_id, "mode": body.mode},
        )
        await session.commit()

        await ChatEventWriter(
            conversation_id=body.conversation_id,
            turn_id=body.last_user_message_id,
        ).write(
            user_message_chunk(
                message_id=str(body.last_user_message_id),
                parts=[{"type": "text", "text": body.last_user_text}],
            ),
        )

    after = await latest_turn_boundary(body.conversation_id)

    turn_id = body.prior_assistant_message_id or uuid4()
    payload = ChatTurnPayload.from_context(
        body=body,
        user_id=user_id,
        turn_id=turn_id,
    )
    # The status is persisted before the job exists, so it can never land after
    # the worker's first chunk.
    await ChatEventWriter(
        conversation_id=body.conversation_id,
        turn_id=turn_id,
    ).write(
        turn_status_event(label="Queued").model_dump(
            by_alias=True,
            mode="json",
            exclude_none=True,
        ),
    )
    # Every turn for one conversation writes the same checkpoint thread, so the
    # lock keeps concurrent workers from running two of them together.
    await run_chat_turn_job.configure(lock=str(body.conversation_id)).defer_async(
        payload=payload.model_dump(mode="json", by_alias=True),
    )

    return StreamingResponse(
        iter_sse(conversation_id=body.conversation_id, after=after),
        media_type="text/event-stream",
        headers=dict(VERCEL_AI_DSP_HEADERS),
    )


__all__ = ["ChatRequestBody", "dispatch"]
