"""A sub-agent approval ends the Lead's turn deferred, and the user's answer
re-enters the sub-agent before the Lead run continues.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.ui.vercel_ai.request_types import ToolApprovalResponded
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.graph import lead_node
from pathfinder.ai.graph._lead_capture import _LeadRunCapture
from pathfinder.ai.graph.lead_node import _drive_lead_stream
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_stream, sub_agent_tools
from pathfinder.ai.lead.lead_agent import build_lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.toolsets import verification
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_OPTIMIZE_ARGS: dict[str, Any] = {
    "target": {
        "site_id": "plasmodb",
        "record_type": "transcript",
        "search_name": "GenesByRNASeqEvidence",
        "parameter_space": [
            {"name": "min_fold_change", "kind": "numeric", "low": 1.5, "high": 4.0},
        ],
    },
    "controls": {
        "positive_controls": ["PF3D7_1133400"],
        "negative_controls": ["PF3D7_0930300"],
    },
    "settings": {"budget": 8, "objective": "f1"},
}
_VERIFICATION_FINAL: dict[str, Any] = {
    "digest": {
        "disposition": "done",
        "prose": "scripted",
        "reason": "scripted",
        "success": True,
    },
}
_RECOVERY_FINAL: dict[str, Any] = {
    "actionsTaken": ["deleted s2"],
    "followUpNeeded": False,
}
_LEAD_FINAL: dict[str, Any] = {"prose": "scripted", "nextState": "await_user"}

_TEST_INSTRUCTIONS = "Call the tool the script names, then return the typed output."


def _tool_calls(messages: list[ModelMessage]) -> list[ToolCallPart]:
    return [
        part
        for msg in messages
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    ]


def _user_prompts(messages: list[ModelMessage]) -> list[str]:
    return [
        part.content
        for msg in messages
        if isinstance(msg, ModelRequest)
        for part in msg.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    ]


def _model(part_for: Any, seen_prompts: list[str] | None = None) -> FunctionModel:
    """A FunctionModel driven by ``part_for(messages) -> list[ToolCallPart]``."""

    def _parts(messages: list[ModelMessage]) -> list[ToolCallPart]:
        if seen_prompts is not None:
            seen_prompts.extend(_user_prompts(messages))
        produced: ToolCallPart | list[ToolCallPart] = part_for(messages)
        return produced if isinstance(produced, list) else [produced]

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        return ModelResponse(parts=list(_parts(messages)))

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del info
        yield {
            index: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            )
            for index, part in enumerate(_parts(messages))
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


def _one_call_model(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    final_args: dict[str, Any],
    seen_prompts: list[str] | None = None,
) -> FunctionModel:
    """Call ``tool_name`` once, then emit the agent's typed output."""

    def _part(messages: list[ModelMessage]) -> ToolCallPart:
        if tool_name not in {c.tool_name for c in _tool_calls(messages)}:
            return ToolCallPart(
                tool_name=tool_name,
                args=tool_args,
                tool_call_id=f"call_{tool_name}",
            )
        return ToolCallPart(
            tool_name="final_result",
            args=final_args,
            tool_call_id=f"call_final_{uuid4().hex[:8]}",
        )

    return _model(_part, seen_prompts)


def _two_delete_model() -> FunctionModel:
    """Ask to delete one step, then another, then finish."""

    def _part(messages: list[ModelMessage]) -> ToolCallPart:
        deletes = [c for c in _tool_calls(messages) if c.tool_name == "delete_step"]
        if len(deletes) < 2:
            index = len(deletes) + 1
            return ToolCallPart(
                tool_name="delete_step",
                args={"step_id": f"s{index}"},
                tool_call_id=f"call_delete_{index}",
            )
        return ToolCallPart(
            tool_name="final_result",
            args=_RECOVERY_FINAL,
            tool_call_id=f"call_final_{uuid4().hex[:8]}",
        )

    return _model(_part)


class _Collector:
    """Stands in for the langgraph stream writer."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)

    def chunks_of(self, chunk_type: str) -> list[dict[str, Any]]:
        return [
            p["chunk"]
            for p in self.payloads
            if "chunk" in p and p["chunk"].get("type") == chunk_type
        ]


def _quota_offline() -> AsyncSession:
    """Quota accumulation tolerates a database that is not there."""
    msg = "no database in this unit test"
    raise OperationalError(msg, None, Exception(msg))


def _state() -> PipelineState:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Tune the RNA-Seq fold change against my controls.",
        user_message_id=uuid4(),
    )
    state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1", "s2"],
        failed_steps=[],
        root_count=0,
    )
    return state


def _deps(state: PipelineState) -> LeadDeps:
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_quota_offline,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
    )


async def _drive(
    *,
    state: PipelineState,
    deps: LeadDeps,
    writer: _Collector,
) -> _LeadRunCapture:
    capture = _LeadRunCapture()
    await _drive_lead_stream(
        state=state,
        agent=build_lead_agent(),
        deps=deps,
        capture=capture,
        writer=writer,
        message_id=uuid4(),
    )
    return capture


@pytest.fixture
def writer(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    return captured


@pytest.fixture
def deleted_step_ids() -> list[str]:
    return []


@pytest.fixture
def stub_execution_toolset(deleted_step_ids: list[str]) -> Iterator[None]:
    """The execution agent with one approval-gated tool that records its calls."""

    async def delete_step(ctx: RunContext[AgentDeps], step_id: str) -> str:
        del ctx
        deleted_step_ids.append(step_id)
        return f"deleted {step_id}"

    toolset = FunctionToolset[AgentDeps](
        tools=[Tool(delete_step, requires_approval=True)],
    )
    with execution_agent.override(
        toolsets=[toolset],
        instructions=_TEST_INSTRUCTIONS,
    ):
        yield


def _lead_model(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    seen_prompts: list[str] | None = None,
) -> None:
    monkeypatch.setattr(
        lead_node,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name=tool_name,
            tool_args={"reason": "scripted dispatch"},
            final_args=_LEAD_FINAL,
            seen_prompts=seen_prompts,
        ),
    )


async def test_the_turn_ends_deferred_on_the_sub_agents_approval(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _lead_model(monkeypatch, "verify_strategy")
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="optimize_search_parameters",
            tool_args=_OPTIMIZE_ARGS,
            final_args=_VERIFICATION_FINAL,
        ),
    )
    state = _state()
    deps = _deps(state)

    with verification_agent.override(
        toolsets=[verification.build_toolset()],
        instructions=_TEST_INSTRUCTIONS,
    ):
        capture = await _drive(state=state, deps=deps, writer=writer)

    pending = capture.pending_approval
    assert pending is not None
    assert capture.response is None
    assert pending.phase == "verification"
    assert pending.tool_name == "verify_strategy"
    assert pending.tool_call_id == "call_verify_strategy"
    assert pending.sub_agent is not None
    assert pending.sub_agent.role == "verification"
    inner = pending.sub_agent.approvals[0]
    assert inner.tool_call_id == "call_optimize_search_parameters"
    assert inner.tool_name == "optimize_search_parameters"

    approvals = writer.chunks_of("tool-approval-request")
    assert [c["toolCallId"] for c in approvals] == ["call_optimize_search_parameters"]
    # The Lead's own dispatch call stays plumbing: it never reaches the client.
    assert all(
        c["toolCallId"] != "call_verify_strategy"
        for c in writer.chunks_of("tool-input-available")
    )
    lead_history = ModelMessagesTypeAdapter.validate_json(pending.prior_messages_json)
    assert any(c.tool_name == "verify_strategy" for c in _tool_calls(lead_history))


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_the_answer_finishes_the_sub_agent_and_the_lead_replies(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    _lead_model(monkeypatch, "recover_failed_steps")
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    deps = _deps(state)
    first = await _drive(state=state, deps=deps, writer=writer)
    pending = first.pending_approval
    assert pending is not None
    assert deleted_step_ids == []

    resumed_state = _state()
    resumed_state.user_message_id = state.user_message_id
    resumed_state.pending_approval = pending
    resumed_state.approval_responses = {
        "call_delete_step": ToolApprovalResponded(
            id="call_delete_step",
            approved=True,
        ),
    }
    resumed_deps = _deps(resumed_state)
    second = await _drive(state=resumed_state, deps=resumed_deps, writer=writer)

    assert deleted_step_ids == ["s2"]
    assert second.approval_consumed is True
    assert second.pending_approval is None
    assert second.response is not None
    assert second.response.prose == "scripted"
    outputs = writer.chunks_of("tool-output-available")
    assert "call_delete_step" in [c["toolCallId"] for c in outputs]
    # The dispatch call is plumbing on both turns, so the client is never left
    # with a tool part it cannot resolve.
    named = {
        chunk.get("toolCallId")
        for kind in (
            "tool-input-start",
            "tool-input-available",
            "tool-output-available",
            "tool-approval-request",
        )
        for chunk in writer.chunks_of(kind)
    }
    assert "call_recover_failed_steps" not in named


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_an_answer_naming_the_dispatch_call_still_answers_the_tool(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """A client that answers the Lead's dispatch call (the chat debugger does)
    answers the approvals that call is waiting on."""
    _lead_model(monkeypatch, "recover_failed_steps")
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None

    resumed_state = _state()
    resumed_state.user_message_id = state.user_message_id
    resumed_state.pending_approval = pending
    resumed_state.approval_responses = {
        "call_recover_failed_steps": ToolApprovalResponded(
            id="call_recover_failed_steps",
            approved=True,
        ),
    }
    second = await _drive(
        state=resumed_state,
        deps=_deps(resumed_state),
        writer=writer,
    )

    assert deleted_step_ids == ["s2"]
    assert second.response is not None
    assert second.pending_approval is None


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_second_approval_defers_the_turn_again(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    _lead_model(monkeypatch, "recover_failed_steps")
    monkeypatch.setattr(sub_agent_tools, "get_mock_model", _two_delete_model)
    state = _state()
    deps = _deps(state)
    first = await _drive(state=state, deps=deps, writer=writer)
    pending = first.pending_approval
    assert pending is not None
    assert pending.sub_agent is not None
    assert pending.sub_agent.approvals[0].tool_call_id == "call_delete_1"

    resumed_state = _state()
    resumed_state.user_message_id = state.user_message_id
    resumed_state.pending_approval = pending
    resumed_state.approval_responses = {
        "call_delete_1": ToolApprovalResponded(id="call_delete_1", approved=True),
    }
    second = await _drive(
        state=resumed_state,
        deps=_deps(resumed_state),
        writer=writer,
    )

    assert deleted_step_ids == ["s1"]
    assert second.response is None
    second_pending = second.pending_approval
    assert second_pending is not None
    assert second_pending.tool_call_id == "call_recover_failed_steps"
    assert second_pending.sub_agent is not None
    assert second_pending.sub_agent.approvals[0].tool_call_id == "call_delete_2"


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_typed_denial_denies_the_tool_and_reaches_the_lead(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """Typing instead of clicking denies the tool once and delivers the text."""
    seen_prompts: list[str] = []
    _lead_model(monkeypatch, "recover_failed_steps", seen_prompts)
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None

    typed_state = _state()
    typed_state.pending_approval = pending
    typed_state.user_message_id = uuid4()
    typed_state.user_prompt = "no, keep that step"
    second = await _drive(
        state=typed_state,
        deps=_deps(typed_state),
        writer=writer,
    )

    assert deleted_step_ids == []
    assert second.pending_approval is None
    assert second.response is not None
    assert second.response.prose == "scripted"
    assert "no, keep that step" in seen_prompts
    denied = writer.chunks_of("tool-output-denied")
    assert [c["toolCallId"] for c in denied] == ["call_delete_step"]


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_typed_approval_runs_the_tool_and_delivers_no_prompt(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    seen_prompts: list[str] = []
    _lead_model(monkeypatch, "recover_failed_steps", seen_prompts)
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None

    typed_state = _state()
    typed_state.pending_approval = pending
    typed_state.user_message_id = uuid4()
    typed_state.user_prompt = "yes, go ahead"
    second = await _drive(
        state=typed_state,
        deps=_deps(typed_state),
        writer=writer,
    )

    assert deleted_step_ids == ["s2"]
    assert second.response is not None
    assert "yes, go ahead" not in seen_prompts


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_turn_with_no_answer_never_re_runs_the_dispatch(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """An unresolved dispatch call would be re-executed by pydantic-ai, so a
    turn that answers nothing keeps the card and runs no sub-agent."""
    _lead_model(monkeypatch, "recover_failed_steps")
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None
    started_before = len(writer.chunks_of("data-sub-agent-step"))

    idle_state = _state()
    idle_state.user_message_id = state.user_message_id
    idle_state.pending_approval = pending
    second = await _drive(
        state=idle_state,
        deps=_deps(idle_state),
        writer=writer,
    )

    assert deleted_step_ids == []
    assert second.response is None
    assert second.pending_approval == pending
    assert len(writer.chunks_of("data-sub-agent-step")) == started_before


def _consult_and_dispatch_model() -> FunctionModel:
    """One response that both asks the user a question and dispatches a sub-agent."""

    def _parts(messages: list[ModelMessage]) -> list[ToolCallPart]:
        names = {c.tool_name for c in _tool_calls(messages)}
        if "recover_failed_steps" not in names:
            return [
                ToolCallPart(
                    tool_name="consult_user",
                    args={"questions": [{"id": "q1", "prompt": "Which step?"}]},
                    tool_call_id="call_consult",
                ),
                ToolCallPart(
                    tool_name="recover_failed_steps",
                    args={"reason": "drop the failed step"},
                    tool_call_id="call_recover_failed_steps",
                ),
            ]
        return [
            ToolCallPart(
                tool_name="final_result",
                args=_LEAD_FINAL,
                tool_call_id=f"call_final_{uuid4().hex[:8]}",
            ),
        ]

    return _model(_parts)


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_consult_beside_a_dispatch_loses_neither(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """A response that defers both a consult and a dispatch: the sub-agent's
    approval is the pending one, and the consult answer still lands."""
    monkeypatch.setattr(lead_node, "get_mock_model", _consult_and_dispatch_model)
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="delete_step",
            tool_args={"step_id": "s2"},
            final_args=_RECOVERY_FINAL,
        ),
    )
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None
    assert pending.tool_call_id == "call_recover_failed_steps"
    assert pending.sub_agent is not None
    assert pending.sub_agent.approvals[0].tool_call_id == "call_delete_step"

    resumed_state = _state()
    resumed_state.user_message_id = state.user_message_id
    resumed_state.pending_approval = pending
    resumed_state.approval_responses = {
        "call_delete_step": ToolApprovalResponded(id="call_delete_step", approved=True),
        "call_consult": ToolApprovalResponded(id="call_consult", approved=True),
    }
    second = await _drive(
        state=resumed_state,
        deps=_deps(resumed_state),
        writer=writer,
    )

    assert deleted_step_ids == ["s2"]
    assert second.pending_approval is None
    assert second.response is not None
    assert second.response.prose == "scripted"


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_a_click_after_a_typed_reply_delivers_no_stale_text(
    writer: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """The typed reply is spent on the denial that raised the second approval,
    so answering that one carries no leftover message."""
    seen_prompts: list[str] = []
    _lead_model(monkeypatch, "recover_failed_steps", seen_prompts)
    monkeypatch.setattr(sub_agent_tools, "get_mock_model", _two_delete_model)
    state = _state()
    first = await _drive(state=state, deps=_deps(state), writer=writer)
    pending = first.pending_approval
    assert pending is not None
    assert pending.sub_agent is not None
    assert pending.sub_agent.approvals[0].tool_call_id == "call_delete_1"

    typed_state = _state()
    typed_state.pending_approval = pending
    typed_state.user_message_id = uuid4()
    typed_state.user_prompt = "no, keep that step"
    second = await _drive(
        state=typed_state,
        deps=_deps(typed_state),
        writer=writer,
    )
    second_pending = second.pending_approval
    assert second_pending is not None
    assert second.response is None
    assert deleted_step_ids == []
    assert second_pending.sub_agent is not None
    assert second_pending.sub_agent.approvals[0].tool_call_id == "call_delete_2"

    idle_state = _state()
    idle_state.pending_approval = second_pending
    idle_state.user_message_id = typed_state.user_message_id
    idle_state.user_prompt = typed_state.user_prompt
    third = await _drive(
        state=idle_state,
        deps=_deps(idle_state),
        writer=writer,
    )
    assert third.response is None
    assert third.pending_approval == second_pending
    assert "no, keep that step" not in seen_prompts

    click_state = _state()
    click_state.pending_approval = second_pending
    click_state.user_message_id = typed_state.user_message_id
    click_state.user_prompt = typed_state.user_prompt
    click_state.approval_responses = {
        "call_delete_2": ToolApprovalResponded(id="call_delete_2", approved=True),
    }
    fourth = await _drive(
        state=click_state,
        deps=_deps(click_state),
        writer=writer,
    )

    assert deleted_step_ids == ["s2"]
    assert fourth.response is not None
    assert fourth.pending_approval is None
    assert "no, keep that step" not in seen_prompts
