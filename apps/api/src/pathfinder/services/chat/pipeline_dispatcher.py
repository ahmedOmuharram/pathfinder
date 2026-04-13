"""Pipeline dispatcher — drives the 5-phase state machine over AI-SDK SSE.

Entry point for ``POST /api/v2/chat``. One call = one user turn.

The dispatcher owns the outer loop; each phase iteration spins up a
``VercelAIAdapter`` bound to that phase's agent (from ``PHASE_AGENTS``) and
streams native pydantic-ai events through the adapter's translation layer
into AI SDK v6 UI Message Stream chunks, SSE-encoded on the wire.

## Why composable primitives, not ``dispatch_request``

``VercelAIAdapter.dispatch_request`` is a convenient one-liner for
single-agent chats. Our state machine runs 5 agents per turn and threads
``message_history`` across them, so we drop one level:

    adapter = VercelAIAdapter(agent, run_input=..., sdk_version=6)
    stream = adapter.build_event_stream()
    async for chunk in stream.transform_stream(
        adapter.run_stream_native(deps=..., message_history=...)
    ):
        yield stream.encode_event(chunk)       # SSE line

One adapter per phase; one shared ``ctx.message_history`` accumulating
across phases within a turn.

## State machine mapping

The state machine (``pathfinder.ai.orchestration.pipeline``) still uses
legacy event names inherited from the ``finish_*``-tool era
(``finish_scoping``, ``submit_draft``/``approve``, ...). The new
``PhaseDecision.next_action`` literals are semantic (``advance_to_discovery``,
``complete``, ...). Translation lives in ``_state_mapping.events_for_decision``.

## Persistence

- User message: inserted at dispatch start, before the stream opens.
- Assistant message: inserted in the ``finally`` block of the stream
  generator, dumped from the accumulated ``ctx.message_history``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import Request
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai._event_stream import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.request_types import RequestData, UIMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    StartChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
    ToolInputAvailableChunk,
    ToolInputDeltaChunk,
    ToolInputErrorChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response, StreamingResponse

from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.usage import UsageLimits
from pydantic_core import to_jsonable_python

from pathfinder.ai.agents.discovery import DISCOVERY_USAGE_LIMITS
from pathfinder.ai.agents.execution import EXECUTION_USAGE_LIMITS
from pathfinder.ai.agents.planning import PLANNING_USAGE_LIMITS
from pathfinder.ai.agents.scoping import SCOPING_USAGE_LIMITS
from pathfinder.ai.agents.verification import VERIFICATION_USAGE_LIMITS

PHASE_USAGE_LIMITS: dict[str, UsageLimits] = {
    "scoping": SCOPING_USAGE_LIMITS,
    "discovery": DISCOVERY_USAGE_LIMITS,
    "planning": PLANNING_USAGE_LIMITS,
    "execution": EXECUTION_USAGE_LIMITS,
    "verification": VERIFICATION_USAGE_LIMITS,
}

from pathfinder.ai.agents import PHASE_AGENTS
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.pipeline import AgentPipeline, create_pipeline
from pathfinder.domain.strategy.plan_payload import (
    PersistedStrategyGraph,
    StrategyPlanPayload,
)
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import ChatRepository, MessagesRepository
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.platform.logging import get_logger
from pathfinder.services.chat._state_mapping import events_for_decision
from pathfinder.services.chat.chat_context import (
    DispatcherChatContext,
    PhaseDecision,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def dispatch(
    request: Request,
    *,
    session: AsyncSession,
    user_id: UUID,
) -> Response:
    raw_body = await request.body()
    incoming = _parse_request_body(raw_body)
    ctx = await _prepare_context(session, incoming, user_id=user_id)

    adapter: VercelAIAdapter[AgentDeps, Any] = VercelAIAdapter(
        agent=PHASE_AGENTS["scoping"],
        run_input=incoming.ai_sdk_run_input,
        sdk_version=6,
    )

    # ``x-vercel-ai-ui-message-stream: v1`` is a constant set by the adapter —
    # the AI SDK's ``useChat`` hook validates it. We inline the constant
    # rather than instantiating a throwaway event stream just to read the
    # response_headers property.
    headers = {"x-vercel-ai-ui-message-stream": "v1"}
    return StreamingResponse(
        _event_source(ctx=ctx, adapter=adapter, session=session),
        media_type=SSE_CONTENT_TYPE,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _IncomingChatRequest:
    """Normalized view of the client-side ``{id, message, metadata}`` body.

    The frontend's ``prepareSendMessagesRequest`` sends only the latest
    ``message`` (keeps request size bounded; history lives server-side).
    ``VercelAIAdapter`` expects the canonical AI SDK shape
    ``{trigger, id, messages}`` — we translate here.
    """

    chat_id: UUID
    user_message_id: UUID
    user_prompt: str
    user_parts: list[dict[str, Any]]
    ai_sdk_run_input: RequestData
    site_id: str
    mode: str
    pipeline_config: dict[str, Any] | None


def _parse_request_body(raw: bytes) -> _IncomingChatRequest:
    """Validate and decode the raw POST body into a normalized shape."""
    payload = json.loads(raw)
    chat_id = UUID(payload["id"])
    user_message = UIMessage.model_validate(payload["message"])
    metadata = payload.get("metadata") or {}

    ai_sdk_payload = {
        "trigger": "submit-message",
        "id": str(chat_id),
        "messages": [user_message.model_dump(by_alias=True, exclude_none=True)],
    }
    ai_sdk_run_input = VercelAIAdapter.build_run_input(
        json.dumps(ai_sdk_payload).encode("utf-8")
    )

    user_message_id = UUID(user_message.id) if _is_uuid(user_message.id) else uuid4()
    parts_dump = [
        p.model_dump(by_alias=True, exclude_none=True) for p in user_message.parts
    ]

    return _IncomingChatRequest(
        chat_id=chat_id,
        user_message_id=user_message_id,
        user_prompt=_extract_prompt(user_message),
        user_parts=parts_dump,
        ai_sdk_run_input=ai_sdk_run_input,
        site_id=str(metadata.get("siteId") or ""),
        mode=str(metadata.get("mode") or "strategy"),
        pipeline_config=metadata.get("pipeline"),
    )


def _is_uuid(s: str) -> bool:
    try:
        UUID(s)
    except (TypeError, ValueError):
        return False
    return True


def _extract_prompt(message: UIMessage) -> str:
    """Concatenate the text of a ``UIMessage``'s text parts."""
    pieces: list[str] = []
    for part in message.parts:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            pieces.append(text)
    return "".join(pieces)


# ---------------------------------------------------------------------------
# Turn setup — persist user message, build context
# ---------------------------------------------------------------------------


async def _prepare_context(
    session: AsyncSession,
    incoming: _IncomingChatRequest,
    *,
    user_id: UUID,
) -> DispatcherChatContext:
    await _ensure_chat_row(
        session, incoming.chat_id, user_id=user_id, site_id=incoming.site_id,
    )
    repo = MessagesRepository(session)
    raw_history = await repo.latest_assistant_model_history(incoming.chat_id)
    prior_history = (
        ModelMessagesTypeAdapter.validate_python(raw_history) if raw_history else []
    )
    await _persist_user_message(session, incoming)
    await session.commit()

    return DispatcherChatContext(
        chat_id=incoming.chat_id,
        user_id=user_id,
        user_message_id=incoming.user_message_id,
        user_prompt=incoming.user_prompt,
        message_history=list(prior_history),
        site_id=incoming.site_id,
        mode=incoming.mode,
        pipeline_config=incoming.pipeline_config,
    )


async def _ensure_chat_row(
    session: AsyncSession,
    chat_id: UUID,
    *,
    user_id: UUID,
    site_id: str,
) -> None:
    existing = await session.get(Chat, chat_id)
    if existing is None:
        session.add(
            Chat(id=chat_id, user_id=user_id, site_id=site_id, name=""),
        )
        await session.flush()


async def _persist_user_message(
    session: AsyncSession, incoming: _IncomingChatRequest
) -> None:
    """Store the incoming user message (preserves the exact parts array)."""
    repo = MessagesRepository(session)
    await repo.insert_message(
        message_id=incoming.user_message_id,
        chat_id=incoming.chat_id,
        role="user",
        parts=incoming.user_parts,
        metadata={"siteId": incoming.site_id, "mode": incoming.mode},
    )


# ---------------------------------------------------------------------------
# Outer stream generator + inner pipeline loop
# ---------------------------------------------------------------------------


async def _event_source(
    *,
    ctx: DispatcherChatContext,
    adapter: VercelAIAdapter[AgentDeps, Any],
    session: AsyncSession,
) -> AsyncIterator[str]:
    """Yield SSE lines for the turn.

    On any exception: emit an ``ErrorChunk`` but continue to the ``finally``
    block so the assistant message is persisted and the ``[DONE]`` terminator
    goes out (clients treat the absence of ``[DONE]`` as a protocol error).
    On client disconnect (``CancelledError``): skip the ErrorChunk (the wire
    is already closed) but still persist whatever parts accumulated.
    """
    pipeline = create_pipeline()
    # build_event_stream()'s declared return type is the base UIEventStream;
    # VercelAIAdapter always returns a VercelAIEventStream. The narrow type
    # buys us strict typing downstream (e.g. access to ``_finish_reason``).
    event_stream = cast(
        "VercelAIEventStream[AgentDeps, Any]", adapter.build_event_stream()
    )
    cancelled = False
    try:
        async for sse_line in _drive_pipeline(
            ctx=ctx,
            pipeline=pipeline,
            event_stream=event_stream,
            initial_run_input=adapter.run_input,
            session=session,
        ):
            yield sse_line
    except asyncio.CancelledError:
        # Client hung up; nothing to emit (wire closed). We still want to
        # persist whatever parts accumulated, hence the flag + finally.
        logger.info("Chat stream cancelled by client disconnect")
        cancelled = True
    except Exception as exc:
        logger.exception("Pipeline dispatcher failed", exc_info=exc)
        yield _encode(event_stream, ErrorChunk(error_text=str(exc)))
    finally:
        if not cancelled:
            yield "data: [DONE]\n\n"


async def _drive_pipeline(
    *,
    ctx: DispatcherChatContext,
    pipeline: AgentPipeline,
    event_stream: VercelAIEventStream[AgentDeps, Any],
    initial_run_input: RequestData,
    session: AsyncSession,
) -> AsyncIterator[str]:
    deps = await _build_agent_deps(ctx, session)
    trace_id = str(uuid4())
    created_at = datetime.now(UTC).isoformat()
    ctx.turn_trace_id = trace_id
    ctx.turn_created_at = created_at

    while not pipeline.is_done:
        phase = pipeline.current_phase
        if phase not in PHASE_AGENTS:
            msg = f"state machine entered unknown phase: {phase!r}"
            raise RuntimeError(msg)

        ctx.current_phase = phase
        phase_agent: Agent[AgentDeps, Any] = PHASE_AGENTS[phase]
        phase_message_id = uuid4()

        yield _encode(
            event_stream,
            StartChunk(
                message_id=str(phase_message_id),
                message_metadata={
                    "phase": phase,
                    "model": _model_id(phase_agent),
                    "traceId": trace_id,
                    "createdAt": created_at,
                    "chatId": str(ctx.chat_id),
                },
            ),
        )

        phase_new_messages: list[ModelMessage] = []
        async for sse_line, maybe_result in _run_phase_and_yield(
            phase_agent=phase_agent,
            run_input=initial_run_input,
            deps=deps,
            message_history=ctx.message_history,
            usage_limits=PHASE_USAGE_LIMITS.get(phase),
        ):
            if sse_line is not None:
                yield sse_line
            if maybe_result is not None:
                phase_decision, phase_messages = maybe_result
                ctx.record_phase_completion(phase, phase_decision)
                ctx.message_history.extend(phase_messages)
                phase_new_messages = phase_messages
                reply = _reply_text(phase_decision)
                if reply:
                    text_id = str(uuid4())
                    yield _encode(event_stream, TextStartChunk(id=text_id))
                    yield _encode(
                        event_stream, TextDeltaChunk(id=text_id, delta=reply),
                    )
                    yield _encode(event_stream, TextEndChunk(id=text_id))

        yield _encode(
            event_stream,
            FinishChunk(finish_reason=event_stream._finish_reason or "stop"),
        )

        decision_obj = ctx.phase_decisions[phase]
        await _persist_phase_message(
            session=session,
            ctx=ctx,
            phase=phase,
            phase_message_id=phase_message_id,
            phase_messages=phase_new_messages,
            decision=decision_obj,
            phase_agent=phase_agent,
            trace_id=trace_id,
            created_at=created_at,
        )

        events = events_for_decision(decision_obj)
        if not events:
            break
        for event_name in events:
            pipeline.send(event_name)


# ---------------------------------------------------------------------------
# Per-phase run (yields SSE chunks AND the final decision+messages)
# ---------------------------------------------------------------------------


async def _run_phase_and_yield(
    *,
    phase_agent: Agent[AgentDeps, Any],
    run_input: RequestData,
    deps: AgentDeps,
    message_history: list[ModelMessage],
    usage_limits: UsageLimits | None = None,
) -> AsyncIterator[
    tuple[str | None, tuple[PhaseDecision, list[ModelMessage]] | None]
]:
    phase_adapter: VercelAIAdapter[AgentDeps, Any] = VercelAIAdapter(
        agent=phase_agent,
        run_input=run_input,
        sdk_version=6,
    )
    phase_stream = cast(
        "VercelAIEventStream[AgentDeps, Any]", phase_adapter.build_event_stream()
    )

    suppressed_tool_ids: set[str] = set()
    async for chunk in phase_stream.transform_stream(
        phase_adapter.run_stream_native(
            deps=deps,
            message_history=message_history or None,
            usage_limits=usage_limits,
        )
    ):
        if isinstance(chunk, StartChunk | FinishChunk | DoneChunk):
            continue
        if isinstance(chunk, ToolInputStartChunk) and chunk.tool_name == "final_result":
            suppressed_tool_ids.add(chunk.tool_call_id)
            continue
        if (
            isinstance(
                chunk,
                ToolInputDeltaChunk
                | ToolInputAvailableChunk
                | ToolInputErrorChunk
                | ToolOutputAvailableChunk,
            )
            and chunk.tool_call_id in suppressed_tool_ids
        ):
            continue
        yield phase_stream.encode_event(chunk), None

    run_result = phase_stream._result
    if run_result is None:
        msg = "phase exited without an AgentRunResult"
        raise RuntimeError(msg)

    output = run_result.output
    if not _is_phase_decision(output):
        msg = (
            f"phase did not produce a PhaseDecision; got "
            f"{type(output).__name__}"
        )
        raise RuntimeError(msg)

    yield None, (output, list(run_result.new_messages()))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reply_text(decision: PhaseDecision) -> str:
    reason = getattr(decision, "reason", "") or ""
    frame = getattr(decision, "problem_frame", "") or ""
    if frame and frame != reason:
        return f"{reason}\n\n{frame}".strip()
    return reason.strip()


def _is_phase_decision(value: object) -> bool:
    from pathfinder.ai.agents._phase_decisions import (  # noqa: PLC0415
        DiscoveryDecision,
        ExecutionDecision,
        PlanningDecision,
        ScopingDecision,
        VerificationDecision,
    )

    return isinstance(
        value,
        ScopingDecision
        | DiscoveryDecision
        | PlanningDecision
        | ExecutionDecision
        | VerificationDecision,
    )


async def _build_agent_deps(
    ctx: DispatcherChatContext, session: AsyncSession,
) -> AgentDeps:
    chat = await ChatRepository(session).get_by_id(ctx.chat_id)
    persisted: PersistedStrategyGraph | None = None
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

    strategy_session = build_strategy_session(
        site_id=ctx.site_id, strategy_graph=persisted,
    )
    return AgentDeps(
        site_id=ctx.site_id,
        user_id=ctx.user_id,
        strategy_session=strategy_session,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
    )


def _model_id(agent: Agent[AgentDeps, Any]) -> str:
    """Readable model id for metadata (``anthropic:claude-X``, ``mock/...``).

    ``Agent.model`` may be a ``Model`` instance (most common path), a known
    model name string (``'anthropic:claude-sonnet-4-5'``), or ``None``.
    """
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return model.model_name


def _encode(event_stream: VercelAIEventStream[AgentDeps, Any], chunk: BaseChunk) -> str:
    """Encode a chunk as the canonical ``data: ...\\n\\n`` SSE line."""
    return event_stream.encode_event(chunk)


# ---------------------------------------------------------------------------
# Persistence — assistant message written at turn end
# ---------------------------------------------------------------------------


async def _persist_phase_message(
    *,
    session: AsyncSession,
    ctx: DispatcherChatContext,
    phase: str,
    phase_message_id: UUID,
    phase_messages: list[ModelMessage],
    decision: PhaseDecision,
    phase_agent: Agent[AgentDeps, Any],
    trace_id: str,
    created_at: str,
) -> None:
    assistant_parts: list[dict[str, Any]] = []
    if phase_messages:
        ui_messages = VercelAIAdapter.dump_messages(phase_messages)
        for m in ui_messages:
            if m.role != "assistant":
                continue
            for p in m.parts:
                dumped = p.model_dump(by_alias=True, exclude_none=True)
                if dumped.get("type") == "tool-final_result":
                    continue
                assistant_parts.append(dumped)

    reply = _reply_text(decision)
    if reply:
        assistant_parts.append({"type": "text", "text": reply, "state": "done"})

    if not assistant_parts:
        return

    repo = MessagesRepository(session)
    await repo.insert_message(
        message_id=phase_message_id,
        chat_id=ctx.chat_id,
        role="assistant",
        parts=assistant_parts,
        metadata={
            "phase": phase,
            "model": _model_id(phase_agent),
            "traceId": trace_id,
            "createdAt": created_at,
            "siteId": ctx.site_id,
            "mode": ctx.mode,
            "phaseDecision": decision.model_dump(mode="json"),
            "modelHistory": to_jsonable_python(ctx.message_history),
        },
    )
    await session.commit()
