from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from assistant_core.graph.stream_events import background_task_started_event
from assistant_core.graph.turn_state import UserQuestionAnswer
from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.spec import TurnStart
from langgraph.types import Interrupt
from pydantic import BaseModel, ValidationError
from pydantic_ai.ui.vercel_ai._utils import iter_tool_approval_responses
from pydantic_ai.ui.vercel_ai.request_types import (
    DataUIPart,
    ToolApprovalResponded,
)

from pathfinder.ai.conversation.request_body import ChatRequestBody


def resolve_site_id(
    *,
    chat_site_id: str | None,
    body_site_id: str,
    conversation_id: UUID,
) -> str:
    if chat_site_id is not None and chat_site_id.strip() != "":
        return chat_site_id
    if body_site_id.strip() != "":
        return body_site_id
    msg = (
        f"site_id could not be resolved for chat {conversation_id}: "
        f"conversation.site_id={chat_site_id!r}, body.site_id={body_site_id!r}"
    )
    raise ValueError(msg)


def _extract_approval_responses(
    incoming: ChatRequestBody,
) -> dict[str, ToolApprovalResponded]:
    return dict(iter_tool_approval_responses(incoming.messages))


_USER_QUESTION_ANSWERS_TYPE = "data-user-question-answers"


class _UserQuestionAnswersPayload(CamelModel):
    """Shape of a ``data-user-question-answers`` UI part's ``data`` field.

    The frontend question carousel sends this on the assistant message
    carrying the ``approval-responded`` part for ``consult_user``, with
    camelCase keys (``toolCallId``) — so this MUST be a CamelModel. Paired by
    ``tool_call_id``.
    """

    tool_call_id: str
    answers: list[UserQuestionAnswer]


def _extract_user_question_answers(
    incoming: ChatRequestBody,
) -> dict[str, list[UserQuestionAnswer]]:
    """Pull ``data-user-question-answers`` parts out of assistant messages.

    Returns ``{tool_call_id: [UserQuestionAnswer, ...]}`` so the
    ``consult_user`` body can hand the Lead the user's answers.
    """
    out: dict[str, list[UserQuestionAnswer]] = {}
    for msg in incoming.messages:
        if msg.role != "assistant":
            continue
        for part in msg.parts:
            if not isinstance(part, DataUIPart):
                continue
            if part.type != _USER_QUESTION_ANSWERS_TYPE:
                continue
            try:
                payload = _UserQuestionAnswersPayload.model_validate(part.data)
            except ValidationError:
                continue
            out[payload.tool_call_id] = payload.answers
    return out


def build_turn_start(
    incoming: ChatRequestBody,
    user_id: UUID,
    *,
    turn_message_id: UUID,
    turn_start_event_id: int,
) -> TurnStart:
    """The turn's inputs, for the assistant's state factory to shape."""
    resume = incoming.is_approval_resume
    return TurnStart(
        conversation_id=incoming.conversation_id,
        user_id=user_id,
        site_id=incoming.site_id,
        mode=incoming.mode,
        turn_message_id=turn_message_id,
        turn_start_event_id=turn_start_event_id,
        turn_trace_id=str(uuid4()),
        turn_created_at=datetime.now(UTC).isoformat(),
        is_resume=resume,
        user_message_id=None if resume else incoming.last_user_message_id,
        user_prompt="" if resume else incoming.last_user_text,
        approval_responses=_extract_approval_responses(incoming),
        user_question_answers=_extract_user_question_answers(incoming),
    )


class _ChunkEnvelope(BaseModel):
    chunk: dict[str, Any]


def _extract_chunk(payload: object) -> dict[str, Any] | None:
    """Pull a v6 chunk dict out of the ``{"chunk": {...}}`` writer envelope."""
    if not isinstance(payload, dict):
        return None
    try:
        envelope = _ChunkEnvelope.model_validate(payload)
    except ValidationError:
        return None
    return envelope.chunk


_INTERRUPT_KEY: str = "__interrupt__"


class _DurableInterruptPayload(BaseModel):
    """Typed shape of the value passed to ``interrupt()`` by ``@durable_tool``."""

    kind: Literal["durable_task"]
    task_id: str
    tool_name: str
    estimated_duration_seconds: int


def _iter_raw_interrupts(
    payload: object,
) -> list[tuple[Interrupt, _DurableInterruptPayload]]:
    if not isinstance(payload, dict):
        return []
    raw_interrupts = payload.get(_INTERRUPT_KEY)
    if not isinstance(raw_interrupts, tuple | list):
        return []
    parsed: list[tuple[Interrupt, _DurableInterruptPayload]] = []
    for item in raw_interrupts:
        if not isinstance(item, Interrupt):
            continue
        try:
            durable = _DurableInterruptPayload.model_validate(
                item.value,
                strict=False,
            )
        except ValidationError:
            continue
        parsed.append((item, durable))
    return parsed


def _interrupt_chunks(payload: object) -> Iterator[dict[str, Any]]:
    """Yield one ``data-background-task-started`` chunk per durable interrupt."""
    raw = _iter_raw_interrupts(payload)
    for _, durable in raw:
        chunk = background_task_started_event(
            task_id=UUID(durable.task_id),
            tool_name=durable.tool_name,
            estimated_duration_seconds=durable.estimated_duration_seconds,
        )
        yield chunk.model_dump(by_alias=True, mode="json", exclude_none=True)
