from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from langgraph.config import get_stream_writer
from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartEndEvent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)
from pydantic_ai.ui.vercel_ai.request_types import (
    DataUIPart,
    ReasoningUIPart,
    TextUIPart,
    ToolInputAvailablePart,
    ToolOutputAvailablePart,
    ToolOutputErrorPart,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy.exc import SQLAlchemyError

from pathfinder.ai.agents.supervisor import (
    SupervisorDecision,
    SupervisorDeps,
    SupervisorTarget,
    build_supervisor_agent,
)
from pathfinder.ai.conversation.approval import (
    ApprovalDecision,
    classify_approval_reply,
)
from pathfinder.ai.conversation.vercel_adapter import (
    DeferredToolHint,
    PhaseStreamEmitter,
)
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph.agents import PHASE_AGENTS
from pathfinder.ai.graph.runtime import (
    AgentDeps,
    Context,
    build_node_deps,
    extract_state_delta,
)
from pathfinder.ai.graph.state import (
    PendingApproval,
    PhaseDisposition,
    PhaseName,
    PhaseOutcome,
    PipelineState,
    VerificationDigest,
)
from pathfinder.ai.graph.stream_events import (
    phase_change_event,
    phase_start_event,
    scratchpad_updated_event,
    specialist_suggestion_event,
    supervisor_decision_event,
    turn_qa_event,
    turn_rejected_event,
    turn_usage_event,
)
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.ai.models.mock import get_mock_model
from pathfinder.ai.scratchpad.compactor import maybe_compact_scratchpad
from pathfinder.ai.scratchpad.rendering import render_scratchpad_for_supervisor
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.repositories._message_metadata import MessageMetadata
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger
from pathfinder.services import quota as quota_service
from pathfinder.services import user_preferences as prefs_service

logger = get_logger(__name__)

SUPERVISOR_CALL_BUDGET: int = 15

# Per-phase guardrail. The library catches the violation between LLM
# requests and raises ``UsageLimitExceeded``; we convert that into a
# graceful outcome so the supervisor can decide what to do next instead
# of the whole turn crashing. Generous caps — they exist to prevent
# pathological loops, not to throttle legitimate work.
PHASE_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=60,
    tool_calls_limit=60,
    total_tokens_limit=2_000_000,
)


def model_id(agent: Agent[Any, Any]) -> str:
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return model.model_id


# Mirrors pydantic_ai._output.DEFAULT_OUTPUT_TOOL_NAME (private). Union output
# types fan out to ``<base>_<TypeName>``, so prefix-match too.
_FINAL_RESULT_NAME = "final_result"
_FINAL_RESULT_PREFIX = "final_result_"


def _is_final_result_tool(name: str) -> bool:
    return name == _FINAL_RESULT_NAME or name.startswith(_FINAL_RESULT_PREFIX)


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
) -> list[_PersistedPart]:
    tool_returns = _index_tool_returns(new_messages)
    parts: list[_PersistedPart] = []
    for msg in new_messages:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            converted = _convert_response_part(part, tool_returns)
            if converted is not None:
                parts.append(converted)
    return parts


type _PersistedPart = (
    TextUIPart
    | ReasoningUIPart
    | ToolInputAvailablePart
    | ToolOutputAvailablePart
    | ToolOutputErrorPart
)

type _TurnPart = _PersistedPart | DataUIPart


def _dump_parts(parts: list[_TurnPart]) -> list[dict[str, Any]]:
    return [
        p.model_dump(by_alias=True, mode="json", exclude_none=True)
        for p in parts
    ]


def _convert_response_part(
    part: object,
    tool_returns: dict[str, ToolReturnPart],
) -> _PersistedPart | None:
    match part:
        case TextPart(content=content) if content:
            return TextUIPart(text=content, state="done")
        case ThinkingPart(content=content) if content:
            return ReasoningUIPart(text=content, state="done")
        case ToolCallPart() as tc if not _is_final_result_tool(tc.tool_name):
            ret = tool_returns.get(tc.tool_call_id)
            if ret is None:
                return ToolInputAvailablePart(
                    type=f"tool-{tc.tool_name}",
                    tool_call_id=tc.tool_call_id,
                    input=tc.args_as_dict(),
                )
            if ret.outcome == "failed":
                return ToolOutputErrorPart(
                    type=f"tool-{tc.tool_name}",
                    tool_call_id=tc.tool_call_id,
                    input=tc.args_as_dict(),
                    error_text=str(ret.content),
                )
            return ToolOutputAvailablePart(
                type=f"tool-{tc.tool_name}",
                tool_call_id=tc.tool_call_id,
                input=tc.args_as_dict(),
                # Pydantic v2 walks ``Any`` recursively in mode="json",
                # so BaseModel/dataclass returns serialize without our
                # old hand-rolled ``_serialize_tool_return_content``.
                output=ret.content,
            )
        case _:
            return None


def _phase_start_part(phase: PhaseName, trace_id: str | None, model: str) -> DataUIPart:
    return DataUIPart(
        type="data-phase-start",
        data={"phase": phase, "traceId": trace_id or "", "model": model},
    )


def _data_part(part_type: str, data: dict[str, Any]) -> DataUIPart:
    return DataUIPart(type=part_type, data=data)


def _text_part(text: str) -> TextUIPart:
    return TextUIPart(text=text, state="done")


def _build_turn_metadata(
    *,
    state: PipelineState,
    total_tokens: int,
    cost_usd: Decimal,
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


async def _write_turn_message(
    *,
    context: Context,
    state: PipelineState,
    parts: list[_TurnPart],
) -> UUID | None:
    """Finalize the turn's assistant message row.

    ``_persist_phase_progress`` already upserted progressively at each phase,
    so this upsert replaces the partial row with the final parts and usage.
    """
    if not parts:
        return None
    metadata = _build_turn_metadata(
        state=state,
        total_tokens=state.turn_total_tokens,
        cost_usd=state.turn_total_cost_usd,
    )
    async with context.db_session_factory() as session:
        await MessagesRepository(session).upsert_message(
            message_id=state.turn_message_id,
            conversation_id=state.conversation_id,
            role="assistant",
            parts=_dump_parts(parts),
            metadata=metadata,
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
    # Tokens / cost already charged to the user's quota mid-stream. Phase-end
    # reconciliation charges the residual ``tokens - charged_tokens`` and
    # ``cost_usd - charged_cost``.
    charged_input_tokens: int = 0
    charged_output_tokens: int = 0
    charged_cache_read_tokens: int = 0
    charged_cache_write_tokens: int = 0
    charged_cost: Decimal = Field(default_factory=lambda: Decimal(0))
    orphan_text_parts: list[TextPart] = Field(default_factory=list)
    prose_already_streamed: bool = False
    pending_approval: PendingApproval | None = None
    approval_consumed: bool = False

    @property
    def charged_tokens(self) -> int:
        return self.charged_input_tokens + self.charged_output_tokens


def _synthesize_from_orphan_text(
    capture: _PhaseRunCapture,
    state: PipelineState,
    phase: PhaseName,
    agent_model: str,
) -> None:
    if not capture.orphan_text_parts:
        # Model returned ``finish_reason=stop`` with no tool call and no text
        # (commonly seen after a durable-tool resume when the agent decides
        # there's nothing more to add). Crashing the whole graph here would
        # silence the chat — fall back to a neutral AWAITING_USER outcome
        # routed back to the supervisor instead.
        logger.warning(
            "phase produced no AgentRunResult and no text — soft-ended phase",
            phase=phase,
            conversation_id=str(state.conversation_id),
            user_id=str(state.user_id),
            trace_id=state.turn_trace_id,
            model=agent_model,
            finish_reason=capture.finish_reason,
        )
        capture.phase_outcome = PhaseOutcome(
            disposition=PhaseDisposition.AWAITING_USER,
            prose="",
            reason=(
                f"{phase} phase produced no actionable output "
                f"(finish_reason={capture.finish_reason})"
            ),
        )
        capture.prose_already_streamed = True
        capture.new_messages = []
        return

    prose = "\n".join(p.content for p in capture.orphan_text_parts).strip()
    capture.phase_outcome = PhaseOutcome(
        disposition=PhaseDisposition.AWAITING_USER,
        prose=prose[:4000],
        reason="phase returned prose without calling final_result",
    )
    capture.prose_already_streamed = True
    capture.new_messages = [
        ModelRequest(parts=[UserPromptPart(content=state.user_prompt)]),
        ModelResponse(parts=list(capture.orphan_text_parts)),
    ]
    logger.warning(
        "phase produced prose without AgentRunResult — synthesized outcome",
        phase=phase,
        conversation_id=str(state.conversation_id),
        user_id=str(state.user_id),
        trace_id=state.turn_trace_id,
        model=agent_model,
        prose_chars=len(prose),
    )


def _absorb_run_result(
    event: AgentRunResultEvent,
    capture: _PhaseRunCapture,
    *,
    phase: PhaseName,
    plan_id: str | None,
) -> None:
    run_result = event.result
    capture.new_messages = list(run_result.new_messages())
    response = run_result.response
    if response.finish_reason:
        capture.finish_reason = response.finish_reason
    output = run_result.output
    if isinstance(output, PhaseOutcome):
        capture.phase_outcome = output
    elif isinstance(output, DeferredToolRequests) and output.approvals:
        approval_call = output.approvals[0]
        capture.pending_approval = PendingApproval(
            phase=phase,
            tool_call_id=approval_call.tool_call_id,
            tool_name=approval_call.tool_name,
            tool_args=approval_call.args_as_dict(),
            plan_id=plan_id,
            prior_messages_json=ModelMessagesTypeAdapter.dump_json(
                capture.new_messages,
            ).decode(),
        )
        capture.phase_outcome = PhaseOutcome(
            disposition=PhaseDisposition.AWAITING_USER,
            prose=(
                "The plan is ready for your review. Click on 'Approve' "
                "or 'Deny' in the right sidebar, or describe changes you'd like."
            ),
            reason=f"{approval_call.tool_name} awaiting user approval",
        )
    usage = run_result.usage()
    capture.tokens = usage.total_tokens
    capture.cost_usd = cost_for_run(
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
    new_parts: list[_TurnPart],
    capture: _PhaseRunCapture,
) -> dict[str, Any]:
    delta = extract_state_delta(deps)
    delta["current_phase"] = phase
    delta["turn_message_parts"] = state.turn_message_parts + new_parts
    delta["turn_total_tokens"] = state.turn_total_tokens + capture.tokens
    delta["turn_total_cost_usd"] = state.turn_total_cost_usd + capture.cost_usd
    if capture.phase_outcome is not None:
        delta["last_phase_outcome"] = capture.phase_outcome
        if isinstance(capture.phase_outcome, VerificationDigest):
            delta["verification_digest"] = capture.phase_outcome
    if capture.pending_approval is not None:
        delta["pending_approval"] = capture.pending_approval
    elif capture.approval_consumed:
        delta["pending_approval"] = None
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


def _resume_user_prompt(state: PipelineState) -> str | None:
    """When resuming a deferred tool, the user text is already captured as
    the approval / denial — don't re-insert it as a new UserPromptPart."""
    if state.pending_approval is None:
        return state.user_prompt
    return None


def _build_deferred_tool_results(
    state: PipelineState,
    phase: PhaseName,
) -> DeferredToolResults | None:
    approval = state.pending_approval
    if approval is None or approval.phase != phase:
        return None
    decision = classify_approval_reply(state.user_prompt)
    if decision == ApprovalDecision.APPROVED:
        return DeferredToolResults(approvals={approval.tool_call_id: True})
    return DeferredToolResults(
        approvals={
            approval.tool_call_id: ToolDenied(
                message=f"User did not approve. Message: {state.user_prompt}",
            ),
        },
    )


def _resume_message_history(
    state: PipelineState, phase: PhaseName,
) -> list[ModelMessage] | None:
    """Replay the prior agent run's actual messages so the provider sees
    the original tool-call request it issued. OpenAI rejects tool results
    referencing tool_call_ids it didn't see in the same conversation, so
    a synthesized stub doesn't suffice — we deserialize the captured
    ``new_messages`` snapshot stored on ``PendingApproval``."""
    approval = state.pending_approval
    if approval is None or approval.phase != phase:
        return None
    if not approval.prior_messages_json:
        return None
    return ModelMessagesTypeAdapter.validate_json(approval.prior_messages_json)


def _plan_id_from_state(state: PipelineState) -> str | None:
    return state.active_plan.id if state.active_plan is not None else None


_OVERRIDE_MAX_TOKENS = 32_000
"""Anthropic rejects ``max_tokens <= thinking.budget_tokens`` (default
``max_tokens=4096``; ``Thinking(effort="high")`` budget = 16384). 32000
covers all current ``ANTHROPIC_THINKING_BUDGET_MAP`` entries we use and
is silently capped by OpenAI / Google.
"""

_OVERRIDE_MODEL_SETTINGS: ModelSettings = {"max_tokens": _OVERRIDE_MAX_TOKENS}


async def _resolve_phase_model_override(
    state: PipelineState, runtime: Runtime[Context], phase: PhaseName,
) -> str | None:
    """Per-user phase model override, or None to keep the agent's default."""
    if runtime.context is None:
        return None
    try:
        async with runtime.context.db_session_factory() as session:
            return await prefs_service.resolve_phase_model(
                session, user_id=state.user_id, phase=phase,
            )
    except SQLAlchemyError:
        logger.warning(
            "failed to load phase model pref; using phase-agent default",
            user_id=str(state.user_id),
            phase=phase,
        )
        return None


async def _resolve_phase_model_context(
    agent: Agent[AgentDeps, Any],
    state: PipelineState,
    runtime: Runtime[Context],
    phase: PhaseName,
) -> tuple[Any, str]:
    """Resolve the override context manager and the agent-model id label.

    Mock chat provider (E2E mode) swaps in the deterministic FunctionModel
    so chat doesn't depend on a real LLM API key. User-pref overrides are
    ignored in mock mode because the mock fakes every phase.
    """
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        if isinstance(agent.model, FunctionModel):
            return contextlib.nullcontext(), f"mock:{phase}"
        return agent.override(model=get_mock_model()), f"mock:{phase}"
    model_override = await _resolve_phase_model_override(state, runtime, phase)
    if model_override is None:
        return contextlib.nullcontext(), model_id(agent)
    ctx = agent.override(
        model=model_override,
        model_settings=_OVERRIDE_MODEL_SETTINGS,
    )
    return ctx, model_override


def _handle_usage_limit_exceeded(
    capture: _PhaseRunCapture,
    exc: UsageLimitExceeded,
    *,
    phase: PhaseName,
    state: PipelineState,
    agent_model: str,
) -> None:
    """Convert a hit usage cap into a graceful phase outcome.

    Better to halt the phase and let the supervisor decide than to keep
    burning budget. The synthesized outcome flips the turn to
    ``awaiting_user`` so the user can refine or approve continuation.
    """
    logger.warning(
        "phase usage limit exceeded — capping run",
        phase=phase,
        conversation_id=str(state.conversation_id),
        user_id=str(state.user_id),
        trace_id=state.turn_trace_id,
        model=agent_model,
        error=str(exc),
    )
    capture.phase_outcome = PhaseOutcome(
        disposition=PhaseDisposition.AWAITING_USER,
        prose=(
            f"The {phase} phase hit its safety budget ({exc}). "
            "Investigation paused — refine the request or approve a "
            "continuation to proceed."
        ),
        reason=f"{phase} phase exceeded usage budget",
    )
    capture.prose_already_streamed = False


def _emit_residual_prose(
    writer: Any,
    capture: _PhaseRunCapture,
    *,
    phase_message_id: UUID,
    new_parts: list[_TurnPart],
) -> None:
    outcome = capture.phase_outcome
    if outcome is None or not outcome.prose or capture.prose_already_streamed:
        return
    prose_chunk_id = f"phase-prose-{phase_message_id}"
    _emit_chunk(writer, TextStartChunk(id=prose_chunk_id))
    _emit_chunk(
        writer, TextDeltaChunk(id=prose_chunk_id, delta=outcome.prose),
    )
    _emit_chunk(writer, TextEndChunk(id=prose_chunk_id))
    new_parts.append(_text_part(outcome.prose))


def _deferred_hint_for_phase(
    pending: PendingApproval | None, phase: PhaseName,
) -> DeferredToolHint | None:
    if pending is None or pending.phase != phase:
        return None
    return DeferredToolHint(
        tool_call_id=pending.tool_call_id,
        tool_name=pending.tool_name,
        tool_args=pending.tool_args,
    )


def _log_phase_stream_error(
    *, phase: PhaseName, state: PipelineState, agent_model: str,
) -> None:
    logger.exception(
        "phase stream raised",
        phase=phase,
        conversation_id=str(state.conversation_id),
        user_id=str(state.user_id),
        trace_id=state.turn_trace_id,
        model=agent_model,
    )


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

    override_ctx, agent_model = await _resolve_phase_model_context(
        agent, state, runtime, phase,
    )

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
    deferred_hint = _deferred_hint_for_phase(state.pending_approval, phase)
    emitter = PhaseStreamEmitter(
        message_id=str(phase_message_id), deferred_hint=deferred_hint,
    )
    deferred_results = _build_deferred_tool_results(state, phase)
    capture.approval_consumed = deferred_results is not None
    resume_prompt = _resume_user_prompt(state)
    resume_history = _resume_message_history(state, phase)
    usage_acc = RunUsage()

    async def _agent_events() -> AsyncGenerator[AgentStreamEvent | AgentRunResultEvent[Any]]:
        async for event in agent.run_stream_events(
            resume_prompt,
            deps=deps,
            message_history=resume_history,
            deferred_tool_results=deferred_results,
            usage_limits=PHASE_USAGE_LIMITS,
            usage=usage_acc,
        ):
            if isinstance(event, AgentRunResultEvent):
                _absorb_run_result(
                    event,
                    capture,
                    phase=phase,
                    plan_id=_plan_id_from_state(state),
                )
            elif (
                isinstance(event, PartEndEvent)
                and isinstance(event.part, TextPart)
                and event.part.content.strip()
            ):
                capture.orphan_text_parts.append(event.part)
            await _charge_token_delta(
                runtime.context, state, capture, usage_acc, writer,
                agent_model,
            )
            yield event

    try:
        with override_ctx:
            async for v6_chunk in emitter.chunks(_agent_events()):
                _emit_chunk(writer, v6_chunk)
    except UsageLimitExceeded as exc:
        _handle_usage_limit_exceeded(
            capture, exc, phase=phase, state=state, agent_model=agent_model,
        )
    except GraphBubbleUp:
        raise
    except Exception:
        _log_phase_stream_error(
            phase=phase, state=state, agent_model=agent_model,
        )
        raise

    if not capture.new_messages:
        _synthesize_from_orphan_text(capture, state, phase, agent_model)

    new_parts: list[_TurnPart] = [
        _phase_start_part(phase, state.turn_trace_id, agent_model),
        *_convert_assistant_parts(capture.new_messages),
    ]
    _emit_residual_prose(
        writer, capture, phase_message_id=phase_message_id, new_parts=new_parts,
    )

    cumulative_tokens = state.turn_total_tokens + capture.tokens
    cumulative_cost = state.turn_total_cost_usd + capture.cost_usd
    cumulative_parts = state.turn_message_parts + new_parts

    await _persist_phase_progress(
        runtime.context,
        state=state,
        capture=capture,
        cumulative_parts=cumulative_parts,
    )
    _emit_chunk(
        writer,
        turn_usage_event(
            total_tokens=cumulative_tokens,
            cost_usd=str(cumulative_cost),
        ),
    )

    return _build_phase_delta(
        state=state, deps=deps, phase=phase, new_parts=new_parts, capture=capture,
    )


def _split_agent_model(agent_model: str) -> tuple[str | None, str | None]:
    """Split ``"openai:gpt-4.1-mini"`` into ``("openai", "gpt-4.1-mini")``.

    Falls back to ``(None, value)`` for unprefixed ids. The provider
    prefix matches ``genai_prices``'s ``provider_id`` taxonomy so the
    cost lookup hits the right pricing table.
    """
    if ":" not in agent_model:
        return None, agent_model or None
    provider, _, model = agent_model.partition(":")
    return provider or None, model or None


async def _charge_token_delta(
    context: Context | None,
    state: PipelineState,
    capture: _PhaseRunCapture,
    usage: RunUsage,
    writer: Any,
    agent_model: str,
) -> None:
    """Charge the user's quota for tokens + cost accumulated since the
    last call. Pydantic-ai mutates the shared ``RunUsage`` as the stream
    progresses; we read it after every event and persist the delta so a
    phase that fails midway still bills correctly."""
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
            total_tokens=state.turn_total_tokens + capture.charged_tokens,
            cost_usd=str(state.turn_total_cost_usd + capture.charged_cost),
        ),
    )


async def _persist_phase_progress(
    context: Context | None,
    *,
    state: PipelineState,
    capture: _PhaseRunCapture,
    cumulative_parts: list[_TurnPart],
) -> None:
    """Persist per-phase quota + the turn message's partial state.

    Charges the user for this phase immediately (so mid-turn failures still
    charge) and upserts the turn's assistant message so the conversation
    detail endpoint reflects accumulated usage without waiting for
    ``finalize_turn_node``.
    """
    if context is None or not cumulative_parts:
        return

    cumulative_tokens = state.turn_total_tokens + capture.tokens
    cumulative_cost = state.turn_total_cost_usd + capture.cost_usd

    async with context.db_session_factory() as session:
        residual_tokens = max(capture.tokens - capture.charged_tokens, 0)
        residual_cost = max(capture.cost_usd - capture.charged_cost, Decimal(0))
        if residual_tokens > 0 or residual_cost > 0:
            try:
                await quota_service.accumulate(
                    session,
                    user_id=state.user_id,
                    tokens=residual_tokens,
                    cost_usd=residual_cost,
                )
                capture.charged_output_tokens += residual_tokens
                capture.charged_cost += residual_cost
            except SQLAlchemyError:
                logger.warning(
                    "failed to accumulate phase quota",
                    user_id=str(state.user_id),
                    conversation_id=str(state.conversation_id),
                    phase=state.current_phase,
                )
        metadata = _build_turn_metadata(
            state=state,
            total_tokens=cumulative_tokens,
            cost_usd=cumulative_cost,
        )
        try:
            await MessagesRepository(session).upsert_message(
                message_id=state.turn_message_id,
                conversation_id=state.conversation_id,
                role="assistant",
                parts=_dump_parts(cumulative_parts),
                metadata=metadata,
            )
        except SQLAlchemyError:
            logger.warning(
                "failed to upsert partial turn message",
                conversation_id=str(state.conversation_id),
            )
        await session.commit()


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


async def _render_supervisor_state(
    state: PipelineState, context: Context | None,
) -> str:
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
    body = "\n".join(lines)
    if context is None:
        return body
    async with context.db_session_factory() as session:
        repo = ScratchpadRepository(session)
        notes, total_count, _ = await repo.list_for_index_with_totals(
            conversation_id=state.conversation_id,
        )
    scratchpad_block = render_scratchpad_for_supervisor(
        notes, total_count=total_count,
    )
    return f"{body}\n\n{scratchpad_block}"


def _supervisor_goto(target: SupervisorTarget) -> SupervisorGoto:
    match target:
        case "end" | "reject" | "question":
            return _FINALIZE
        case _:
            return target


def _supervisor_finalize(
    state: PipelineState,
    reason: str,
    extra_part: _TurnPart,
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


def _resume_pending_approval(
    state: PipelineState, writer: Any,
) -> Command[SupervisorGoto] | None:
    """Short-circuit supervisor when a tool approval is pending.

    The pending approval implies the last turn halted on a deferred tool;
    this turn must resume that exact phase to hand the user's reply back
    to pydantic-ai as a ``DeferredToolResults``.
    """
    approval = state.pending_approval
    if approval is None or state.phase_call_counts:
        return None
    reason = (
        f"resuming {approval.tool_name} approval on {approval.phase} phase"
    )
    _emit_chunk(
        writer,
        supervisor_decision_event(to=approval.phase, reason=reason),
    )
    return Command(
        goto=approval.phase,
        update={
            "current_phase": approval.phase,
            "last_routing_reason": reason,
            "supervisor_call_count": state.supervisor_call_count + 1,
            "turn_message_parts": [
                *state.turn_message_parts,
                _data_part(
                    "data-supervisor-decision",
                    {"to": approval.phase, "reason": reason},
                ),
            ],
        },
    )


def _supervisor_budget_exhausted(
    state: PipelineState, writer: Any,
) -> Command[SupervisorGoto] | None:
    if state.supervisor_call_count < SUPERVISOR_CALL_BUDGET:
        return None
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
        _data_part(
            "data-phase-change",
            {"phase": "completed", "status": "failed", "reason": abort_reason},
        ),
    )


def _supervisor_halt_on_awaiting_user(
    state: PipelineState, writer: Any,
) -> Command[SupervisorGoto] | None:
    outcome = state.last_phase_outcome
    if outcome is None or outcome.disposition != PhaseDisposition.AWAITING_USER:
        return None
    halt_reason = outcome.reason
    _emit_chunk(writer, supervisor_decision_event(to="end", reason=halt_reason))
    return _supervisor_finalize(
        state,
        halt_reason,
        _data_part(
            "data-supervisor-decision",
            {"to": "end", "reason": halt_reason},
        ),
    )


async def _run_supervisor_agent(
    state: PipelineState, runtime: Runtime[Context],
) -> SupervisorDecision | None:
    supervisor_model_id = await _resolve_supervisor_model(state, runtime)
    agent = build_supervisor_agent(model_id=supervisor_model_id)
    deps = SupervisorDeps(
        state_block=await _render_supervisor_state(state, runtime.context),
    )
    user_prompt_for_run = (
        "Decide the next action."
        if state.phase_call_counts
        else state.user_prompt or "(empty user message)"
    )
    is_mock = (
        get_settings().pathfinder_chat_provider.strip().lower() == "mock"
    )
    override_ctx = (
        agent.override(model=get_mock_model())
        if is_mock and not isinstance(agent.model, FunctionModel)
        else contextlib.nullcontext()
    )
    try:
        with override_ctx:
            result = await agent.run(
                user_prompt_for_run, deps=deps, message_history=None,
            )
    except Exception:
        logger.exception(
            "supervisor agent failed; ending turn",
            conversation_id=str(state.conversation_id),
        )
        return None
    return result.output


async def supervisor_node(
    state: PipelineState, runtime: Runtime[Context]
) -> Command[SupervisorGoto]:
    writer = get_stream_writer()
    for guard in (
        _supervisor_budget_exhausted(state, writer),
        _resume_pending_approval(state, writer),
        _supervisor_halt_on_awaiting_user(state, writer),
    ):
        if guard is not None:
            return guard

    decision = await _run_supervisor_agent(state, runtime)
    if decision is None:
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
            _data_part(
                "data-phase-change",
                {
                    "phase": "completed",
                    "status": "failed",
                    "reason": fallback_reason,
                },
            ),
        )
    _emit_chunk(
        writer,
        supervisor_decision_event(to=decision.to, reason=decision.reason),
    )
    new_parts: list[_TurnPart] = [
        _data_part("data-supervisor-decision", {"to": decision.to, "reason": decision.reason}),
    ]
    if decision.suggested_specialist is not None:
        _emit_chunk(
            writer,
            specialist_suggestion_event(kind=decision.suggested_specialist),
        )
        new_parts.append(
            _data_part(
                "data-specialist-suggestion",
                {"kind": decision.suggested_specialist},
            ),
        )

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

    if runtime.context is not None and state.current_phase == "verification":
        try:
            compaction_run = await maybe_compact_scratchpad(
                conversation_id=state.conversation_id,
                user_id=state.user_id,
                db_session_factory=runtime.context.db_session_factory,
            )
        except Exception:
            # Compaction must never break the turn — broad catch mirrors
            # the supervisor-agent failure handler above (same rationale).
            logger.exception(
                "scratchpad compaction wrapper failed",
                conversation_id=str(state.conversation_id),
            )
            compaction_run = None
        if compaction_run is not None:
            writer = get_stream_writer()
            writer(
                {
                    "chunk": scratchpad_updated_event().model_dump(
                        by_alias=True, mode="json", exclude_none=True,
                    ),
                },
            )

    return Command(goto=_END, update={"turn_message_parts": []})
