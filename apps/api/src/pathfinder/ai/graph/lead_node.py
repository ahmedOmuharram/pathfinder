"""LangGraph node that runs the Lead Agent for a single chat turn.

The Lead is the only LLM in the dispatcher; sub-agents run as tools the
Lead invokes inside its single ``run_stream_events`` call. This module owns
the turn driver (``_drive_lead_stream``) and ``make_lead_node``, which binds
the driver to the hooks the graph was built with; run accounting lives in
``_lead_capture``, sub-agent event rendering in ``_lead_events``, model
selection in ``_lead_model``, and memory retrieval plus approval resolution in
``_lead_turn``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from assistant_core.capabilities.repetition_guard import (
    RepetitionGuard,
    ToolRepetitionGuard,
)
from assistant_core.conversation.vercel_adapter import PhaseStreamEmitter
from assistant_core.cost import cost_for_run
from assistant_core.graph import approvals
from assistant_core.graph.emit import emit_chunk, emit_turn_usage
from assistant_core.graph.pre_turn import PreTurnHook
from assistant_core.graph.stream_events import (
    memory_retrieved_event,
    turn_status_event,
)
from assistant_core.graph.turn_agent import TurnAgentFactory
from assistant_core.memory.schemas import MemoryValue
from assistant_core.platform.logging import get_logger
from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolResultEvent,
)
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.graph._lead_capture import (
    _charge_token_delta,
    _emit_residual_prose,
    _LeadRunCapture,
    _persist_residual_quota,
    emit_lead_usage,
)
from pathfinder.ai.graph._lead_events import (
    handle_sub_agent_event,
    is_suppressed_sub_agent_chunk,
)
from pathfinder.ai.graph._lead_model import resolve_lead_model_context
from pathfinder.ai.graph._lead_turn import (
    ApprovalResolution,
    pending_approval,
    resolve_pending_approval,
    retrieve_memories,
)
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.graph.stream_events import ledger_update_event
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.lead_agent import LeadAgent, LeadResponse
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, SubAgentRunUsage

logger = get_logger(__name__)

LEAD_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=80,
    tool_calls_limit=80,
    total_tokens_limit=4_000_000,
)

_FINALIZE: Literal["finalize_turn"] = "finalize_turn"


class LeadNode(Protocol):
    """The call shape LangGraph invokes the turn node with."""

    def __call__(
        self,
        state: PipelineState,
        *,
        runtime: Runtime[Context],
    ) -> Awaitable[Command[Literal["finalize_turn"]]]: ...


def _run_prompt(state: PipelineState, resolution: ApprovalResolution) -> str | None:
    """The message the Lead's run starts from.

    A turn that resumes a deferred tool carries the user's answer, not a new
    prompt, unless the user answered by typing instead of clicking.
    """
    if resolution.user_prompt:
        return resolution.user_prompt
    if state.pending_approval is not None:
        return None
    return state.user_prompt


def _absorb_run_result(
    event: AgentRunResultEvent[Any],
    capture: _LeadRunCapture,
    deps: LeadDeps,
) -> None:
    run_result = event.result
    capture.new_messages = list(run_result.new_messages())
    response = run_result.response
    if response.finish_reason:
        capture.finish_reason = response.finish_reason
    output = run_result.output
    if isinstance(output, LeadResponse):
        capture.response = output
    elif isinstance(output, DeferredToolRequests):
        capture.pending_approval = pending_approval(
            output=output,
            deps=deps,
            messages=list(run_result.all_messages()),
        )
    usage = run_result.usage
    capture.tokens = usage.total_tokens
    capture.cost_usd = cost_for_run(
        usage=usage,
        model_name=response.model_name,
        provider_name=response.provider_name,
        provider_url=response.provider_url,
    )


def _emit_unless_suppressed(
    writer: Any,
    chunk: BaseChunk,
    sub_agent_tool_calls: dict[str, str],
) -> None:
    """Write one chunk, unless a sub-agent already renders that call itself."""
    if is_suppressed_sub_agent_chunk(chunk, sub_agent_tool_calls):
        return
    emit_chunk(writer, chunk)


def _guard_stopped_on(
    event: AgentStreamEvent | AgentRunResultEvent[Any],
    guard: ToolRepetitionGuard,
) -> bool:
    """True for the result of the call whose refusal ends the run."""
    return (
        isinstance(event, FunctionToolResultEvent)
        and event.tool_call_id == guard.stopped_call_id
    )


def _absorb_loop_stop(
    capture: _LeadRunCapture,
    guard: ToolRepetitionGuard,
) -> None:
    """Say why the turn ended when the guard stopped the Lead's own run."""
    if not guard.stopped_call_id or capture.response is not None:
        return
    capture.response = LeadResponse(
        prose=(
            "I stopped this turn: I was repeating the same lookup and making "
            "no progress. Tell me what to try instead and I will carry on."
        ),
        next_state="await_user",
    )


async def _drive_lead_stream(
    *,
    state: PipelineState,
    agent: LeadAgent,
    deps: LeadDeps,
    capture: _LeadRunCapture,
    writer: Any,
    message_id: UUID,
) -> None:
    resolution = await resolve_pending_approval(state=state, deps=deps)
    if resolution.still_pending is not None:
        # The sub-agent asked for another approval. The Lead's run is untouched,
        # so the turn ends on the new question instead of resuming it.
        capture.pending_approval = resolution.still_pending
        return
    approval = state.pending_approval
    emitter = PhaseStreamEmitter(
        message_id=str(message_id),
        deferred_hint=(
            approvals.deferred_hint(approval) if approval is not None else None
        ),
    )
    deferred_results = resolution.results
    capture.approval_consumed = deferred_results is not None
    resume_prompt = _run_prompt(state, resolution)
    resume_messages = (
        approvals.resume_history(approval) if approval is not None else None
    )
    usage_acc = RunUsage()
    override_ctx, agent_model = resolve_lead_model_context(
        agent,
        model_override=deps.runtime.phase_models.get("lead"),
        reasoning_effort=deps.runtime.phase_reasoning.get("lead"),
    )
    capture.lead_model = agent_model
    sub_agent_tool_calls: dict[str, str] = {}
    emit_chunk(
        writer,
        turn_status_event(label="Thinking...", waiting_on_llm=True, model=agent_model),
    )

    guard = deps.tool_repetition_guard

    async def _agent_events() -> AsyncGenerator[
        AgentStreamEvent | AgentRunResultEvent[Any]
    ]:
        async with agent.run_stream_events(
            resume_prompt,
            deps=deps,
            message_history=resume_messages,
            deferred_tool_results=deferred_results,
            capabilities=[RepetitionGuard(guard=guard)],
            usage_limits=LEAD_USAGE_LIMITS,
            usage=usage_acc,
        ) as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    _absorb_run_result(event, capture, deps)
                else:
                    handle_sub_agent_event(
                        deps,
                        writer,
                        event,
                        sub_agent_tool_calls,
                        capture.sub_agent_usage_by_call,
                    )
                await _charge_token_delta(
                    deps.runtime,
                    state,
                    capture,
                    usage_acc,
                    writer,
                    agent_model,
                )
                yield event
                if _guard_stopped_on(event, guard):
                    return

    try:
        with override_ctx:
            async for v6_chunk in emitter.chunks(_agent_events()):
                _emit_unless_suppressed(writer, v6_chunk, sub_agent_tool_calls)
    except UsageLimitExceeded as exc:
        logger.warning(
            "lead exceeded usage cap",
            conversation_id=str(state.conversation_id),
            error=str(exc),
        )
        capture.response = LeadResponse(
            prose=(
                f"Investigation paused: hit safety cap ({exc}). "
                "Refine the request or approve a continuation."
            ),
            next_state="await_user",
        )
    except GraphBubbleUp:
        raise
    except Exception:
        logger.exception(
            "lead stream raised",
            conversation_id=str(state.conversation_id),
            user_id=str(state.user_id),
        )
        raise
    _absorb_loop_stop(capture, guard)


def _domain_delta(
    *,
    deps: LeadDeps,
    capture: _LeadRunCapture,
) -> StrategyDomainState:
    domain = deps.state.domain
    next_state = (
        capture.response.next_state
        if capture.response is not None
        else domain.lead_next_state
    )
    return domain.model_copy(
        update={
            "user_intent": deps.intent,
            "discovered_searches": dict(domain.discovered_searches),
            "lead_next_state": next_state,
            # Staleness is measured against the live strategy every turn.
            "stale_build": None,
        },
    )


def _build_state_delta(
    *,
    state: PipelineState,
    deps: LeadDeps,
    capture: _LeadRunCapture,
    memories: list[MemoryValue],
) -> dict[str, Any]:
    cumulative_tokens = (
        state.turn_total_tokens + capture.tokens + capture.sub_agent_tokens
    )
    cumulative_cost = (
        state.turn_total_cost_usd + capture.cost_usd + capture.sub_agent_cost
    )
    delta: dict[str, Any] = {
        "domain": _domain_delta(deps=deps, capture=capture),
        "retrieved_memories": memories,
        "turn_total_tokens": cumulative_tokens,
        "turn_total_cost_usd": cumulative_cost,
    }
    if capture.pending_approval is not None:
        delta["pending_approval"] = capture.pending_approval
    elif capture.approval_consumed:
        delta["pending_approval"] = None
    return delta


async def _run_lead_turn(
    state: PipelineState,
    runtime: Runtime[Context],
    *,
    pre_turn: PreTurnHook[PipelineState, Context],
    build_agent: TurnAgentFactory[LeadAgent],
) -> Command[Literal["finalize_turn"]]:
    writer = get_stream_writer()
    if state.pending_approval is not None:
        memories = list(state.retrieved_memories)
    else:
        stored = await retrieve_memories(state, runtime)
        memories = [s.value for s in stored]
        if stored:
            writer(memory_retrieved_event(memories=stored))
    capture = _LeadRunCapture()
    message_id = uuid4()

    def _record_sub_agent_usage(usage_info: SubAgentRunUsage) -> None:
        cost = cost_for_run(
            usage=usage_info.usage,
            model_name=usage_info.model_name,
            provider_name=usage_info.provider_name,
            provider_url=usage_info.provider_url,
        )
        capture.sub_agent_tokens += usage_info.usage.total_tokens
        capture.sub_agent_cost += cost
        capture.sub_agent_usage_by_call[usage_info.parent_tool_call_id] = (
            usage_info.usage.total_tokens,
            str(cost),
        )
        total_tokens, cost_usd = capture.live_totals(state)
        emit_turn_usage(writer, total_tokens, cost_usd)

    working_state = await pre_turn(state, runtime.context)
    deps = LeadDeps(
        state=working_state,
        intent=state.domain.user_intent,
        runtime=runtime.context,
        retrieved_memories=memories,
        record_sub_agent_usage=_record_sub_agent_usage,
    )

    await _drive_lead_stream(
        state=state,
        agent=build_agent(),
        deps=deps,
        capture=capture,
        writer=writer,
        message_id=message_id,
    )

    if capture.response is None and capture.pending_approval is None:
        capture.response = LeadResponse(
            prose=(
                "I couldn't produce a response for this turn. Please "
                "rephrase or provide more context and I'll try again."
            ),
            next_state="await_user",
        )

    _emit_residual_prose(writer, capture, message_id=message_id)
    residual_tokens, residual_cost = capture.residual_totals(state)
    final_sub_agent_tokens = capture.sub_agent_tokens
    final_sub_agent_cost = capture.sub_agent_cost
    await _persist_residual_quota(runtime.context, state, capture)
    capture.sub_agent_tokens = final_sub_agent_tokens
    capture.sub_agent_cost = final_sub_agent_cost
    emit_turn_usage(writer, residual_tokens, residual_cost)
    emit_lead_usage(writer, capture.lead_model, capture.tokens, str(capture.cost_usd))
    final_ledger = derive_ledger(deps.state, deps.intent)
    emit_chunk(writer, ledger_update_event(ledger=final_ledger))
    delta = _build_state_delta(
        state=state,
        deps=deps,
        capture=capture,
        memories=memories,
    )
    return Command(goto=_FINALIZE, update=delta)


def make_lead_node(
    *,
    pre_turn: PreTurnHook[PipelineState, Context],
    build_agent: TurnAgentFactory[LeadAgent],
) -> LeadNode:
    """Bind the turn driver to the hooks the product wired at build time."""

    async def lead_node(
        state: PipelineState,
        runtime: Runtime[Context],
    ) -> Command[Literal["finalize_turn"]]:
        return await _run_lead_turn(
            state,
            runtime,
            pre_turn=pre_turn,
            build_agent=build_agent,
        )

    return lead_node
