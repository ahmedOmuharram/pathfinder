from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Interrupt
from pydantic import BaseModel, ValidationError
from pydantic_ai.ui.vercel_ai._utils import iter_tool_approval_responses
from pydantic_ai.ui.vercel_ai.request_types import (
    DataUIPart,
    TextUIPart,
    ToolApprovalResponded,
)

from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PlanSlotAnswer
from pathfinder.ai.graph.stream_events import background_task_started_event
from pathfinder.domain.research.citations import (
    LiteratureFilters,
    LiteratureOutputOptions,
    LiteratureSort,
    LiteratureSource,
)
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.processing import LiteratureSearchResponse
from pathfinder.services.research.web_search import (
    SearchDiagnostics,
    WebSearchResponse,
    WebSearchService,
)
from pathfinder.services.strategies.session_factory import build_strategy_session


class _StubLiteratureSearchService(LiteratureSearchService):
    async def search(
        self,
        query: str,
        *,
        source: LiteratureSource = "all",
        limit: int = 5,
        sort: LiteratureSort = "relevance",
        options: LiteratureOutputOptions | None = None,
        filters: LiteratureFilters | None = None,
    ) -> LiteratureSearchResponse:
        del limit, options
        return LiteratureSearchResponse(
            query=query,
            source=source,
            sort=sort,
            include_abstract=False,
            abstract_max_chars=500,
            max_authors=2,
            filters=filters or LiteratureFilters(),
            results=[],
            citations=[],
        )


class _StubWebSearchService(WebSearchService):
    async def search(
        self,
        query: str,
        limit: int = 5,
        *,
        include_summary: bool = False,
        summary_max_chars: int = 600,
    ) -> WebSearchResponse:
        del limit, include_summary, summary_max_chars
        return WebSearchResponse(
            query=query,
            effective_query=query,
            search_adjusted=False,
            search_diagnostics=SearchDiagnostics(),
            results=[],
            citations=[],
        )


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


def _build_runtime_context(
    *,
    conversation: Conversation | None,
    site_id: str,
    user_id: UUID,
    memory_store: AsyncPostgresStore | None,
) -> Context:
    persisted: PersistedStrategyGraph | None = None
    experiment_id: str | None = None
    if conversation is not None:
        plan_payload: StrategyAst | None = None
        if conversation.strategy_ast and "root" in conversation.strategy_ast:
            try:
                plan_payload = StrategyAst.model_validate(conversation.strategy_ast)
            except (ValueError, KeyError, TypeError):
                plan_payload = None
        persisted = PersistedStrategyGraph(
            id=str(conversation.id),
            name=conversation.name,
            strategy_ast=plan_payload,
            wdk_strategy_id=conversation.wdk_strategy_id,
        )
        experiment_id = conversation.experiment_id

    strategy_session = build_strategy_session(
        site_id=site_id, strategy_graph=persisted,
    )
    is_mock = (
        get_settings().pathfinder_chat_provider.strip().lower() == "mock"
    )
    return Context(
        site_id=site_id,
        user_id=user_id,
        strategy_session=strategy_session,
        db_session_factory=async_session_factory,
        web_search_service=_StubWebSearchService() if is_mock else WebSearchService(),
        literature_search_service=(
            _StubLiteratureSearchService() if is_mock else LiteratureSearchService()
        ),
        cancel_event=asyncio.Event(),
        memory_store=memory_store,
        experiment_id=experiment_id,
    )


def _extract_approval_responses(
    incoming: ChatRequestBody,
) -> dict[str, ToolApprovalResponded]:
    return dict(iter_tool_approval_responses(incoming.messages))


_PLAN_SLOT_ANSWERS_TYPE = "data-plan-slot-answers"


class _PlanSlotAnswersPayload(BaseModel):
    """Shape of a ``data-plan-slot-answers`` UI part's ``data`` field.

    Frontend sends this on the assistant message that carries the
    ``approval-responded`` part for ``submit_plan``. The pairing is by
    ``tool_call_id``.
    """

    tool_call_id: str
    answers: list[PlanSlotAnswer]


def _extract_plan_slot_answers(
    incoming: ChatRequestBody,
) -> dict[str, list[PlanSlotAnswer]]:
    """Pull ``data-plan-slot-answers`` parts out of assistant messages.

    Returns ``{tool_call_id: [PlanSlotAnswer, ...]}``. The submit_plan
    body resolves its own ``tool_call_id`` from ``ctx`` and applies the
    matched list to the active plan.
    """
    out: dict[str, list[PlanSlotAnswer]] = {}
    for msg in incoming.messages:
        if msg.role != "assistant":
            continue
        for part in msg.parts:
            if not isinstance(part, DataUIPart):
                continue
            if part.type != _PLAN_SLOT_ANSWERS_TYPE:
                continue
            try:
                payload = _PlanSlotAnswersPayload.model_validate(part.data)
            except ValidationError:
                continue
            out[payload.tool_call_id] = payload.answers
    return out


def _build_turn_input(
    incoming: ChatRequestBody,
    user_id: UUID,
    *,
    turn_message_id: UUID,
    turn_start_event_id: int,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "conversation_id": incoming.conversation_id,
        "user_id": user_id,
        "site_id": incoming.site_id,
        "mode": incoming.mode,
        "approval_responses": _extract_approval_responses(incoming),
        "plan_slot_answers": _extract_plan_slot_answers(incoming),
        "turn_trace_id": str(uuid4()),
        "turn_created_at": datetime.now(UTC).isoformat(),
        "turn_message_id": turn_message_id,
        "turn_start_event_id": turn_start_event_id,
        "turn_total_tokens": 0,
        "turn_total_cost_usd": Decimal(0),
        "retrieved_memories": [],
    }
    if incoming.is_approval_resume:
        return base
    return {
        **base,
        "user_message_id": incoming.last_user_message_id,
        "user_prompt": incoming.last_user_text,
        "user_parts": [TextUIPart(text=incoming.last_user_text, state="done")],
    }


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
                item.value, strict=False,
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
