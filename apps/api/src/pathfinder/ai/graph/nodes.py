from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai._event_stream import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.request_types import RequestData, SubmitMessage, UIMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DoneChunk,
    ErrorChunk,
    FinishChunk,
    StartChunk,
    ToolInputAvailableChunk,
    ToolInputDeltaChunk,
    ToolInputErrorChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
)
from pydantic_ai.usage import UsageLimits
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PhaseDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.agents.discovery import DISCOVERY_USAGE_LIMITS
from pathfinder.ai.agents.execution import EXECUTION_USAGE_LIMITS
from pathfinder.ai.agents.planning import PLANNING_USAGE_LIMITS
from pathfinder.ai.agents.scoping import SCOPING_USAGE_LIMITS
from pathfinder.ai.agents.verification import VERIFICATION_USAGE_LIMITS
from pathfinder.ai.graph.agents import PHASE_AGENTS
from pathfinder.ai.graph.runtime import (
    AgentDeps,
    Context,
    build_node_deps,
    extract_state_delta,
)
from pathfinder.ai.graph.state import PhaseName, PipelineState
from pathfinder.ai.graph.stream_chunks import (
    encode_chunk_as_sse,
    phase_finish_chunk,
    phase_start_chunk,
)
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

PHASE_USAGE_LIMITS: dict[PhaseName, UsageLimits] = {
    "scoping": SCOPING_USAGE_LIMITS,
    "discovery": DISCOVERY_USAGE_LIMITS,
    "planning": PLANNING_USAGE_LIMITS,
    "execution": EXECUTION_USAGE_LIMITS,
    "verification": VERIFICATION_USAGE_LIMITS,
}

# Each phase agent uses ``output_type=[str, <Decision>]``; plain-prose outputs
# fall back to a "do not advance" decision so the pipeline halts cleanly and
# the user still sees the text.
_DEFAULT_PHASE_DECISIONS: dict[PhaseName, PhaseDecision] = {
    "scoping": ScopingDecision(next_action="need_more_input"),
    "discovery": DiscoveryDecision(next_action="need_more_input"),
    "planning": PlanningDecision(next_action="request_revision"),
    "execution": ExecutionDecision(next_action="abort"),
    "verification": VerificationDecision(next_action="abort"),
}

_DECISION_TYPES: tuple[type[PhaseDecision], ...] = (
    ScopingDecision,
    DiscoveryDecision,
    PlanningDecision,
    ExecutionDecision,
    VerificationDecision,
)


def _resolve_decision(raw_output: object, phase: PhaseName) -> PhaseDecision:
    """Return the structured decision, or the phase's safe default for prose."""
    if isinstance(raw_output, _DECISION_TYPES):
        return raw_output
    return _DEFAULT_PHASE_DECISIONS[phase]


class PhaseRunError(RuntimeError):
    """Raised when a phase agent stream ends without an ``AgentRunResult``."""


def build_run_input(state: PipelineState) -> RequestData:
    user_message = UIMessage.model_validate(
        {
            "id": str(state.user_message_id) if state.user_message_id else str(uuid4()),
            "role": "user",
            "parts": state.user_parts,
        }
    )
    return SubmitMessage(
        trigger="submit-message",
        id=str(state.chat_id),
        messages=[user_message],
    )


def model_id(agent: Agent[Any, Any]) -> str:
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return model.model_name


def _is_final_result_tool(name: str) -> bool:
    """True for the pydantic-ai structured-output tools.

    Plain structured output uses ``final_result``; output unions like
    ``output_type=[str, Decision]`` use ``final_result_<TypeName>``.
    """
    return name == "final_result" or name.startswith("final_result_")


def is_chunk_to_drop(chunk: BaseChunk, suppressed_tool_ids: set[str]) -> bool:
    if isinstance(chunk, StartChunk | FinishChunk | DoneChunk):
        return True
    if isinstance(chunk, ToolInputStartChunk) and _is_final_result_tool(
        chunk.tool_name,
    ):
        suppressed_tool_ids.add(chunk.tool_call_id)
        return True
    return bool(
        isinstance(
            chunk,
            ToolInputDeltaChunk
            | ToolInputAvailableChunk
            | ToolInputErrorChunk
            | ToolOutputAvailableChunk,
        )
        and chunk.tool_call_id in suppressed_tool_ids
    )


@dataclass(frozen=True)
class PhaseMessage:
    chat_id: UUID
    site_id: str
    mode: str
    phase: PhaseName
    message_id: UUID
    new_messages: list[ModelMessage]
    decision: PhaseDecision
    agent: Agent[Any, Any]
    trace_id: str | None
    created_at: str | None


async def persist_phase_message(context: Context, message: PhaseMessage) -> None:
    assistant_parts: list[dict[str, Any]] = []
    if message.new_messages:
        ui_messages = VercelAIAdapter.dump_messages(message.new_messages)
        for ui in ui_messages:
            if ui.role != "assistant":
                continue
            for part in ui.parts:
                dumped = part.model_dump(by_alias=True, exclude_none=True)
                if dumped.get("type") == "tool-final_result":
                    continue
                assistant_parts.append(dumped)

    if not assistant_parts:
        return

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
                "phaseDecision": message.decision.model_dump(mode="json"),
            },
        )
        await session.commit()


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
    # Prefer freshly retrieved memories (scoping); otherwise use the batch
    # the scoping phase persisted to state so downstream agents see them too.
    effective_memories = memories if memories is not None else state.retrieved_memories
    deps = build_node_deps(state, runtime.context, memories=effective_memories)
    run_input = build_run_input(state)

    adapter: VercelAIAdapter[AgentDeps, Any] = VercelAIAdapter(
        agent=agent,
        run_input=run_input,
        sdk_version=6,
    )
    event_stream = cast(
        "VercelAIEventStream[AgentDeps, Any]", adapter.build_event_stream()
    )

    phase_message_id = uuid4()
    writer(
        {
            "sse": encode_chunk_as_sse(
                phase_start_chunk(
                    message_id=str(phase_message_id),
                    phase=phase,
                    model_name=model_id(agent),
                    trace_id=state.turn_trace_id or "",
                    created_at=state.turn_created_at or "",
                    chat_id=str(state.chat_id),
                )
            )
        }
    )

    suppressed_tool_ids: set[str] = set()
    error_text: str | None = None
    try:
        async for chunk in event_stream.transform_stream(
            adapter.run_stream_native(
                deps=deps,
                message_history=state.message_history or None,
                usage_limits=usage_limits,
            )
        ):
            if isinstance(chunk, ErrorChunk):
                # pydantic-ai's UI stream swallows run-time exceptions and
                # emits them as ErrorChunks. Capture the message so the
                # PhaseRunError below carries the real cause instead of a
                # blank "no result", and log it with full context.
                error_text = chunk.error_text
                logger.error(
                    "phase stream error chunk",
                    phase=phase,
                    chat_id=str(state.chat_id),
                    user_id=str(state.user_id),
                    trace_id=state.turn_trace_id,
                    model=model_id(agent),
                    error_text=chunk.error_text,
                )
            if is_chunk_to_drop(chunk, suppressed_tool_ids):
                continue
            writer({"sse": event_stream.encode_event(chunk)})
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

    finish_reason = event_stream._finish_reason or "stop"
    writer({"sse": encode_chunk_as_sse(phase_finish_chunk(reason=finish_reason))})

    run_result = event_stream._result
    if run_result is None:
        detail = f": {error_text}" if error_text else ""
        msg = (
            f"phase {phase} stream errored without AgentRunResult "
            f"(finish_reason={finish_reason}){detail}"
        )
        logger.error(
            "phase produced no AgentRunResult",
            phase=phase,
            chat_id=str(state.chat_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=model_id(agent),
            finish_reason=finish_reason,
            error_text=error_text,
            message_history_len=len(state.message_history or []),
        )
        raise PhaseRunError(msg)

    decision = _resolve_decision(run_result.output, phase)
    new_messages = list(run_result.new_messages())

    await persist_phase_message(
        runtime.context,
        PhaseMessage(
            chat_id=state.chat_id,
            site_id=state.site_id,
            mode=state.mode,
            phase=phase,
            message_id=phase_message_id,
            new_messages=new_messages,
            decision=decision,
            agent=agent,
            trace_id=state.turn_trace_id,
            created_at=state.turn_created_at,
        ),
    )

    delta = extract_state_delta(deps)
    delta["current_phase"] = phase
    delta["phase_decisions"] = {**state.phase_decisions, phase: decision}
    delta["message_history"] = new_messages
    delta["retry_counts"] = {
        **state.retry_counts,
        phase: state.retry_counts.get(phase, 0) + 1,
    }
    return delta


async def scoping_node(
    state: PipelineState, runtime: Runtime[Context]
) -> dict[str, Any]:
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
    # Persist for downstream phases — discovery/planning/execution/verification
    # read from ``state.retrieved_memories`` via the default branch in
    # ``_run_phase_node``.
    delta["retrieved_memories"] = memories
    return delta


async def discovery_node(
    state: PipelineState, runtime: Runtime[Context]
) -> dict[str, Any]:
    return await _run_phase_node(state, runtime, phase="discovery")


async def planning_node(
    state: PipelineState, runtime: Runtime[Context]
) -> dict[str, Any]:
    return await _run_phase_node(state, runtime, phase="planning")


async def execution_node(
    state: PipelineState, runtime: Runtime[Context]
) -> dict[str, Any]:
    return await _run_phase_node(state, runtime, phase="execution")


async def verification_node(
    state: PipelineState, runtime: Runtime[Context]
) -> dict[str, Any]:
    delta = await _run_phase_node(state, runtime, phase="verification")
    decision = delta["phase_decisions"]["verification"]
    if (
        isinstance(decision, VerificationDecision)
        and decision.next_action == "complete"
        and runtime.context.memory_store is not None
    ):
        await _safe_auto_write(state=state, delta=delta, runtime=runtime)
    return delta


async def _safe_auto_write(
    *,
    state: PipelineState,
    delta: dict[str, Any],
    runtime: Runtime[Context],
) -> None:
    """Best-effort autowrite — never fails the verification turn.

    Autowrite is a side effect: if embedding/IO/DB hiccups, log and return.
    """
    if runtime.context.memory_store is None:
        return
    mem_store = MemoryStore(store=runtime.context.memory_store)
    tombstones = TombstoneRepository(
        session_factory=runtime.context.db_session_factory,
    )
    merged_state = state.model_copy(update={
        k: v for k, v in delta.items() if k in PipelineState.model_fields
    })
    try:
        await auto_write_memories(
            store=mem_store, tombstones=tombstones, state=merged_state,
        )
    except (RuntimeError, ValueError, OSError, SQLAlchemyError) as exc:
        logger.warning("auto-write memories failed: %s", exc)
