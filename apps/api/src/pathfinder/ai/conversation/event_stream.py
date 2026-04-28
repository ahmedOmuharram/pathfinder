from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

import asyncpg
from pydantic import Discriminator, Tag, TypeAdapter, ValidationError
from pydantic_ai.ui.vercel_ai.response_types import (
    AbortChunk,
    BaseChunk,
    DataChunk,
    DoneChunk,
    ErrorChunk,
    FileChunk,
    FinishChunk,
    FinishStepChunk,
    MessageMetadataChunk,
    ReasoningDeltaChunk,
    ReasoningEndChunk,
    ReasoningStartChunk,
    SourceDocumentChunk,
    SourceUrlChunk,
    StartChunk,
    StartStepChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
    ToolApprovalRequestChunk,
    ToolInputAvailableChunk,
    ToolInputDeltaChunk,
    ToolInputErrorChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
    ToolOutputDeniedChunk,
    ToolOutputErrorChunk,
)
from sqlalchemy import select
from sqlalchemy.engine import make_url

from pathfinder.persistence.models import ConversationEvent
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


def _chunk_tag(value: Any) -> str:
    raw_type = value["type"] if isinstance(value, dict) else value.type
    if not isinstance(raw_type, str):
        return ""
    return "data" if raw_type.startswith("data-") else raw_type


_ChunkUnion = Annotated[
    Annotated[TextStartChunk, Tag("text-start")]
    | Annotated[TextDeltaChunk, Tag("text-delta")]
    | Annotated[TextEndChunk, Tag("text-end")]
    | Annotated[ReasoningStartChunk, Tag("reasoning-start")]
    | Annotated[ReasoningDeltaChunk, Tag("reasoning-delta")]
    | Annotated[ReasoningEndChunk, Tag("reasoning-end")]
    | Annotated[ErrorChunk, Tag("error")]
    | Annotated[ToolInputStartChunk, Tag("tool-input-start")]
    | Annotated[ToolInputDeltaChunk, Tag("tool-input-delta")]
    | Annotated[ToolOutputAvailableChunk, Tag("tool-output-available")]
    | Annotated[ToolInputAvailableChunk, Tag("tool-input-available")]
    | Annotated[ToolInputErrorChunk, Tag("tool-input-error")]
    | Annotated[ToolOutputErrorChunk, Tag("tool-output-error")]
    | Annotated[ToolApprovalRequestChunk, Tag("tool-approval-request")]
    | Annotated[ToolOutputDeniedChunk, Tag("tool-output-denied")]
    | Annotated[SourceUrlChunk, Tag("source-url")]
    | Annotated[SourceDocumentChunk, Tag("source-document")]
    | Annotated[FileChunk, Tag("file")]
    | Annotated[DataChunk, Tag("data")]
    | Annotated[StartStepChunk, Tag("start-step")]
    | Annotated[FinishStepChunk, Tag("finish-step")]
    | Annotated[StartChunk, Tag("start")]
    | Annotated[FinishChunk, Tag("finish")]
    | Annotated[AbortChunk, Tag("abort")]
    | Annotated[MessageMetadataChunk, Tag("message-metadata")]
    | Annotated[DoneChunk, Tag("done")],
    Discriminator(_chunk_tag),
]

_CHUNK_ADAPTER: TypeAdapter[BaseChunk] = TypeAdapter(_ChunkUnion)


def _asyncpg_dsn(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _fetch_after(
    conversation_id: UUID, after: int,
) -> list[tuple[int, dict[str, Any]]]:
    """Fetch chat-stream chunks. Task-tagged rows belong to the per-task SSE
    endpoint and use a different envelope shape (``{"sse": "<frame>"}``);
    pulling them into the chat replay would crash the v6 chunk discriminator.
    """
    async with async_session_factory() as session:
        rows = (
            await session.scalars(
                select(ConversationEvent)
                .where(
                    ConversationEvent.conversation_id == conversation_id,
                    ConversationEvent.id > after,
                    ConversationEvent.task_id.is_(None),
                )
                .order_by(ConversationEvent.id),
            )
        ).all()
        return [(r.id, r.chunk) for r in rows]


async def latest_event(
    conversation_id: UUID,
) -> tuple[int, dict[str, Any]] | None:
    async with async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(ConversationEvent.conversation_id == conversation_id)
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
        if row is None:
            return None
        return (row.id, row.chunk)


async def latest_turn_boundary(conversation_id: UUID) -> int:
    """Return the id of the most recent turn-terminator (`done` chunk).

    Used as the SSE replay baseline so a new client never tails into the
    middle of a tool-call sequence still being written by a prior turn —
    the failure mode that produces "Received tool-input-delta for missing
    tool call with ID …" on retry. Task-tagged rows are excluded so the
    boundary tracks the chat stream alone.
    """
    async with async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(
                ConversationEvent.conversation_id == conversation_id,
                ConversationEvent.task_id.is_(None),
                ConversationEvent.chunk["type"].astext == "done",
            )
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
        return row.id if row is not None else 0


async def latest_event_with_timestamp(
    conversation_id: UUID,
) -> tuple[int, dict[str, Any], datetime] | None:
    async with async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(ConversationEvent.conversation_id == conversation_id)
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
        if row is None:
            return None
        return (row.id, row.chunk, row.emitted_at)


async def _drain_and_yield(
    conversation_id: UUID,
    last_sent: int,
    queue: asyncio.Queue[int],
) -> AsyncIterator[tuple[int, dict[str, Any]]]:
    while True:
        await queue.get()
        while not queue.empty():
            queue.get_nowait()
        for event_id, chunk in await _fetch_after(conversation_id, last_sent):
            yield event_id, chunk
            last_sent = event_id


async def replay_and_tail(
    *,
    conversation_id: UUID,
    after: int,
) -> AsyncIterator[tuple[int, dict[str, Any]]]:
    last_sent = after
    for event_id, chunk in await _fetch_after(conversation_id, after):
        yield event_id, chunk
        last_sent = event_id

    channel = f"conversation_events:{conversation_id}"
    queue: asyncio.Queue[int] = asyncio.Queue()

    def on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
        try:
            queue.put_nowait(int(payload))
        except ValueError:
            logger.warning("pg_notify payload not an int", payload=payload)

    dsn = _asyncpg_dsn(get_settings().database_url)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.add_listener(channel, on_notify)
        # Sweep after LISTEN arms in case a row landed between the initial
        # SELECT and add_listener.
        for event_id, chunk in await _fetch_after(conversation_id, last_sent):
            yield event_id, chunk
            last_sent = event_id

        async for event_id, chunk in _drain_and_yield(
            conversation_id, last_sent, queue,
        ):
            yield event_id, chunk
    finally:
        await conn.close()


async def iter_sse(
    *, conversation_id: UUID, after: int,
) -> AsyncIterator[str]:
    async for event_id, chunk in replay_and_tail(
        conversation_id=conversation_id, after=after,
    ):
        if not isinstance(chunk, dict) or "type" not in chunk:
            logger.warning(
                "skipping persisted chunk without type discriminator",
                event_id=event_id,
                conversation_id=str(conversation_id),
            )
            continue
        try:
            typed = _CHUNK_ADAPTER.validate_python(chunk)
        except ValidationError:
            logger.warning(
                "skipping unparseable persisted chunk",
                event_id=event_id,
                conversation_id=str(conversation_id),
            )
            continue
        yield _frame_event(event_id, typed)
        if isinstance(typed, DoneChunk):
            return


def _frame_event(event_id: int, chunk: BaseChunk) -> str:
    payload = (
        "[DONE]"
        if isinstance(chunk, DoneChunk)
        else chunk.model_dump_json(by_alias=True, exclude_none=True)
    )
    return f"id: {event_id}\ndata: {payload}\n\n"
