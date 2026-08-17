"""LangGraph node that runs the Lead Agent for a single chat turn.

The Lead is the only LLM in the dispatcher; sub-agents run as tools the
Lead invokes inside its single ``run_stream_events`` call. This module
owns the turn driver (``_drive_lead_stream``) and the node entrypoint
(``lead_node``); run accounting lives in ``_lead_capture``, sub-agent
event rendering in ``_lead_events``, and turn persistence in ``_lead_turn``.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.conversation.vercel_adapter import (
    DeferredToolHint,
    PhaseStreamEmitter,
)
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph._lead_capture import (
    _charge_token_delta,
    _emit_chunk,
    _emit_residual_prose,
    _LeadRunCapture,
    _model_id,
    _persist_residual_quota,
    emit_lead_usage,
    emit_turn_usage,
)
from pathfinder.ai.graph._lead_events import (
    handle_sub_agent_event,
    is_suppressed_sub_agent_chunk,
)
from pathfinder.ai.graph._lead_turn import retrieve_memories
from pathfinder.ai.graph._llm_capture import maybe_wrap_model
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PendingApproval, PipelineState
from pathfinder.ai.graph.stream_events import (
    ledger_update_event,
    memory_retrieved_event,
    turn_status_event,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.lead_agent import LeadResponse, lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, SubAgentRunUsage
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.models.mock import get_mock_model
from pathfinder.ai.models.settings import build_model_settings
from pathfinder.ai.models.tiers import resolve_phase_tier_config
from pathfinder.domain.strategy.staleness import detect_build_staleness
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import ReasoningEffort
from pathfinder.services.strategies.live_counts import read_wdk_step_counts

logger = get_logger(__name__)

LEAD_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=80,
    tool_calls_limit=80,
    total_tokens_limit=4_000_000,
)

_FINALIZE: Literal["finalize_turn"] = "finalize_turn"


def _resume_user_prompt(state: PipelineState) -> str | None:
    """When resuming from a deferred tool, the user's text is already
    captured as the approval/denial — don't re-insert it as a new prompt."""
    if state.pending_approval is None:
        return state.user_prompt
    return None


def _resume_message_history(
    state: PipelineState,
) -> list[ModelMessage] | None:
    """Replay the prior agent run's messages so OpenAI sees the original
    tool-call request when the user approves a deferred tool."""
    approval = state.pending_approval
    if approval is None or not approval.prior_messages_json:
        return None
    return ModelMessagesTypeAdapter.validate_json(approval.prior_messages_json)


def _build_deferred_tool_results(
    state: PipelineState,
) -> DeferredToolResults | None:
    """Resolve a pending approval from the user's structured response."""
    approval = state.pending_approval
    if approval is None:
        return None
    response = state.approval_responses.get(approval.tool_call_id)
    if response is None:
        return None
    if response.approved:
        return DeferredToolResults(approvals={approval.tool_call_id: True})
    return DeferredToolResults(
        approvals={
            approval.tool_call_id: ToolDenied(
                message=response.reason or "User denied the plan.",
            ),
        },
    )


def _absorb_run_result(
    event: AgentRunResultEvent[Any],
    capture: _LeadRunCapture,
) -> None:
    run_result = event.result
    capture.new_messages = list(run_result.new_messages())
    response = run_result.response
    if response.finish_reason:
        capture.finish_reason = response.finish_reason
    output = run_result.output
    if isinstance(output, LeadResponse):
        capture.response = output
    elif isinstance(output, DeferredToolRequests) and output.approvals:
        approval_call = output.approvals[0]
        # Replay the FULL run history (request + the deferred tool call), not
        # just new_messages(): when the Lead's first action is the deferred
        # tool, new_messages() holds only the assistant ToolCallPart with no
        # leading ModelRequest, which pydantic-ai rejects on resume as an
        # empty history. all_messages() always carries the user request.
        capture.pending_approval = PendingApproval(
            phase="lead",
            tool_call_id=approval_call.tool_call_id,
            tool_name=approval_call.tool_name,
            tool_args=approval_call.args_as_dict(),
            plan_id=None,
            prior_messages_json=ModelMessagesTypeAdapter.dump_json(
                list(run_result.all_messages()),
            ).decode(),
        )
    usage = run_result.usage
    capture.tokens = usage.total_tokens
    capture.cost_usd = cost_for_run(
        usage=usage,
        model_name=response.model_name,
        provider_name=response.provider_name,
        provider_url=response.provider_url,
    )


def _deferred_hint(pending: PendingApproval | None) -> DeferredToolHint | None:
    if pending is None:
        return None
    return DeferredToolHint(
        tool_call_id=pending.tool_call_id,
        tool_name=pending.tool_name,
        tool_args=pending.tool_args,
    )


def _resolve_lead_model_context(
    *,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[Any, str]:
    """Swap in the mock for the mock provider, otherwise honor per-request overrides."""
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        if isinstance(lead_agent.model, FunctionModel):
            return contextlib.nullcontext(), "mock:lead"
        return lead_agent.override(model=get_mock_model()), "mock:lead"

    settings = get_settings()
    tier_cfg = resolve_phase_tier_config(
        settings.default_provider, settings.default_tier, "lead"
    )
    tier_model = tier_cfg.model_id if tier_cfg is not None else None
    effective_model = model_override or tier_model or _model_id(lead_agent)
    effort = reasoning_effort or (
        tier_cfg.reasoning_effort if tier_cfg is not None else None
    )
    return (
        lead_agent.override(
            model=maybe_wrap_model(effective_model, "lead"),
            model_settings=build_model_settings(effective_model, thinking=effort),
        ),
        effective_model,
    )


async def _drive_lead_stream(
    *,
    state: PipelineState,
    runtime: Runtime[Context],
    deps: LeadDeps,
    capture: _LeadRunCapture,
    writer: Any,
    message_id: UUID,
) -> None:
    deferred_hint = _deferred_hint(state.pending_approval)
    emitter = PhaseStreamEmitter(
        message_id=str(message_id),
        deferred_hint=deferred_hint,
    )
    deferred_results = _build_deferred_tool_results(state)
    capture.approval_consumed = deferred_results is not None
    resume_prompt = _resume_user_prompt(state)
    resume_history = _resume_message_history(state)
    usage_acc = RunUsage()
    override_ctx, agent_model = _resolve_lead_model_context(
        model_override=runtime.context.phase_models.get("lead"),
        reasoning_effort=runtime.context.phase_reasoning.get("lead"),
    )
    capture.lead_model = agent_model
    sub_agent_tool_calls: dict[str, str] = {}
    _emit_chunk(
        writer,
        turn_status_event(label="Thinking...", waiting_on_llm=True, model=agent_model),
    )

    async def _agent_events() -> AsyncGenerator[
        AgentStreamEvent | AgentRunResultEvent[Any]
    ]:
        async with lead_agent.run_stream_events(
            resume_prompt,
            deps=deps,
            message_history=resume_history,
            deferred_tool_results=deferred_results,
            usage_limits=LEAD_USAGE_LIMITS,
            usage=usage_acc,
        ) as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    _absorb_run_result(event, capture)
                else:
                    handle_sub_agent_event(
                        deps,
                        writer,
                        event,
                        sub_agent_tool_calls,
                        capture.sub_agent_usage_by_call,
                    )
                await _charge_token_delta(
                    runtime.context,
                    state,
                    capture,
                    usage_acc,
                    writer,
                    agent_model,
                )
                yield event

    try:
        with override_ctx:
            async for v6_chunk in emitter.chunks(_agent_events()):
                if is_suppressed_sub_agent_chunk(
                    v6_chunk,
                    sub_agent_tool_calls,
                ):
                    continue
                _emit_chunk(writer, v6_chunk)
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
        "user_intent": deps.intent,
        "operational_spec": deps.state.operational_spec,
        "discovered_searches": dict(deps.state.discovered_searches),
        "verification_digest": deps.state.verification_digest,
        "last_build_outcome": deps.state.last_build_outcome,
        "retrieved_memories": memories,
        "turn_total_tokens": cumulative_tokens,
        "turn_total_cost_usd": cumulative_cost,
    }
    if capture.pending_approval is not None:
        delta["pending_approval"] = capture.pending_approval
    elif capture.approval_consumed:
        delta["pending_approval"] = None
    if capture.response is not None:
        delta["lead_next_state"] = capture.response.next_state
    return delta


async def lead_node(
    state: PipelineState,
    runtime: Runtime[Context],
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

    working_state = state.model_copy(deep=True)
    # The user can edit the strategy between turns, in the graph editor or on
    # the site. WDK owns it, so only WDK can say what it holds now.
    sync_state = runtime.context.strategy_session.sync_state
    working_state.stale_build = detect_build_staleness(
        working_state.last_build_outcome,
        await read_wdk_step_counts(
            sync_state, get_strategy_api(runtime.context.site_id)
        )
        if sync_state is not None
        else {},
    )
    deps = LeadDeps(
        state=working_state,
        intent=state.user_intent,
        runtime=runtime.context,
        retrieved_memories=memories,
        record_sub_agent_usage=_record_sub_agent_usage,
    )

    await _drive_lead_stream(
        state=state,
        runtime=runtime,
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
    _emit_chunk(writer, ledger_update_event(ledger=final_ledger))
    delta = _build_state_delta(
        state=state,
        deps=deps,
        capture=capture,
        memories=memories,
    )
    return Command(goto=_FINALIZE, update=delta)
