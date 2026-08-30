"""Turn-level helpers for the Lead node.

Memory retrieval at turn start, and the Lead's half of the approval cycle:
which deferred call the turn waits on, and what the user's answer means for
the sub-agent run under it. The cycle's shared mechanics are the runtime's.
"""

from __future__ import annotations

from dataclasses import dataclass

from assistant_core.graph import approvals
from assistant_core.graph.turn_state import PendingApproval
from assistant_core.memory.retrieval import retrieve_relevant_memories
from assistant_core.memory.store import MemoryStore, StoredMemory
from langgraph.runtime import Runtime
from pydantic_ai.exceptions import ModelRetry
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
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.dispatch_resume import SubAgentOutcome, resume_sub_agent
from pathfinder.ai.lead.memory_candidates import PRODUCT_MEMORY_KINDS
from pathfinder.ai.lead.sub_agent_stream import SubAgentApprovalWait, SubAgentResume
from pathfinder.ai.lead.sub_agent_tools import WIRE_PHASE_BY_ROLE, LeadDeps

_DENIED_BY_REPLY = "The user replied instead of answering the approval."


async def retrieve_memories(
    state: PipelineState,
    runtime: Runtime[Context],
) -> list[StoredMemory]:
    """Fresh-turn cross-thread retrieval.

    Returns ``[]`` on an approval-resume turn: the turn's memories are
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
        kinds=PRODUCT_MEMORY_KINDS,
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
    """
    dispatches = [
        call
        for call in output.calls
        if call.tool_call_id in deps.pending_sub_agent_approvals
    ]
    if len(dispatches) > 1:
        raise ConcurrentSubAgentApprovalsError([c.tool_call_id for c in dispatches])
    user_message_id = deps.state.user_message_id
    if dispatches:
        sub_agent = deps.pending_sub_agent_approvals[dispatches[0].tool_call_id]
        parked = approvals.parked_call(
            call=dispatches[0],
            phase=WIRE_PHASE_BY_ROLE[sub_agent.role],
            messages=messages,
        )
        return parked.model_copy(
            update={"sub_agent": sub_agent, "user_message_id": user_message_id},
        )
    own = approvals.pending_approval(output=output, phase="lead", messages=messages)
    if own is None:
        return None
    return own.model_copy(update={"user_message_id": user_message_id})


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
        answers[tool_call_id] = approvals.approval_answer(response)
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
    history = approvals.resume_history(approval)
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
    outcome: SubAgentOutcome | ModelRetry
    try:
        outcome = await resume_sub_agent(
            deps=deps,
            approval=approval,
            resume=SubAgentResume(
                messages=ModelMessagesTypeAdapter.validate_json(
                    sub_agent.messages_json
                ),
                results=DeferredToolResults(approvals=answers),
            ),
        )
    except ModelRetry as retry:
        # A dispatch refuses its own sub-agent's result here as it does on a
        # fresh call. pydantic-ai accepts a ModelRetry as a deferred call's
        # result, so the Lead reads the refusal and the turn does not end.
        outcome = retry
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
