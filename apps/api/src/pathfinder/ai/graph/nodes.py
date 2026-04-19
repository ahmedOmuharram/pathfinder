from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from genai_prices import calc_price
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)
from pydantic_ai.usage import RunUsage
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.agents.supervisor import (
    SupervisorDecision,
    SupervisorDeps,
    SupervisorTarget,
    build_supervisor_agent,
)
from pathfinder.ai.conversation.vercel_adapter import PhaseStreamEmitter
from pathfinder.ai.graph.agents import PHASE_AGENTS
from pathfinder.ai.graph.runtime import (
    AgentDeps,
    Context,
    build_node_deps,
    extract_state_delta,
)
from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PhaseName,
    PhaseOutcome,
    PipelineState,
)
from pathfinder.ai.graph.stream_events import (
    phase_change_event,
    phase_start_event,
    supervisor_decision_event,
    turn_qa_event,
    turn_rejected_event,
)
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.platform.logging import get_logger
from pathfinder.services import quota as quota_service
from pathfinder.services import user_preferences as prefs_service

logger = get_logger(__name__)

SUPERVISOR_CALL_BUDGET: int = 15


class PhaseRunError(RuntimeError):
    """Raised when a phase agent stream ends without an ``AgentRunResult``."""


def model_id(agent: Agent[Any, Any]) -> str:
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return model.model_name


def _is_final_result_tool(name: str) -> bool:
    return name == "final_result" or name.startswith("final_result_")


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class _PersistedTextPart(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_to_camel)
    type: Literal["text"] = "text"
    text: str
    state: Literal["done"] = "done"


class _PersistedReasoningPart(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_to_camel)
    type: Literal["reasoning"] = "reasoning"
    text: str
    state: Literal["done"] = "done"


class _PersistedToolCallPart(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_to_camel)
    type: str
    tool_call_id: str
    state: Literal["input-available", "output-available", "output-error"] = (
        "input-available"
    )
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any | None = None
    error_text: str | None = None
    provider_executed: bool = False


def _serialize_tool_return_content(content: Any) -> Any:
    """Coerce a pydantic-ai ToolReturnPart.content into a JSON-safe shape."""
    if content is None or isinstance(content, (str, int, float, bool)):
        return content
    if isinstance(content, BaseModel):
        return content.model_dump(by_alias=True, mode="json")
    if isinstance(content, list):
        return [_serialize_tool_return_content(c) for c in content]
    if isinstance(content, dict):
        return {
            str(k): _serialize_tool_return_content(v) for k, v in content.items()
        }
    try:
        return json.loads(json.dumps(content, default=str))
    except (TypeError, ValueError):
        return str(content)


def _index_tool_returns(
    new_messages: list[ModelMessage],
) -> dict[str, ToolReturnPart]:
    """Map ``tool_call_id`` → ``ToolReturnPart`` across every ModelRequest.

    Tool outputs live on the ``ModelRequest`` that carries the result back into
    the next model turn. Persistence of tool-call parts needs to merge both
    sides — input (from ``ModelResponse``) and output (from ``ModelRequest``) —
    so the reload-from-DB view shows the same result the user saw streamed.
    """
    returns: dict[str, ToolReturnPart] = {}
    for msg in new_messages:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                returns[part.tool_call_id] = part
    return returns


def _convert_assistant_parts(
    new_messages: list[ModelMessage],
) -> list[dict[str, Any]]:
    """Convert pydantic-ai messages into persisted parts, merging tool outputs."""
    tool_returns = _index_tool_returns(new_messages)
    parts: list[dict[str, Any]] = []
    for msg in new_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            converted = _convert_response_part(part, tool_returns)
            if converted is None:
                continue
            parts.append(converted.model_dump(by_alias=True, exclude_none=True))
    return parts


def _convert_response_part(
    part: object,
    tool_returns: dict[str, ToolReturnPart],
) -> _PersistedTextPart | _PersistedReasoningPart | _PersistedToolCallPart | None:
    match part:
        case TextPart(content=content) if content:
            return _PersistedTextPart(text=content)
        case ThinkingPart(content=content) if content:
            return _PersistedReasoningPart(text=content)
        case ToolCallPart() as tc if not _is_final_result_tool(tc.tool_name):
            ret = tool_returns.get(tc.tool_call_id)
            if ret is None:
                return _PersistedToolCallPart(
                    type=f"tool-{tc.tool_name}",
                    tool_call_id=tc.tool_call_id,
                    input=tc.args_as_dict(),
                )
            output = _serialize_tool_return_content(ret.content)
            if ret.outcome == "failed":
                return _PersistedToolCallPart(
                    type=f"tool-{tc.tool_name}",
                    tool_call_id=tc.tool_call_id,
                    state="output-error",
                    input=tc.args_as_dict(),
                    error_text=str(ret.content),
                )
            return _PersistedToolCallPart(
                type=f"tool-{tc.tool_name}",
                tool_call_id=tc.tool_call_id,
                state="output-available",
                input=tc.args_as_dict(),
                output=output,
            )
        case _:
            return None


def _phase_start_part(phase: PhaseName, trace_id: str | None, model: str) -> dict[str, Any]:
    return {
        "type": "data-phase-start",
        "data": {"phase": phase, "traceId": trace_id or "", "model": model},
    }


def _data_part(part_type: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"type": part_type, "data": data}


def _text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text, "state": "done"}


async def _write_turn_message(
    *,
    context: Context,
    state: PipelineState,
    parts: list[dict[str, Any]],
) -> UUID | None:
    if not parts:
        return None
    async with context.db_session_factory() as session:
        repo = MessagesRepository(session)
        await repo.insert_message(
            message_id=state.turn_message_id,
            conversation_id=state.conversation_id,
            role="assistant",
            parts=parts,
            metadata={
                "traceId": state.turn_trace_id,
                "createdAt": state.turn_created_at,
                "siteId": state.site_id,
                "mode": state.mode,
                "usage": {
                    "totalTokens": state.turn_total_tokens,
                    "costUsd": str(state.turn_total_cost_usd),
                },
            },
        )
        await session.commit()
    return state.turn_message_id


def _extract_latest_assistant_prose(new_messages: list[ModelMessage]) -> str:
    for msg in reversed(new_messages):
        if not isinstance(msg, ModelResponse):
            continue
        texts = [p.content for p in msg.parts if isinstance(p, TextPart)]
        prose = "\n".join(t for t in texts if t.strip())
        if prose:
            return prose
    return ""


def _emit_chunk(writer: Any, chunk: BaseChunk) -> None:
    writer(
        {
            "chunk": chunk.model_dump(
                by_alias=True, mode="json", exclude_none=True,
            ),
        },
    )


class _PhaseRunCapture(BaseModel):
    """Terminal state captured from an agent's streaming run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    new_messages: list[ModelMessage] = Field(default_factory=list)
    finish_reason: str = "stop"
    phase_outcome: PhaseOutcome | None = None
    tokens: int = 0
    cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))


def _cost_for_run(
    *,
    usage: RunUsage,
    model_name: str | None,
    provider_name: str | None,
    provider_url: str | None,
) -> Decimal:
    """Mirror of ``ModelResponse.cost()`` but for whole-run ``RunUsage``."""
    if not model_name or not usage.has_values():
        return Decimal(0)
    if provider_url:
        try:
            return calc_price(
                usage, model_name, provider_api_url=provider_url,
            ).total_price
        except LookupError:
            pass
    try:
        return calc_price(
            usage, model_name, provider_id=provider_name,
        ).total_price
    except LookupError:
        return Decimal(0)


def _absorb_run_result(
    event: AgentRunResultEvent, capture: _PhaseRunCapture,
) -> None:
    run_result = event.result
    capture.new_messages = list(run_result.new_messages())
    response = run_result.response
    if response.finish_reason:
        capture.finish_reason = response.finish_reason
    if isinstance(run_result.output, PhaseOutcome):
        capture.phase_outcome = run_result.output
    usage = run_result.usage()
    capture.tokens = usage.total_tokens
    capture.cost_usd = _cost_for_run(
        usage=usage,
        model_name=response.model_name,
        provider_name=response.provider_name,
        provider_url=response.provider_url,
    )


def _build_phase_delta(
    *,
    state: PipelineState,
    deps: AgentDeps,
    phase: PhaseName,
    new_parts: list[dict[str, Any]],
    capture: _PhaseRunCapture,
) -> dict[str, Any]:
    delta = extract_state_delta(deps)
    delta["current_phase"] = phase
    delta["message_history"] = capture.new_messages
    delta["turn_message_parts"] = state.turn_message_parts + new_parts
    delta["turn_total_tokens"] = state.turn_total_tokens + capture.tokens
    delta["turn_total_cost_usd"] = state.turn_total_cost_usd + capture.cost_usd
    if capture.phase_outcome is not None:
        delta["last_phase_outcome"] = capture.phase_outcome
    delta["phase_call_counts"] = {
        **state.phase_call_counts,
        phase: state.phase_call_counts.get(phase, 0) + 1,
    }
    prose = (
        capture.phase_outcome.prose
        if capture.phase_outcome is not None
        else _extract_latest_assistant_prose(capture.new_messages)
    )
    if prose:
        delta["last_assistant_prose"] = prose
    return delta


async def _run_phase_node(
    state: PipelineState,
    runtime: Runtime[Context],
    *,
    phase: PhaseName,
    memories: list[MemoryValue] | None = None,
) -> dict[str, Any]:
    agent: Agent[AgentDeps, Any] = PHASE_AGENTS[phase]
    writer = get_stream_writer()
    effective_memories = memories if memories is not None else state.retrieved_memories
    deps = build_node_deps(state, runtime.context, memories=effective_memories)
    agent_model = model_id(agent)

    phase_message_id = uuid4()
    _emit_chunk(
        writer,
        phase_start_event(
            phase=phase,
            trace_id=state.turn_trace_id or "",
            model=agent_model,
        ),
    )

    capture = _PhaseRunCapture()
    emitter = PhaseStreamEmitter(message_id=str(phase_message_id))

    async def _agent_events() -> Any:
        """Forward agent events, capturing the terminal run result."""
        async for event in agent.run_stream_events(
            state.user_prompt,
            deps=deps,
            message_history=state.message_history or None,
        ):
            if isinstance(event, AgentRunResultEvent):
                _absorb_run_result(event, capture)
            yield event

    try:
        async for v6_chunk in emitter.chunks(_agent_events()):
            _emit_chunk(writer, v6_chunk)
    except Exception:
        logger.exception(
            "phase stream raised",
            phase=phase,
            conversation_id=str(state.conversation_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=agent_model,
            message_history_len=len(state.message_history or []),
        )
        raise

    if not capture.new_messages:
        msg = (
            f"phase {phase} stream ended without AgentRunResult "
            f"(finish_reason={capture.finish_reason})"
        )
        logger.error(
            "phase produced no AgentRunResult",
            phase=phase,
            conversation_id=str(state.conversation_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=agent_model,
            finish_reason=capture.finish_reason,
            message_history_len=len(state.message_history or []),
        )
        raise PhaseRunError(msg)

    new_parts: list[dict[str, Any]] = [
        _phase_start_part(phase, state.turn_trace_id, agent_model),
        *_convert_assistant_parts(capture.new_messages),
    ]
    if capture.phase_outcome is not None and capture.phase_outcome.prose:
        prose_chunk_id = f"phase-prose-{phase_message_id}"
        _emit_chunk(writer, TextStartChunk(id=prose_chunk_id))
        _emit_chunk(
            writer,
            TextDeltaChunk(id=prose_chunk_id, delta=capture.phase_outcome.prose),
        )
        _emit_chunk(writer, TextEndChunk(id=prose_chunk_id))
        new_parts.append(_text_part(capture.phase_outcome.prose))

    return _build_phase_delta(
        state=state, deps=deps, phase=phase, new_parts=new_parts, capture=capture,
    )


async def scoping_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["supervisor"]]:
    memories: list[MemoryValue] = []
    if runtime.context.memory_store is not None and state.user_prompt.strip():
        mem_store = MemoryStore(store=runtime.context.memory_store)
        memories = await retrieve_relevant_memories(
            store=mem_store,
            user_id=state.user_id,
            query=state.user_prompt,
            site_id=state.site_id,
            top_k=8,
        )
    delta = await _run_phase_node(
        state, runtime, phase="scoping", memories=memories,
    )
    delta["retrieved_memories"] = memories
    return Command(goto="supervisor", update=delta)


async def discovery_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["supervisor"]]:
    delta = await _run_phase_node(state, runtime, phase="discovery")
    return Command(goto="supervisor", update=delta)


async def planning_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["supervisor"]]:
    delta = await _run_phase_node(state, runtime, phase="planning")
    return Command(goto="supervisor", update=delta)


async def execution_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["supervisor"]]:
    delta = await _run_phase_node(state, runtime, phase="execution")
    return Command(goto="supervisor", update=delta)


async def verification_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["supervisor"]]:
    delta = await _run_phase_node(state, runtime, phase="verification")
    return Command(goto="supervisor", update=delta)


SupervisorGoto = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
    "finalize_turn",
]

_END: Literal["__end__"] = "__end__"
_FINALIZE: Literal["finalize_turn"] = "finalize_turn"


def _waiting_for_user_reply(state: PipelineState) -> bool:
    """True when the most recent phase has handed the turn back to the user.

    Two independent signals, either sufficient:

    * The phase agent called ``signal_phase_outcome(disposition=awaiting_user)``
      — the explicit, authoritative declaration. Prefer this.
    * Scoping left structured ``blocking_questions`` on the problem frame
      with ``ready_for_wdk_discovery=False`` — the old structural signal,
      kept as a belt-and-suspenders for when the scoping agent populated
      the frame but forgot to call ``signal_phase_outcome``.
    """
    outcome = state.last_phase_outcome
    if outcome is not None and outcome.disposition == PhaseDisposition.AWAITING_USER:
        return True
    frame = state.problem_frame
    if frame is None:
        return False
    if frame.ready_for_wdk_discovery:
        return False
    return len(frame.blocking_questions) > 0


def _render_supervisor_state(state: PipelineState) -> str:
    lines: list[str] = ["Pipeline state:"]
    lines.append(f"- supervisor_call: {state.supervisor_call_count + 1}")
    lines.append(f"- current_phase: {state.current_phase or 'null'}")
    lines.append(f"- has_problem_frame: {state.problem_frame is not None}")
    if state.problem_frame is not None:
        lines.append(
            f"- problem_frame.ready_for_discovery: {state.problem_frame.ready_for_wdk_discovery}",
        )
        lines.append(
            f"- problem_frame.blocking_questions: {len(state.problem_frame.blocking_questions)}",
        )
    lines.append(f"- has_active_plan: {state.active_plan is not None}")
    if state.active_plan is not None:
        lines.append(f"- plan.status: {state.active_plan.status.value}")
        lines.append(f"- plan.step_count: {len(state.active_plan.steps)}")
    if state.phase_call_counts:
        parts = ", ".join(
            f"{p}={n}" for p, n in state.phase_call_counts.items()
        )
        lines.append(f"- phase_call_counts_this_turn: {parts}")
    lines.append(f"- prior_message_count: {len(state.message_history)}")
    if state.last_phase_outcome is not None:
        outcome = state.last_phase_outcome
        lines.append(
            f"- last_phase_outcome: {outcome.disposition.value} — {outcome.reason}",
        )
        if outcome.handoff_to:
            lines.append(f"- last_phase_outcome.handoff_to: {outcome.handoff_to}")
    if state.last_assistant_prose:
        lines.append("- last_phase_prose_to_user: |")
        lines.extend(f"    {prose_line}" for prose_line in state.last_assistant_prose.splitlines())
    return "\n".join(lines)


def _supervisor_history(state: PipelineState) -> list[ModelMessage]:
    sanitized: list[ModelMessage] = []
    for msg in state.message_history:
        if isinstance(msg, ModelRequest):
            user_parts = [p for p in msg.parts if isinstance(p, UserPromptPart)]
            if user_parts:
                sanitized.append(ModelRequest(parts=list(user_parts)))
        elif isinstance(msg, ModelResponse):
            text_parts = [p for p in msg.parts if isinstance(p, TextPart)]
            if text_parts:
                sanitized.append(ModelResponse(parts=list(text_parts)))
    return sanitized


def _supervisor_goto(target: SupervisorTarget) -> SupervisorGoto:
    match target:
        case "end" | "reject" | "question":
            return _FINALIZE
        case _:
            return target


def _supervisor_finalize(
    state: PipelineState,
    reason: str,
    extra_part: dict[str, Any],
) -> Command[SupervisorGoto]:
    return Command(
        goto=_FINALIZE,
        update={
            "last_routing_reason": reason,
            "supervisor_call_count": state.supervisor_call_count + 1,
            "turn_message_parts": [*state.turn_message_parts, extra_part],
        },
    )


async def _resolve_supervisor_model(
    state: PipelineState, runtime: Runtime[Context]
) -> str | None:
    if runtime.context is None:
        return None
    try:
        async with runtime.context.db_session_factory() as session:
            return await prefs_service.resolve_supervisor_model_id(
                session,
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
    except SQLAlchemyError:
        logger.warning(
            "failed to load supervisor pref; falling back to default",
            user_id=str(state.user_id),
            conversation_id=str(state.conversation_id),
        )
        return None


async def supervisor_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[SupervisorGoto]:
    writer = get_stream_writer()

    if state.supervisor_call_count >= SUPERVISOR_CALL_BUDGET:
        logger.warning(
            "supervisor call budget exhausted",
            conversation_id=str(state.conversation_id),
            count=state.supervisor_call_count,
        )
        abort_reason = "supervisor call budget exhausted — safety abort"
        _emit_chunk(
            writer,
            phase_change_event(
                phase="completed", status="failed", reason=abort_reason,
            ),
        )
        return _supervisor_finalize(
            state,
            abort_reason,
            _data_part("data-phase-change", {"phase": "completed", "status": "failed", "reason": abort_reason}),
        )

    if _waiting_for_user_reply(state):
        outcome = state.last_phase_outcome
        halt_reason = (
            outcome.reason
            if outcome is not None and outcome.disposition == PhaseDisposition.AWAITING_USER
            else "waiting for user reply — previous phase left open blocking questions"
        )
        _emit_chunk(writer, supervisor_decision_event(to="end", reason=halt_reason))
        return _supervisor_finalize(
            state,
            halt_reason,
            _data_part("data-supervisor-decision", {"to": "end", "reason": halt_reason}),
        )

    supervisor_model_id = await _resolve_supervisor_model(state, runtime)
    agent = build_supervisor_agent(model_id=supervisor_model_id)
    history = _supervisor_history(state)
    deps = SupervisorDeps(state_block=_render_supervisor_state(state))
    if state.phase_call_counts:
        user_prompt_for_run = "Decide the next action."
    else:
        user_prompt_for_run = state.user_prompt or "(empty user message)"
    try:
        result = await agent.run(
            user_prompt_for_run,
            deps=deps,
            message_history=history,
        )
    except Exception:
        logger.exception(
            "supervisor agent failed; ending turn",
            conversation_id=str(state.conversation_id),
        )
        fallback_reason = "supervisor failed — ending turn"
        _emit_chunk(
            writer,
            phase_change_event(
                phase="completed", status="failed", reason=fallback_reason,
            ),
        )
        return _supervisor_finalize(
            state,
            fallback_reason,
            _data_part("data-phase-change", {"phase": "completed", "status": "failed", "reason": fallback_reason}),
        )

    decision: SupervisorDecision = result.output
    _emit_chunk(
        writer,
        supervisor_decision_event(to=decision.to, reason=decision.reason),
    )
    new_parts: list[dict[str, Any]] = [
        _data_part("data-supervisor-decision", {"to": decision.to, "reason": decision.reason}),
    ]

    if decision.to in ("reject", "question") and state.phase_call_counts:
        logger.info(
            "suppressed supervisor turn-response after phase output",
            conversation_id=str(state.conversation_id),
            original=decision.to,
            phase_call_counts=dict(state.phase_call_counts),
        )
        return Command(
            goto=_FINALIZE,
            update={
                "last_routing_reason": (
                    f"suppressed {decision.to} — phase already responded this turn"
                ),
                "supervisor_call_count": state.supervisor_call_count + 1,
                "turn_message_parts": [*state.turn_message_parts, *new_parts],
            },
        )

    goto = _supervisor_goto(decision.to)

    if decision.to == "reject":
        message_text = decision.rejection_message or ""
        _emit_chunk(
            writer,
            turn_rejected_event(message=message_text, reason=decision.reason),
        )
        new_parts.append(
            _data_part("data-turn-rejected", {"message": message_text, "reason": decision.reason}),
        )
    elif decision.to == "question":
        answer_text = decision.answer or ""
        _emit_chunk(
            writer,
            turn_qa_event(answer=answer_text, reason=decision.reason),
        )
        new_parts.append(
            _data_part("data-turn-qa", {"answer": answer_text, "reason": decision.reason}),
        )

    update: dict[str, Any] = {
        "last_routing_reason": decision.reason,
        "supervisor_call_count": state.supervisor_call_count + 1,
        "turn_message_parts": [*state.turn_message_parts, *new_parts],
    }
    if decision.to in {"reject", "question"}:
        response_text = (
            decision.rejection_message
            if decision.to == "reject"
            else decision.answer
        ) or ""
        update["message_history"] = [
            ModelRequest(parts=[UserPromptPart(content=state.user_prompt)]),
            ModelResponse(parts=[TextPart(content=response_text)]),
        ]
    if decision.to not in ("end", "reject", "question"):
        update["current_phase"] = decision.to

    return Command(goto=goto, update=update)


async def finalize_turn_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[Literal["__end__"]]:
    if runtime.context is not None and state.turn_message_parts:
        try:
            await _write_turn_message(
                context=runtime.context,
                state=state,
                parts=state.turn_message_parts,
            )
        except SQLAlchemyError:
            logger.warning(
                "failed to write turn message",
                conversation_id=str(state.conversation_id),
            )

    if runtime.context is not None and (
        state.turn_total_tokens > 0 or state.turn_total_cost_usd > 0
    ):
        try:
            async with runtime.context.db_session_factory() as session:
                await quota_service.accumulate(
                    session,
                    user_id=state.user_id,
                    tokens=state.turn_total_tokens,
                    cost_usd=state.turn_total_cost_usd,
                )
                await session.commit()
        except SQLAlchemyError:
            logger.warning(
                "failed to accumulate quota usage",
                user_id=str(state.user_id),
                conversation_id=str(state.conversation_id),
            )

    if (
        runtime.context is not None
        and state.current_phase == "verification"
        and runtime.context.memory_store is not None
    ):
        mem_store = MemoryStore(store=runtime.context.memory_store)
        tombstones = TombstoneRepository(
            session_factory=runtime.context.db_session_factory,
        )
        try:
            await auto_write_memories(
                store=mem_store, tombstones=tombstones, state=state,
            )
        except (RuntimeError, ValueError, OSError, SQLAlchemyError) as exc:
            logger.warning("auto-write memories failed: %s", exc)

    return Command(goto=_END, update={"turn_message_parts": []})
