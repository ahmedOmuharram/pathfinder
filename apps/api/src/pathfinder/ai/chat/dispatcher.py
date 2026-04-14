from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.vercel_ai.request_types import UIMessage
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response, StreamingResponse

from pathfinder.ai.chat.title_generator import generate_conversation_title
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_chunks import (
    SSE_DONE_LINE,
    encode_chunk_as_sse,
    title_metadata_chunk,
)
from pathfinder.domain.strategy.plan_payload import (
    PersistedStrategyGraph,
    StrategyPlanPayload,
)
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import ChatRepository, MessagesRepository
from pathfinder.persistence.repositories.chat import ChatUpdate
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.logging import get_logger
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session

logger = get_logger(__name__)


class _IncomingChatRequest(BaseModel):
    chat_id: UUID
    user_message_id: UUID
    user_prompt: str
    user_parts: list[dict[str, Any]]
    site_id: str
    mode: str
    pipeline_config: dict[str, Any] | None
    experiment_id: str | None


def _is_uuid(s: str) -> bool:
    try:
        UUID(s)
    except (TypeError, ValueError):
        return False
    return True


def _extract_prompt(message: UIMessage) -> str:
    pieces: list[str] = []
    for part in message.parts:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            pieces.append(text)
    return "".join(pieces)


def _parse_request_body(raw: bytes) -> _IncomingChatRequest:
    payload = json.loads(raw)
    chat_id = UUID(payload["id"])
    user_message = UIMessage.model_validate(payload["message"])
    metadata = payload.get("metadata") or {}

    user_message_id = UUID(user_message.id) if _is_uuid(user_message.id) else uuid4()
    parts_dump = [
        p.model_dump(by_alias=True, exclude_none=True) for p in user_message.parts
    ]

    raw_exp = metadata.get("experimentId")
    experiment_id = str(raw_exp) if raw_exp else None

    return _IncomingChatRequest(
        chat_id=chat_id,
        user_message_id=user_message_id,
        user_prompt=_extract_prompt(user_message),
        user_parts=parts_dump,
        site_id=str(metadata.get("siteId") or ""),
        mode=str(metadata.get("mode") or "strategy"),
        pipeline_config=metadata.get("pipeline"),
        experiment_id=experiment_id,
    )


async def dispatch(
    request: Request,
    *,
    session: AsyncSession,
    user_id: UUID,
) -> Response:
    raw_body = await request.body()
    incoming = _parse_request_body(raw_body)

    await _ensure_chat_row(
        session,
        incoming.chat_id,
        user_id=user_id,
        site_id=incoming.site_id,
        experiment_id=incoming.experiment_id,
    )
    await _persist_user_message(session, incoming)
    await session.commit()

    compiled_graph = request.app.state.compiled_graph
    chat = await ChatRepository(session).get_by_id(incoming.chat_id)
    runtime_context = _build_runtime_context(
        chat=chat, site_id=incoming.site_id, user_id=user_id,
    )

    headers = {"x-vercel-ai-ui-message-stream": "v1"}
    return StreamingResponse(
        _event_source(
            incoming=incoming,
            user_id=user_id,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
        ),
        media_type=SSE_CONTENT_TYPE,
        headers=headers,
    )


async def _ensure_chat_row(
    session: AsyncSession,
    chat_id: UUID,
    *,
    user_id: UUID,
    site_id: str,
    experiment_id: str | None,
) -> None:
    existing = await session.get(Chat, chat_id)
    if existing is None:
        session.add(
            Chat(
                id=chat_id,
                user_id=user_id,
                site_id=site_id,
                name="",
                experiment_id=experiment_id,
            )
        )
        await session.flush()
        return
    if experiment_id and existing.experiment_id != experiment_id:
        existing.experiment_id = experiment_id
        await session.flush()


async def _persist_user_message(
    session: AsyncSession, incoming: _IncomingChatRequest
) -> None:
    repo = MessagesRepository(session)
    await repo.insert_message(
        message_id=incoming.user_message_id,
        chat_id=incoming.chat_id,
        role="user",
        parts=incoming.user_parts,
        metadata={"siteId": incoming.site_id, "mode": incoming.mode},
    )


def _build_runtime_context(
    *,
    chat: Chat | None,
    site_id: str,
    user_id: UUID,
) -> Context:
    persisted: PersistedStrategyGraph | None = None
    experiment_id: str | None = None
    if chat is not None:
        plan_payload: StrategyPlanPayload | None = None
        if chat.plan and "root" in chat.plan:
            try:
                plan_payload = StrategyPlanPayload.model_validate(chat.plan)
            except (ValueError, KeyError, TypeError):
                plan_payload = None
        persisted = PersistedStrategyGraph(
            id=str(chat.id),
            name=chat.name,
            plan=plan_payload,
            wdk_strategy_id=chat.wdk_strategy_id,
        )
        experiment_id = chat.experiment_id

    strategy_session = build_strategy_session(
        site_id=site_id, strategy_graph=persisted,
    )
    return Context(
        site_id=site_id,
        user_id=user_id,
        strategy_session=strategy_session,
        db_session_factory=async_session_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        experiment_id=experiment_id,
    )


def _build_turn_input(incoming: _IncomingChatRequest, user_id: UUID) -> dict[str, Any]:
    state = PipelineState(
        chat_id=incoming.chat_id,
        user_id=user_id,
        site_id=incoming.site_id,
        mode=incoming.mode,
        user_message_id=incoming.user_message_id,
        user_prompt=incoming.user_prompt,
        user_parts=incoming.user_parts,
        turn_trace_id=str(uuid4()),
        turn_created_at=datetime.now(UTC).isoformat(),
    )
    turn_meta = state.model_dump()
    turn_meta["phase_decisions"] = {}
    return turn_meta


def _extract_sse(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    sse = payload.get("sse")
    return sse if isinstance(sse, str) else None


async def _stream_graph_chunks(
    *,
    incoming: _IncomingChatRequest,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
    title_task: asyncio.Task[str] | None,
) -> AsyncIterator[str]:
    thread_config = {"configurable": {"thread_id": str(incoming.chat_id)}}
    title_emitted = False
    graph_input = _build_turn_input(incoming, user_id)

    async for mode, payload in compiled_graph.astream(
        graph_input,
        config=thread_config,
        context=runtime_context,
        stream_mode=["custom"],
    ):
        if mode != "custom":
            continue
        sse = _extract_sse(payload)
        if sse is not None:
            yield sse
        if not title_emitted:
            async for sse_line in _maybe_emit_title_metadata(
                title_task=title_task,
                chat_id=incoming.chat_id,
                wait_for_completion=False,
            ):
                yield sse_line
                title_emitted = True

    if not title_emitted:
        async for sse_line in _maybe_emit_title_metadata(
            title_task=title_task,
            chat_id=incoming.chat_id,
            wait_for_completion=True,
        ):
            yield sse_line


async def _event_source(
    *,
    incoming: _IncomingChatRequest,
    user_id: UUID,
    compiled_graph: Any,
    runtime_context: Context,
) -> AsyncIterator[str]:
    title_task = _maybe_start_title_task(incoming)
    cancelled = False
    try:
        async for sse in _stream_graph_chunks(
            incoming=incoming,
            user_id=user_id,
            compiled_graph=compiled_graph,
            runtime_context=runtime_context,
            title_task=title_task,
        ):
            yield sse
    except asyncio.CancelledError:
        runtime_context.cancel_event.set()
        logger.info("Chat stream cancelled by client disconnect")
        cancelled = True
    except Exception as exc:
        runtime_context.cancel_event.set()
        logger.exception("Pipeline dispatcher failed", exc_info=exc)
    finally:
        if not cancelled:
            yield SSE_DONE_LINE


def _maybe_start_title_task(
    incoming: _IncomingChatRequest,
) -> asyncio.Task[str] | None:
    user_prompt = incoming.user_prompt.strip()
    if not user_prompt:
        return None
    return asyncio.create_task(generate_conversation_title(user_prompt))


async def _maybe_emit_title_metadata(
    *,
    title_task: asyncio.Task[str] | None,
    chat_id: UUID,
    wait_for_completion: bool,
) -> AsyncIterator[str]:
    if title_task is None:
        return
    if not wait_for_completion and not title_task.done():
        return

    try:
        title = await title_task
    except Exception:
        logger.exception("Conversation title generation failed")
        return
    if not title:
        return

    async with async_session_factory() as session:
        chat_repo = ChatRepository(session)
        chat = await chat_repo.get_by_id(chat_id)
        if chat is not None and chat.name:
            return
        await chat_repo.update_chat(chat_id, ChatUpdate(name=title))
        await session.commit()

    yield encode_chunk_as_sse(title_metadata_chunk(title))


__all__ = ["dispatch"]
