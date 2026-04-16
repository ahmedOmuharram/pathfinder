from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from pydantic_ai.usage import UsageLimits
from shared_py.stream_events import StreamEvent
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.agents.discovery import DISCOVERY_USAGE_LIMITS
from pathfinder.ai.agents.execution import EXECUTION_USAGE_LIMITS
from pathfinder.ai.agents.planning import PLANNING_USAGE_LIMITS
from pathfinder.ai.agents.scoping import SCOPING_USAGE_LIMITS
from pathfinder.ai.agents.supervisor import (
    SUPERVISOR_USAGE_LIMITS,
    SupervisorDecision,
    SupervisorTarget,
    build_supervisor_agent,
)
from pathfinder.ai.agents.verification import VERIFICATION_USAGE_LIMITS
from pathfinder.ai.chat.langgraph_adapter import LangGraphEventAdapter
from pathfinder.ai.graph.agents import PHASE_AGENTS
from pathfinder.ai.graph.runtime import (
    AgentDeps,
    Context,
    build_node_deps,
    extract_state_delta,
)
from pathfinder.ai.graph.state import PhaseName, PipelineState
from pathfinder.ai.graph.stream_events import (
    phase_change_event,
    phase_finish_event,
    phase_start_event,
)
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

SUPERVISOR_CALL_BUDGET: int = 15

PHASE_USAGE_LIMITS: dict[PhaseName, UsageLimits] = {
    "scoping": SCOPING_USAGE_LIMITS,
    "discovery": DISCOVERY_USAGE_LIMITS,
    "planning": PLANNING_USAGE_LIMITS,
    "execution": EXECUTION_USAGE_LIMITS,
    "verification": VERIFICATION_USAGE_LIMITS,
}


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
    state: Literal["input-available"] = "input-available"
    input: dict[str, Any] = Field(default_factory=dict)
    provider_executed: bool = False


def _convert_assistant_parts(
    new_messages: list[ModelMessage],
) -> list[dict[str, Any]]:
    """Convert pydantic-ai assistant ModelResponses into persisted parts."""
    parts: list[dict[str, Any]] = []
    for msg in new_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            converted = _convert_response_part(part)
            if converted is None:
                continue
            parts.append(converted.model_dump(by_alias=True, exclude_none=True))
    return parts


def _convert_response_part(
    part: object,
) -> _PersistedTextPart | _PersistedReasoningPart | _PersistedToolCallPart | None:
    match part:
        case TextPart(content=content) if content:
            return _PersistedTextPart(text=content)
        case ThinkingPart(content=content) if content:
            return _PersistedReasoningPart(text=content)
        case ToolCallPart() as tc if not _is_final_result_tool(tc.tool_name):
            return _PersistedToolCallPart(
                type=f"tool-{tc.tool_name}",
                tool_call_id=tc.tool_call_id,
                input=tc.args_as_dict(),
            )
        case _:
            return None


@dataclass(frozen=True)
class PhaseMessage:
    chat_id: UUID
    site_id: str
    mode: str
    phase: PhaseName
    message_id: UUID
    new_messages: list[ModelMessage]
    agent: Agent[Any, Any]
    trace_id: str | None
    created_at: str | None


async def persist_phase_message(context: Context, message: PhaseMessage) -> UUID | None:
    """Persist the assistant message for a phase; return its id when written."""
    assistant_parts = _convert_assistant_parts(message.new_messages)
    if not assistant_parts:
        return None

    async with context.db_session_factory() as session:
        repo = MessagesRepository(session)
        await repo.insert_message(
            message_id=message.message_id,
            chat_id=message.chat_id,
            role="assistant",
            parts=assistant_parts,
            metadata={
                "phase": message.phase,
                "model": model_id(message.agent),
                "traceId": message.trace_id,
                "createdAt": message.created_at,
                "siteId": message.site_id,
                "mode": message.mode,
            },
        )
        await session.commit()
    return message.message_id


def _extract_latest_assistant_prose(new_messages: list[ModelMessage]) -> str:
    for msg in reversed(new_messages):
        if not isinstance(msg, ModelResponse):
            continue
        texts = [p.content for p in msg.parts if isinstance(p, TextPart)]
        prose = "\n".join(t for t in texts if t.strip())
        if prose:
            return prose
    return ""


def _emit_event(writer: Any, event: StreamEvent) -> None:
    writer({"stream_event": event.model_dump(by_alias=True, mode="json")})


async def _run_phase_node(
    state: PipelineState,
    runtime: Runtime[Context],
    *,
    phase: PhaseName,
    memories: list[MemoryValue] | None = None,
) -> dict[str, Any]:
    agent: Agent[AgentDeps, Any] = PHASE_AGENTS[phase]
    usage_limits = PHASE_USAGE_LIMITS[phase]
    writer = get_stream_writer()
    effective_memories = memories if memories is not None else state.retrieved_memories
    deps = build_node_deps(state, runtime.context, memories=effective_memories)

    phase_message_id = uuid4()
    adapter = LangGraphEventAdapter(message_id=str(phase_message_id))

    _emit_event(
        writer,
        phase_start_event(
            phase=phase,
            trace_id=state.turn_trace_id or "",
            model=model_id(agent),
        ),
    )

    new_messages: list[ModelMessage] = []
    finish_reason = "stop"
    try:
        async for event in agent.run_stream_events(
            state.user_prompt,
            deps=deps,
            message_history=state.message_history or None,
            usage_limits=usage_limits,
        ):
            if isinstance(event, AgentRunResultEvent):
                run_result = event.result
                new_messages = list(run_result.new_messages())
                pydantic_reason = run_result.response.finish_reason
                if pydantic_reason:
                    finish_reason = pydantic_reason
                continue
            for stream_event in adapter.handle(event):
                _emit_event(writer, stream_event)
    except Exception:
        logger.exception(
            "phase stream raised",
            phase=phase,
            chat_id=str(state.chat_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=model_id(agent),
            message_history_len=len(state.message_history or []),
        )
        raise

    final = adapter.finalize()
    if final.content or final.tool_calls:
        _emit_event(writer, final)

    _emit_event(writer, phase_finish_event(phase=phase, reason=finish_reason))

    if not new_messages:
        msg = (
            f"phase {phase} stream ended without AgentRunResult "
            f"(finish_reason={finish_reason})"
        )
        logger.error(
            "phase produced no AgentRunResult",
            phase=phase,
            chat_id=str(state.chat_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=model_id(agent),
            finish_reason=finish_reason,
            message_history_len=len(state.message_history or []),
        )
        raise PhaseRunError(msg)

    persisted_id = await persist_phase_message(
        runtime.context,
        PhaseMessage(
            chat_id=state.chat_id,
            site_id=state.site_id,
            mode=state.mode,
            phase=phase,
            message_id=phase_message_id,
            new_messages=new_messages,
            agent=agent,
            trace_id=state.turn_trace_id,
            created_at=state.turn_created_at,
        ),
    )

    _emit_event(
        writer, phase_change_event(phase=phase, status="completed", reason=""),
    )

    delta = extract_state_delta(deps)
    delta["current_phase"] = phase
    delta["message_history"] = new_messages
    delta["phase_call_counts"] = {
        **state.phase_call_counts,
        phase: state.phase_call_counts.get(phase, 0) + 1,
    }
    prose = _extract_latest_assistant_prose(new_messages)
    if prose:
        delta["last_assistant_prose"] = prose
    if phase == "verification" and persisted_id is not None:
        delta["last_verification_message_id"] = persisted_id
    return delta


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
    "scoping", "discovery", "planning", "execution", "verification", "__end__"
]

_END: Literal["__end__"] = "__end__"


def _render_supervisor_context(state: PipelineState) -> str:
    lines: list[str] = ["## Turn State"]
    lines.append(f"- User prompt: {state.user_prompt or '(empty)'}")
    lines.append(f"- Supervisor call #: {state.supervisor_call_count + 1}")
    lines.append(
        f"- Current phase: {state.current_phase or '(none yet this turn)'}"
    )
    if state.phase_call_counts:
        parts = ", ".join(
            f"{p}={n}" for p, n in state.phase_call_counts.items()
        )
        lines.append(f"- Phase call counts this turn: {parts}")
    if state.last_routing_reason:
        lines.append(f"- Previous routing reason: {state.last_routing_reason}")

    if state.problem_frame is not None:
        lines.extend([
            "",
            "## Problem Frame",
            f"- Interpreted goal: {state.problem_frame.interpreted_goal}",
            f"- Ready for WDK discovery: "
            f"{state.problem_frame.ready_for_wdk_discovery}",
            f"- Confidence: {state.problem_frame.confidence:.2f}",
        ])
        if state.problem_frame.blocking_questions:
            lines.append(
                f"- Open blocking questions: "
                f"{len(state.problem_frame.blocking_questions)}"
            )

    if state.active_plan is not None:
        lines.extend([
            "",
            "## Active Plan",
            f"- Status: {state.active_plan.status.value}",
            f"- Steps: {len(state.active_plan.steps)}",
        ])

    if state.last_assistant_prose:
        lines.extend([
            "",
            "## Latest Assistant Prose",
            state.last_assistant_prose[:2000],
        ])

    return "\n".join(lines)


def _supervisor_goto(target: SupervisorTarget) -> SupervisorGoto:
    if target == "end":
        return _END
    return target


async def supervisor_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[SupervisorGoto]:
    writer = get_stream_writer()

    if (
        state.supervisor_call_count == 0
        and state.current_phase is None
        and not state.message_history
    ):
        _emit_event(
            writer,
            phase_change_event(
                phase="scoping", status="started", reason="turn start",
            ),
        )
        return Command(
            goto="scoping",
            update={
                "current_phase": "scoping",
                "last_routing_reason": "turn start",
                "supervisor_call_count": state.supervisor_call_count + 1,
            },
        )

    if state.supervisor_call_count >= SUPERVISOR_CALL_BUDGET:
        logger.warning(
            "supervisor call budget exhausted",
            chat_id=str(state.chat_id),
            count=state.supervisor_call_count,
        )
        abort_reason = "supervisor call budget exhausted — safety abort"
        _emit_event(
            writer,
            phase_change_event(
                phase="completed", status="failed", reason=abort_reason,
            ),
        )
        return Command(
            goto=_END,
            update={
                "last_routing_reason": abort_reason,
                "supervisor_call_count": state.supervisor_call_count + 1,
            },
        )

    agent = build_supervisor_agent()
    rendered = _render_supervisor_context(state)
    try:
        result = await agent.run(
            rendered,
            usage_limits=SUPERVISOR_USAGE_LIMITS,
        )
    except Exception:
        logger.exception(
            "supervisor agent failed; ending turn",
            chat_id=str(state.chat_id),
        )
        fallback_reason = "supervisor failed — ending turn"
        _emit_event(
            writer,
            phase_change_event(
                phase="completed", status="failed", reason=fallback_reason,
            ),
        )
        return Command(
            goto=_END,
            update={
                "last_routing_reason": fallback_reason,
                "supervisor_call_count": state.supervisor_call_count + 1,
            },
        )

    decision: SupervisorDecision = result.output
    goto = _supervisor_goto(decision.to)
    if decision.to == "end":
        status = "completed"
        phase_for_chip: str = "completed"
    else:
        status = "started"
        phase_for_chip = decision.to
    _emit_event(
        writer,
        phase_change_event(
            phase=phase_for_chip, status=status, reason=decision.reason,
        ),
    )

    update: dict[str, Any] = {
        "last_routing_reason": decision.reason,
        "supervisor_call_count": state.supervisor_call_count + 1,
    }
    if decision.to != "end":
        update["current_phase"] = decision.to
    elif state.current_phase == "verification":
        await _finalize_verified_turn(state=state, runtime=runtime)

    return Command(goto=goto, update=update)


async def _finalize_verified_turn(
    *,
    state: PipelineState,
    runtime: Runtime[Context],
) -> None:
    """Mark the verification message as turn-complete and autowrite memories."""
    if state.last_verification_message_id is not None:
        try:
            async with runtime.context.db_session_factory() as session:
                repo = MessagesRepository(session)
                await repo.mark_turn_completed(state.last_verification_message_id)
                await session.commit()
        except SQLAlchemyError:
            logger.warning(
                "failed to mark verification message as turn-complete",
                chat_id=str(state.chat_id),
                message_id=str(state.last_verification_message_id),
            )

    if runtime.context.memory_store is None:
        return
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
