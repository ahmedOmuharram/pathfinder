"""LangGraph node that runs the Lead Agent for a single chat turn.

Replaces the supervisor + per-phase nodes. The Lead is the only LLM in
the dispatcher; sub-agents run as tools the Lead invokes inside its
single ``run_stream_events`` call. The node:

  1. Retrieves cross-thread memories on a fresh user prompt.
  2. Builds ``LeadDeps`` (mutable working ``PipelineState`` + intent +
     runtime context + memories).
  3. Streams the Lead's events through ``PhaseStreamEmitter`` so v6
     chunks reach the user; mid-stream we re-derive the Ledger after
     each sub-agent tool call and emit a ``data-ledger-update`` chunk.
  4. Captures terminal output (``LeadResponse`` or ``DeferredToolRequests``).
  5. Persists token-delta cost mid-stream and a residual at end.
  6. Returns a ``Command(goto="finalize_turn", update=delta)``.

This module replaces ``ai/graph/nodes.py``'s phase-orchestration code in
the Stage-5 architecture; old phase nodes remain in ``nodes.py`` until
Stage 6 deletes them along with ``current_phase`` / ``last_phase_outcome``
state fields.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    RetryPromptPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.conversation.event_stream import fetch_chunks_after
from pathfinder.ai.conversation.ui_message_reducer import reduce_chunks
from pathfinder.ai.conversation.vercel_adapter import (
    DeferredToolHint,
    PhaseStreamEmitter,
)
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import (
    PendingApproval,
    PipelineState,
)
from pathfinder.ai.graph.stream_events import (
    SubAgentCallPayload,
    ledger_update_event,
    sub_agent_call_event,
    turn_status_event,
    turn_usage_event,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.lead_agent import LeadResponse, lead_agent
from pathfinder.ai.lead.sub_agent_tools import (
    LeadDeps,
    SubAgentRunUsage,
    sub_agent_model_id,
)
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.models.mock import get_mock_model
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.repositories._message_metadata import MessageMetadata
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger
from pathfinder.services import quota as quota_service

logger = get_logger(__name__)

LEAD_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=80,
    tool_calls_limit=80,
    total_tokens_limit=4_000_000,
)

_FINALIZE: Literal["finalize_turn"] = "finalize_turn"

_SUB_AGENT_TOOL_TO_PHASE: dict[str, str] = {
    "scope_problem": "scoping",
    "discover_searches": "discovery",
    "build_plan": "planning",
    "execute_plan": "execution",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}
_SUB_AGENT_TOOL_NAMES = frozenset(_SUB_AGENT_TOOL_TO_PHASE.keys())

_SUPPRESSED_SUB_AGENT_CHUNK_TYPES = frozenset({
    "tool-input-start",
    "tool-input-delta",
    "tool-input-available",
    "tool-output-available",
    "tool-input-error",
})


@dataclass
class _LeadRunCapture:
    """Terminal state captured from the Lead agent's streaming run."""

    new_messages: list[ModelMessage] = field(default_factory=list)
    finish_reason: str = "stop"
    response: LeadResponse | None = None
    tokens: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal(0))
    charged_input_tokens: int = 0
    charged_output_tokens: int = 0
    charged_cache_read_tokens: int = 0
    charged_cache_write_tokens: int = 0
    charged_cost: Decimal = field(default_factory=lambda: Decimal(0))
    sub_agent_tokens: int = 0
    sub_agent_cost: Decimal = field(default_factory=lambda: Decimal(0))
    pending_approval: PendingApproval | None = None
    approval_consumed: bool = False
    prose_already_streamed: bool = False

    @property
    def charged_tokens(self) -> int:
        return self.charged_input_tokens + self.charged_output_tokens

    @property
    def cumulative_tokens(self) -> int:
        return self.charged_tokens + self.sub_agent_tokens

    @property
    def cumulative_cost(self) -> Decimal:
        return self.charged_cost + self.sub_agent_cost


def _emit_chunk(writer: Any, chunk: BaseChunk) -> None:
    writer(
        {
            "chunk": chunk.model_dump(
                by_alias=True, mode="json", exclude_none=True,
            ),
        },
    )


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
    event: AgentRunResultEvent[Any], capture: _LeadRunCapture,
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
        capture.pending_approval = PendingApproval(
            phase="lead",
            tool_call_id=approval_call.tool_call_id,
            tool_name=approval_call.tool_name,
            tool_args=approval_call.args_as_dict(),
            plan_id=None,
            prior_messages_json=ModelMessagesTypeAdapter.dump_json(
                capture.new_messages,
            ).decode(),
        )
    usage = run_result.usage()
    capture.tokens = usage.total_tokens
    capture.cost_usd = cost_for_run(
        usage=usage,
        model_name=response.model_name,
        provider_name=response.provider_name,
        provider_url=response.provider_url,
    )


def _is_suppressed_sub_agent_chunk(
    chunk: BaseChunk, sub_agent_tool_calls: dict[str, str],
) -> bool:
    """Hide the default tool-input/output chunks for sub-agent calls so
    the rich ``data-sub-agent-call`` card is the only inline rendering."""
    chunk_type = getattr(chunk, "type", None)
    if chunk_type not in _SUPPRESSED_SUB_AGENT_CHUNK_TYPES:
        return False
    tool_call_id = getattr(chunk, "tool_call_id", None)
    if not isinstance(tool_call_id, str):
        return False
    return tool_call_id in sub_agent_tool_calls


def _summarize_sub_agent_call_args(args: dict[str, Any]) -> str:
    """One-line input summary for the SubAgentCallCard 'started' state."""
    reason = args.get("reason")
    intent_summary = args.get("intent_summary")
    hints = args.get("hints")
    parts: list[str] = []
    if isinstance(reason, str) and reason:
        parts.append(reason)
    if isinstance(intent_summary, str) and intent_summary:
        parts.append(f"intent: {intent_summary}")
    if isinstance(hints, str) and hints:
        parts.append(f"hints: {hints}")
    return " · ".join(parts)[:280]


def _summarize_sub_agent_result(result: ToolReturnPart) -> str:
    """One-line result summary for the SubAgentCallCard 'completed' state."""
    content = result.content
    if isinstance(content, BaseModel):
        return _summarize_delta(content)
    if isinstance(content, dict):
        return _summarize_delta_dict(content)
    return str(content)[:280]


def _summarize_delta(delta: BaseModel) -> str:
    return _summarize_delta_dict(delta.model_dump())


def _summarize_delta_dict(data: dict[str, Any]) -> str:
    """Compact one-liner from a sub-agent's typed delta payload."""
    if "frame" in data:
        frame = data.get("frame") or {}
        return (
            f"frame ready={frame.get('ready_for_wdk_discovery', False)} "
            f"questions={len(frame.get('blocking_questions', []))}"
        )
    if "selections" in data or "fit_reports" in data:
        sels = data.get("selections") or {}
        return f"selected {len(sels)} searches"
    if "plan" in data:
        plan = data.get("plan") or {}
        steps = plan.get("steps") or []
        return f"plan with {len(steps)} step(s)"
    if "outcome" in data:
        outcome = data.get("outcome") or {}
        return (
            f"pushed={len(outcome.get('pushed_step_ids') or [])} "
            f"failed={len(outcome.get('failed_steps') or [])}"
        )
    if "digest" in data:
        digest = data.get("digest") or {}
        return f"verification success={digest.get('success', False)}"
    return ""


def _handle_sub_agent_event(
    deps: LeadDeps,
    writer: Any,
    event: AgentStreamEvent,
    sub_agent_tool_calls: dict[str, str],
) -> None:
    """Emit ``data-sub-agent-call`` (started/completed/failed) and refresh
    the Ledger when a sub-agent tool runs.

    ``sub_agent_tool_calls`` maps tool_call_id → tool_name for the calls
    we've classified as sub-agents; the chunk-emission loop reads it to
    suppress the default tool-input/output chunks for those calls.
    """
    if isinstance(event, FunctionToolCallEvent):
        tool_name = event.part.tool_name
        if tool_name not in _SUB_AGENT_TOOL_NAMES:
            return
        sub_agent_tool_calls[event.tool_call_id] = tool_name
        _emit_chunk(
            writer,
            sub_agent_call_event(SubAgentCallPayload(
                tool_call_id=event.tool_call_id,
                sub_agent=tool_name,
                phase=_SUB_AGENT_TOOL_TO_PHASE[tool_name],
                state="started",
                model_id=sub_agent_model_id(tool_name),
                summary=_summarize_sub_agent_call_args(event.part.args_as_dict()),
            )),
        )
        return
    if isinstance(event, FunctionToolResultEvent):
        result_tool_name = sub_agent_tool_calls.get(event.tool_call_id)
        if result_tool_name is None:
            return
        result = event.result
        if isinstance(result, RetryPromptPart):
            content = result.content
            summary = (
                content[:280] if isinstance(content, str) else "retry requested"
            )
            is_retry = True
        else:
            summary = _summarize_sub_agent_result(result)
            is_retry = False
        _emit_chunk(
            writer,
            sub_agent_call_event(SubAgentCallPayload(
                tool_call_id=event.tool_call_id,
                sub_agent=result_tool_name,
                phase=_SUB_AGENT_TOOL_TO_PHASE[result_tool_name],
                state="failed" if is_retry else "completed",
                model_id=sub_agent_model_id(result_tool_name),
                summary=summary,
                succeeded=not is_retry,
            )),
        )
        ledger = derive_ledger(deps.state, deps.intent)
        _emit_chunk(writer, ledger_update_event(ledger=ledger))


def _split_agent_model(agent_model: str) -> tuple[str | None, str | None]:
    if ":" not in agent_model:
        return None, agent_model or None
    provider, _, model = agent_model.partition(":")
    return provider or None, model or None


async def _charge_token_delta(
    context: Context | None,
    state: PipelineState,
    capture: _LeadRunCapture,
    usage: RunUsage,
    writer: Any,
    agent_model: str,
) -> None:
    if context is None:
        return
    delta_input = usage.input_tokens - capture.charged_input_tokens
    delta_output = usage.output_tokens - capture.charged_output_tokens
    delta_cache_read = (
        usage.cache_read_tokens - capture.charged_cache_read_tokens
    )
    delta_cache_write = (
        usage.cache_write_tokens - capture.charged_cache_write_tokens
    )
    delta_tokens = (
        delta_input + delta_output + delta_cache_read + delta_cache_write
    )
    if delta_tokens <= 0:
        return
    provider_name, model_name = _split_agent_model(agent_model)
    delta_cost = cost_for_run(
        usage=RunUsage(
            input_tokens=delta_input,
            output_tokens=delta_output,
            cache_read_tokens=delta_cache_read,
            cache_write_tokens=delta_cache_write,
        ),
        model_name=model_name,
        provider_name=provider_name,
        provider_url=None,
    )
    try:
        async with context.db_session_factory() as session:
            await quota_service.accumulate(
                session,
                user_id=state.user_id,
                tokens=delta_tokens,
                cost_usd=delta_cost,
            )
            await session.commit()
    except SQLAlchemyError:
        logger.warning(
            "failed to accumulate streaming token delta",
            user_id=str(state.user_id),
            conversation_id=str(state.conversation_id),
            delta=delta_tokens,
        )
        return
    capture.charged_input_tokens += delta_input
    capture.charged_output_tokens += delta_output
    capture.charged_cache_read_tokens += delta_cache_read
    capture.charged_cache_write_tokens += delta_cache_write
    capture.charged_cost += delta_cost
    _emit_chunk(
        writer,
        turn_usage_event(
            total_tokens=state.turn_total_tokens + capture.cumulative_tokens,
            cost_usd=str(state.turn_total_cost_usd + capture.cumulative_cost),
        ),
    )


async def _persist_residual_quota(
    context: Context | None,
    state: PipelineState,
    capture: _LeadRunCapture,
) -> None:
    if context is None:
        return
    lead_residual_tokens = max(capture.tokens - capture.charged_tokens, 0)
    lead_residual_cost = max(capture.cost_usd - capture.charged_cost, Decimal(0))
    sub_agent_tokens = capture.sub_agent_tokens
    sub_agent_cost = capture.sub_agent_cost
    total_tokens = lead_residual_tokens + sub_agent_tokens
    total_cost = lead_residual_cost + sub_agent_cost
    if total_tokens == 0 and total_cost == 0:
        return
    async with context.db_session_factory() as session:
        try:
            await quota_service.accumulate(
                session,
                user_id=state.user_id,
                tokens=total_tokens,
                cost_usd=total_cost,
            )
            capture.charged_output_tokens += lead_residual_tokens
            capture.charged_cost += lead_residual_cost
            capture.sub_agent_tokens = 0
            capture.sub_agent_cost = Decimal(0)
        except SQLAlchemyError:
            logger.warning(
                "failed to accumulate lead residual quota",
                user_id=str(state.user_id),
                conversation_id=str(state.conversation_id),
            )
        await session.commit()


def _emit_residual_prose(
    writer: Any, capture: _LeadRunCapture, *, message_id: UUID,
) -> None:
    response = capture.response
    if response is None or not response.prose or capture.prose_already_streamed:
        return
    chunk_id = f"lead-prose-{message_id}"
    _emit_chunk(writer, TextStartChunk(id=chunk_id))
    _emit_chunk(writer, TextDeltaChunk(id=chunk_id, delta=response.prose))
    _emit_chunk(writer, TextEndChunk(id=chunk_id))


def _deferred_hint(pending: PendingApproval | None) -> DeferredToolHint | None:
    if pending is None:
        return None
    return DeferredToolHint(
        tool_call_id=pending.tool_call_id,
        tool_name=pending.tool_name,
        tool_args=pending.tool_args,
    )


def _model_id(agent: Any) -> str:
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    raw: Any = model.model_id
    return str(raw)


def _build_metadata(
    *, state: PipelineState, total_tokens: int, cost_usd: Decimal,
) -> dict[str, Any]:
    return MessageMetadata.model_validate(
        {
            "traceId": state.turn_trace_id,
            "createdAt": state.turn_created_at,
            "siteId": state.site_id,
            "mode": state.mode,
            "usage": {
                "totalTokens": total_tokens,
                "costUsd": str(cost_usd),
            },
        },
    ).model_dump(by_alias=True, exclude_none=True)


async def _retrieve_memories(
    state: PipelineState, runtime: Runtime[Context],
) -> list[MemoryValue]:
    if state.pending_approval is not None:
        return list(state.retrieved_memories)
    if runtime.context is None or runtime.context.memory_store is None:
        return []
    if not state.user_prompt.strip():
        return []
    mem_store = MemoryStore(store=runtime.context.memory_store)
    return await retrieve_relevant_memories(
        store=mem_store,
        user_id=state.user_id,
        query=state.user_prompt,
        site_id=state.site_id,
        top_k=8,
    )


async def write_turn_message(
    *, context: Context, state: PipelineState,
) -> UUID | None:
    """Persist the assistant message after the Lead's run completes.

    Mirrors the previous ``_write_turn_message`` in ``nodes.py``; placed
    here as a public helper because the Lead node is now the sole
    producer of turn messages.
    """
    _, chunks = await fetch_chunks_after(
        state.conversation_id, state.turn_start_event_id,
    )
    if not chunks:
        return None
    msg = reduce_chunks(chunks, default_message_id=str(state.turn_message_id))
    parts = msg["parts"]
    if not parts:
        return None
    raw_id = msg.get("id") or str(state.turn_message_id)
    message_id = UUID(raw_id)
    metadata = _build_metadata(
        state=state,
        total_tokens=state.turn_total_tokens,
        cost_usd=state.turn_total_cost_usd,
    )
    async with context.db_session_factory() as session:
        await MessagesRepository(session).upsert_message(
            message_id=message_id,
            conversation_id=state.conversation_id,
            role="assistant",
            metadata=metadata,
        )
        await session.commit()
    return message_id


def _resolve_lead_model_context(
    *,
    model_override: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[Any, str]:
    """Swap in the mock for the mock provider, otherwise honor per-request overrides."""
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        if isinstance(lead_agent.model, FunctionModel):
            return contextlib.nullcontext(), "mock:lead"
        return lead_agent.override(model=get_mock_model()), "mock:lead"

    override_kwargs: dict[str, Any] = {}
    if model_override:
        override_kwargs["model"] = model_override
    if reasoning_effort in ("low", "medium", "high"):
        override_kwargs["model_settings"] = {"thinking": reasoning_effort}

    if not override_kwargs:
        return contextlib.nullcontext(), _model_id(lead_agent)

    effective_model = model_override or _model_id(lead_agent)
    return lead_agent.override(**override_kwargs), effective_model


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
        message_id=str(message_id), deferred_hint=deferred_hint,
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
    sub_agent_tool_calls: dict[str, str] = {}
    _emit_chunk(
        writer,
        turn_status_event(label="Thinking...", waiting_on_llm=True),
    )

    async def _agent_events() -> AsyncGenerator[
        AgentStreamEvent | AgentRunResultEvent[Any]
    ]:
        async for event in lead_agent.run_stream_events(
            resume_prompt,
            deps=deps,
            message_history=resume_history,
            deferred_tool_results=deferred_results,
            usage_limits=LEAD_USAGE_LIMITS,
            usage=usage_acc,
        ):
            if isinstance(event, AgentRunResultEvent):
                _absorb_run_result(event, capture)
            else:
                _handle_sub_agent_event(
                    deps, writer, event, sub_agent_tool_calls,
                )
            await _charge_token_delta(
                runtime.context, state, capture, usage_acc, writer,
                agent_model,
            )
            yield event

    try:
        with override_ctx:
            async for v6_chunk in emitter.chunks(_agent_events()):
                if _is_suppressed_sub_agent_chunk(
                    v6_chunk, sub_agent_tool_calls,
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
        "problem_frame": deps.state.problem_frame,
        "discovered_searches": dict(deps.state.discovered_searches),
        "active_plan": deps.state.active_plan,
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


def _consume_blocking_questions_on_user_reply(state: PipelineState) -> None:
    """Clear ``problem_frame.blocking_questions`` when the user has just
    replied with text on a non-resume turn.

    Without this, the Ledger keeps reporting ``frame.blocked = True``
    forever — the questions sit on the saved frame even after the user
    answered them in conversation — and the Lead loops on scoping. The
    user's reply is by definition the answer; the Lead reads the reply
    as part of message_history and either accepts it (proceeds) or
    asks targeted follow-ups in its prose.
    """
    if state.pending_approval is not None:
        return
    if not state.user_prompt.strip():
        return
    frame = state.problem_frame
    if frame is None or not frame.blocking_questions:
        return
    frame.blocking_questions = []


async def lead_node(
    state: PipelineState, runtime: Runtime[Context],
) -> Command[Literal["finalize_turn"]]:
    writer = get_stream_writer()
    memories = await _retrieve_memories(state, runtime)
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
        _emit_chunk(
            writer,
            turn_usage_event(
                total_tokens=state.turn_total_tokens + capture.cumulative_tokens,
                cost_usd=str(
                    state.turn_total_cost_usd + capture.cumulative_cost,
                ),
            ),
        )

    working_state = state.model_copy(deep=True)
    _consume_blocking_questions_on_user_reply(working_state)
    deps = LeadDeps(
        state=working_state,
        intent=state.user_intent,
        runtime=runtime.context,
        retrieved_memories=memories,
        record_sub_agent_usage=_record_sub_agent_usage,
    )

    await _drive_lead_stream(
        state=state, runtime=runtime, deps=deps, capture=capture,
        writer=writer, message_id=message_id,
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
    cumulative_tokens = (
        state.turn_total_tokens + capture.tokens + capture.sub_agent_tokens
    )
    cumulative_cost = (
        state.turn_total_cost_usd + capture.cost_usd + capture.sub_agent_cost
    )
    final_sub_agent_tokens = capture.sub_agent_tokens
    final_sub_agent_cost = capture.sub_agent_cost
    await _persist_residual_quota(runtime.context, state, capture)
    capture.sub_agent_tokens = final_sub_agent_tokens
    capture.sub_agent_cost = final_sub_agent_cost
    _emit_chunk(
        writer,
        turn_usage_event(
            total_tokens=cumulative_tokens, cost_usd=str(cumulative_cost),
        ),
    )
    final_ledger = derive_ledger(deps.state, deps.intent)
    _emit_chunk(writer, ledger_update_event(ledger=final_ledger))
    delta = _build_state_delta(
        state=state, deps=deps, capture=capture, memories=memories,
    )
    return Command(goto=_FINALIZE, update=delta)
