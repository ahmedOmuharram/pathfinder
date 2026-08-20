"""Turn-level helpers for the Lead node.

Memory retrieval at turn start, resolution of the approval the user answered,
and the assistant-message write at turn end.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from langgraph.runtime import Runtime
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    ToolReturnPart,
)
from pydantic_ai.tools import (
    DeferredToolApprovalResult,
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)

from pathfinder.ai.capabilities.security import is_pure_approval
from pathfinder.ai.conversation.event_stream import fetch_chunks_after
from pathfinder.ai.conversation.ui_message_reducer import reduce_chunks
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import (
    SUB_AGENT_APPROVAL_PHASE,
    PendingApproval,
    PipelineState,
)
from pathfinder.ai.lead.sub_agent_dispatch import resume_sub_agent
from pathfinder.ai.lead.sub_agent_stream import SubAgentApprovalWait, SubAgentResume
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.memory.retrieval import retrieve_relevant_memories
from pathfinder.ai.memory.store import MemoryStore, StoredMemory
from pathfinder.persistence.repositories import MessagesRepository
from pathfinder.persistence.repositories._message_metadata import MessageMetadata

_DENIED_BY_REPLY = "The user replied instead of answering the approval."


def _build_metadata(
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


async def retrieve_memories(
    state: PipelineState,
    runtime: Runtime[Context],
) -> list[StoredMemory]:
    """Fresh-turn cross-thread retrieval.

    Returns ``[]`` on an approval-resume turn — the turn's memories are
    already persisted on ``state.retrieved_memories``, so the lead node
    preserves them rather than re-querying (and does not re-emit the
    recalled-memories chunk).
    """
    if state.pending_approval is not None:
        return []
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


class ConcurrentSubAgentApprovalsError(RuntimeError):
    """Two sub-agent dispatches in one Lead response both stopped at an approval."""

    def __init__(self, tool_call_ids: list[str]) -> None:
        super().__init__(
            "Two sub-agent dispatches deferred in one response "
            f"({', '.join(tool_call_ids)}). One suspended run is checkpointed "
            "per turn, so the second would be re-run rather than resumed.",
        )


def pending_approval(
    *,
    output: DeferredToolRequests,
    deps: LeadDeps,
    messages: list[ModelMessage],
) -> PendingApproval | None:
    """The approval a deferred Lead run waits on: the sub-agent call it
    dispatched, else its own tool.

    A dispatch outranks the Lead's own approval, because only the dispatch
    holds a suspended sub-agent run; an unapproved Lead tool is re-collected by
    pydantic-ai on the next run.

    ``messages`` is the FULL run history: when the Lead's first action is the
    deferred tool, ``new_messages()`` holds no leading ``ModelRequest`` and
    pydantic-ai rejects the resume as an empty history.
    """
    history = ModelMessagesTypeAdapter.dump_json(messages).decode()
    dispatches = [
        call
        for call in output.calls
        if call.tool_call_id in deps.pending_sub_agent_approvals
    ]
    if len(dispatches) > 1:
        raise ConcurrentSubAgentApprovalsError([c.tool_call_id for c in dispatches])
    if dispatches:
        dispatch = dispatches[0]
        sub_agent = deps.pending_sub_agent_approvals[dispatch.tool_call_id]
        return PendingApproval(
            phase=SUB_AGENT_APPROVAL_PHASE[sub_agent.role],
            tool_call_id=dispatch.tool_call_id,
            tool_name=dispatch.tool_name,
            tool_args=dispatch.args_as_dict(),
            prior_messages_json=history,
            sub_agent=sub_agent,
            user_message_id=deps.state.user_message_id,
        )
    if not output.approvals:
        return None
    own = output.approvals[0]
    return PendingApproval(
        phase="lead",
        tool_call_id=own.tool_call_id,
        tool_name=own.tool_name,
        tool_args=own.args_as_dict(),
        prior_messages_json=history,
        user_message_id=deps.state.user_message_id,
    )


@dataclass(frozen=True)
class ApprovalResolution:
    """What the user's answer produced: results the Lead resumes with, the
    message to deliver with them, or a further approval to wait on."""

    results: DeferredToolResults | None = None
    still_pending: PendingApproval | None = None
    user_prompt: str | None = None


def _answers_for(
    state: PipelineState,
    tool_call_ids: list[str],
) -> dict[str, bool | DeferredToolApprovalResult]:
    """The user's approve/deny for each of ``tool_call_ids``, when answered."""
    answers: dict[str, bool | DeferredToolApprovalResult] = {}
    for tool_call_id in tool_call_ids:
        response = state.approval_responses.get(tool_call_id)
        if response is None:
            continue
        answers[tool_call_id] = (
            True
            if response.approved
            else ToolDenied(message=response.reason or "User denied the tool call.")
        )
    return answers


def typed_reply(state: PipelineState) -> str | None:
    """The user's new message, when one arrives while an approval is pending.

    Answering the card leaves ``user_message_id`` untouched, so a different id
    is a message the user typed instead of clicking.
    """
    approval = state.pending_approval
    if approval is None or approval.user_message_id is None:
        return None
    if state.user_message_id in (None, approval.user_message_id):
        return None
    return state.user_prompt.strip() or None


def _settled_call_ids(history: list[ModelMessage]) -> set[str]:
    """Tool calls that already carry a result in the replayed history."""
    settled: set[str] = set()
    for message in history:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, ToolReturnPart | RetryPromptPart) and part.tool_call_id:
                settled.add(part.tool_call_id)
    return settled


def _sibling_answers(
    state: PipelineState,
    approval: PendingApproval,
) -> dict[str, bool | DeferredToolApprovalResult]:
    """Answers for the other calls the same Lead response left unresolved."""
    history = ModelMessagesTypeAdapter.validate_json(approval.prior_messages_json)
    last_response = next(
        (m for m in reversed(history) if isinstance(m, ModelResponse)),
        None,
    )
    if last_response is None:
        return {}
    settled = _settled_call_ids(history)
    return _answers_for(
        state,
        [
            call.tool_call_id
            for call in last_response.tool_calls
            if call.tool_call_id != approval.tool_call_id
            and call.tool_call_id not in settled
        ],
    )


def _unanswered_inner(
    state: PipelineState,
    approval: PendingApproval,
    inner_ids: list[str],
) -> tuple[dict[str, bool | DeferredToolApprovalResult], str | None]:
    """How to resolve inner approvals the user did not click.

    An answer naming the dispatch call applies to all of them. A typed reply
    approves them when it is nothing but an approval phrase, and otherwise
    denies them and is delivered to the Lead as the user's next message.
    """
    dispatch_answer = _answers_for(state, [approval.tool_call_id])
    if dispatch_answer:
        answer = dispatch_answer[approval.tool_call_id]
        return dict.fromkeys(inner_ids, answer), None
    typed = typed_reply(state)
    if typed is None:
        return {}, None
    if is_pure_approval(typed):
        approved: bool | DeferredToolApprovalResult = True
        return dict.fromkeys(inner_ids, approved), None
    denial: bool | DeferredToolApprovalResult = ToolDenied(message=_DENIED_BY_REPLY)
    return dict.fromkeys(inner_ids, denial), typed


async def resolve_pending_approval(
    *,
    state: PipelineState,
    deps: LeadDeps,
) -> ApprovalResolution:
    """Turn the user's approve/deny into the results the Lead resumes with.

    A sub-agent's approval is answered inside that sub-agent first; its
    finished delta then becomes the Lead's deferred tool result.
    """
    approval = state.pending_approval
    if approval is None:
        return ApprovalResolution()
    sub_agent = approval.sub_agent
    if sub_agent is None:
        answers = _answers_for(state, [approval.tool_call_id])
        if not answers:
            return ApprovalResolution()
        return ApprovalResolution(results=DeferredToolResults(approvals=answers))
    inner_ids = [call.tool_call_id for call in sub_agent.approvals]
    answers = _answers_for(state, inner_ids)
    prompt: str | None = None
    if not answers:
        answers, prompt = _unanswered_inner(state, approval, inner_ids)
    if not answers:
        # pydantic-ai re-executes a deferred call it is given no result for, so
        # a turn that resolves nothing keeps the card and runs no sub-agent.
        return ApprovalResolution(still_pending=approval)
    outcome = await resume_sub_agent(
        deps=deps,
        approval=approval,
        resume=SubAgentResume(
            messages=ModelMessagesTypeAdapter.validate_json(sub_agent.messages_json),
            results=DeferredToolResults(approvals=answers),
        ),
    )
    if isinstance(outcome, SubAgentApprovalWait):
        # The typed reply is spent: it produced the denial this new approval
        # follows, so the next turn must not deliver it again.
        return ApprovalResolution(
            still_pending=approval.model_copy(
                update={
                    "sub_agent": outcome.pending,
                    "user_message_id": state.user_message_id,
                },
            ),
        )
    return ApprovalResolution(
        results=DeferredToolResults(
            approvals=_sibling_answers(state, approval),
            calls={approval.tool_call_id: outcome},
        ),
        user_prompt=prompt,
    )


async def write_turn_message(
    *,
    context: Context,
    state: PipelineState,
) -> UUID | None:
    """Persist the assistant message after the Lead's run completes."""
    _, chunks = await fetch_chunks_after(
        state.conversation_id,
        state.turn_start_event_id,
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
