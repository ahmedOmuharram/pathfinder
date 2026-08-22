"""A turn whose worker died ends with an error and a terminator.

Keep-alive comment frames hold the SSE connection open, so a turn that never
writes ``done`` leaves every subscriber waiting for a chunk nobody will send.
"""

from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID, uuid4

from procrastinate.testing import InMemoryConnector
from sqlalchemy import select

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.assistant_core.conversation.event_writer import ChatEventWriter
from pathfinder.jobs.maintenance import release_stalled_jobs
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.jobs.tasks import run_chat_turn_job
from pathfinder.persistence.models import Conversation, ConversationEvent, User
from pathfinder.platform.db import async_session_factory

_STALL_SECONDS = 7200


async def _seed_conversation() -> tuple[UUID, UUID]:
    user_id = uuid4()
    conversation_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                site_id="plasmodb",
                name="stalled",
            ),
        )
        await session.commit()
    return user_id, conversation_id


async def _stall_a_turn_job(
    connector: InMemoryConnector,
    *,
    user_id: UUID,
    conversation_id: UUID,
    turn_id: UUID,
) -> None:
    payload = ChatTurnPayload(
        body=ChatRequestBody(conversation_id=conversation_id, site_id="plasmodb"),
        user_id=user_id,
        turn_id=turn_id,
    )
    job_id = await run_chat_turn_job.configure(
        lock=str(conversation_id),
    ).defer_async(payload=payload.model_dump(mode="json", by_alias=True))
    connector.jobs[job_id]["status"] = "doing"
    connector.events[job_id].append(
        {
            "type": "started",
            "at": datetime.datetime.now(tz=datetime.UTC)
            - datetime.timedelta(seconds=_STALL_SECONDS),
        },
    )


async def _events(
    conversation_id: UUID,
) -> list[tuple[UUID | None, dict[str, Any]]]:
    async with async_session_factory() as session:
        rows = (
            await session.scalars(
                select(ConversationEvent)
                .where(ConversationEvent.conversation_id == conversation_id)
                .order_by(ConversationEvent.id),
            )
        ).all()
    return [(row.turn_id, row.chunk) for row in rows]


async def test_a_killed_turn_ends_with_an_error_and_a_terminator(
    patch_app_db_engine: None,
    db_cleaner: None,
    in_memory_jobs: InMemoryConnector,
) -> None:
    del patch_app_db_engine, db_cleaner
    user_id, conversation_id = await _seed_conversation()
    turn_id = uuid4()
    writer = ChatEventWriter(conversation_id=conversation_id, turn_id=turn_id)
    await writer.write({"type": "start", "messageId": str(turn_id)})
    await writer.write({"type": "data-turn-status", "data": {"label": "Queued"}})
    await _stall_a_turn_job(
        in_memory_jobs,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )

    await release_stalled_jobs()

    events = await _events(conversation_id)
    assert [chunk["type"] for _, chunk in events[-3:]] == ["error", "finish", "done"]
    assert "worker" in events[-3][1]["errorText"]
    assert events[-2][1]["finishReason"] == "error"
    assert [row_turn for row_turn, _ in events[-3:]] == [turn_id] * 3


async def test_a_turn_that_already_ended_is_not_reopened(
    patch_app_db_engine: None,
    db_cleaner: None,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """A worker that died after the terminator leaves nothing to close."""
    del patch_app_db_engine, db_cleaner
    user_id, conversation_id = await _seed_conversation()
    turn_id = uuid4()
    writer = ChatEventWriter(conversation_id=conversation_id, turn_id=turn_id)
    await writer.write({"type": "start", "messageId": str(turn_id)})
    await writer.write({"type": "finish", "finishReason": "stop"})
    await writer.write({"type": "done"})
    await _stall_a_turn_job(
        in_memory_jobs,
        user_id=user_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )

    await release_stalled_jobs()

    events = await _events(conversation_id)
    assert [chunk["type"] for _, chunk in events] == ["start", "finish", "done"]
