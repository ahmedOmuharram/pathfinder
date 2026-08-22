"""Release the lock and close the chat stream a killed worker leaves behind."""

from __future__ import annotations

import warnings
from uuid import UUID

from procrastinate.jobs import Job, Status
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_ai.ui.vercel_ai.response_types import (
    DoneChunk,
    ErrorChunk,
    FinishChunk,
)
from sqlalchemy import select

from pathfinder.assistant_core.conversation.event_writer import ChatEventWriter
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.payloads import ChatTurnPayload
from pathfinder.persistence.models import ConversationEvent
from pathfinder.platform.config import get_settings
from pathfinder.platform.db import async_session_factory
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_CHAT_TURN_TASK = "chat_turn:run"

_STALLED_TURN_ERROR = (
    "The worker running this turn stopped before it finished. "
    "Send the message again to retry."
)


class _ChatTurnJobArgs(BaseModel):
    """The task kwargs procrastinate stores for a ``chat_turn:run`` job."""

    model_config = ConfigDict(extra="ignore")

    payload: ChatTurnPayload


async def release_stalled_jobs() -> None:
    """Fail every job left in ``doing`` past the timeout, without retrying it.

    Staleness is the age of the job's started event, not the worker heartbeat,
    because a busy worker can miss heartbeats while its job is alive.
    """
    manager = procrastinate_app.job_manager
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        stalled = await manager.get_stalled_jobs(
            nb_seconds=get_settings().worker_stalled_job_timeout_seconds,
        )
    for job in stalled:
        # The terminator is written first: the conversation lock is still held,
        # so no successor turn can interleave its chunks with it.
        await _close_stalled_turn(job)
        await manager.finish_job(job, status=Status.FAILED, delete_job=False)
        logger.warning(
            "Released a stalled job",
            job_id=job.id,
            task_name=job.task_name,
            queue_name=job.queue,
            lock=job.lock,
        )


async def _close_stalled_turn(job: Job) -> None:
    """End the chat stream a killed turn left open, so subscribers stop waiting."""
    if job.task_name != _CHAT_TURN_TASK:
        return
    try:
        args = _ChatTurnJobArgs.model_validate(job.task_kwargs)
    except ValidationError:
        logger.warning("Stalled chat turn carries no readable payload", job_id=job.id)
        return
    conversation_id = args.payload.body.conversation_id
    if not await _chat_stream_is_open(conversation_id):
        return
    writer = ChatEventWriter(
        conversation_id=conversation_id,
        turn_id=args.payload.turn_id,
    )
    for chunk in (
        ErrorChunk(error_text=_STALLED_TURN_ERROR),
        FinishChunk(finish_reason="error"),
        DoneChunk(),
    ):
        await writer.write(
            chunk.model_dump(by_alias=True, mode="json", exclude_none=True),
        )
    logger.warning(
        "Closed the chat stream of a stalled turn",
        job_id=job.id,
        conversation_id=str(conversation_id),
        turn_id=str(args.payload.turn_id),
    )


async def _chat_stream_is_open(conversation_id: UUID) -> bool:
    """True when the newest chat chunk is not a turn terminator."""
    async with async_session_factory() as session:
        newest = await session.scalar(
            select(ConversationEvent.chunk["type"].astext)
            .where(
                ConversationEvent.conversation_id == conversation_id,
                ConversationEvent.task_id.is_(None),
            )
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
    return newest is not None and newest != "done"
