"""An approval-required tool inside a sub-agent reaches the user.

The sub-agent run stops with ``DeferredToolRequests``; the dispatch forwards the
inner call as a tool part, waits, and the user's answer re-enters the same run.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import pytest
from assistant_core.graph.turn_state import PendingApproval
from pydantic_ai import Agent, DeferredToolRequests, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.tools import DeferredToolResults, ToolDenied
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.execution import EXECUTION_MODEL, ExecutionAgent
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_stream, sub_agent_tools
from pathfinder.ai.lead.deltas import FrameResult, RecoveryDelta
from pathfinder.ai.lead.sub_agent_dispatch import (
    resume_sub_agent,
    run_frame,
    run_recovery,
    run_verification,
)
from pathfinder.ai.lead.sub_agent_stream import SubAgentApprovalWait, SubAgentResume
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, SubAgentRunUsage
from pathfinder.ai.tools.toolsets import execution, verification
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.tests._support.sub_agents import pinned_sub_agent

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
_DELETE_ARGS: dict[str, Any] = {"step_id": "s2"}
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

_TEST_INSTRUCTIONS = "Call the tool the script names, then return the typed output."


def _scripted(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    final_args: dict[str, Any],
) -> FunctionModel:
    """Call ``tool_name`` once, then emit the agent's typed output."""

    def _part(messages: list[ModelMessage]) -> ToolCallPart:
        already = {
            part.tool_name
            for msg in messages
            if isinstance(msg, ModelResponse)
            for part in msg.parts
            if isinstance(part, ToolCallPart)
        }
        if tool_name not in already:
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

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        return ModelResponse(parts=[_part(messages)])

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del info
        part = _part(messages)
        yield {
            0: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            ),
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


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


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps(usage_log: list[SubAgentRunUsage] | None = None) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Tune the RNA-Seq fold change against my controls.",
    )
    state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1", "s2"],
        failed_steps=[],
        root_count=0,
    )
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    recorded = usage_log if usage_log is not None else []
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
        record_sub_agent_usage=recorded.append,
    )


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    return captured


@pytest.fixture
def deleted_step_ids() -> list[str]:
    return []


@pytest.fixture
def stub_execution_toolset(
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> Iterator[None]:
    """The execution agent with one approval-gated tool that records its calls."""

    async def delete_step(ctx: RunContext[AgentDeps], step_id: str) -> str:
        del ctx
        deleted_step_ids.append(step_id)
        return f"deleted {step_id}"

    toolset = FunctionToolset[AgentDeps](
        tools=[Tool(delete_step, requires_approval=True)],
    )
    with pinned_sub_agent(
        monkeypatch,
        "execution",
        toolsets=[toolset],
        instructions=_TEST_INSTRUCTIONS,
    ):
        yield


async def test_verification_approval_reaches_the_client(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="optimize_search_parameters",
            tool_args=_OPTIMIZE_ARGS,
            final_args=_VERIFICATION_FINAL,
        ),
    )
    deps = _deps()

    with pinned_sub_agent(
        monkeypatch,
        "verification",
        toolsets=[verification.build_toolset()],
        instructions=_TEST_INSTRUCTIONS,
    ):
        result = await run_verification(
            deps=deps,
            parent_tool_call_id="lead_call_verify",
            reason="optimize the RNA-Seq fold change against the controls",
        )

    assert isinstance(result, SubAgentApprovalWait)
    assert result.pending.role == "verification"
    call = result.pending.approvals[0]
    assert call.tool_name == "optimize_search_parameters"
    assert call.tool_call_id == "call_optimize_search_parameters"
    assert call.args["settings"] == {"budget": 8, "objective": "f1"}

    started = collector.chunks_of("tool-input-start")
    assert [c["toolCallId"] for c in started] == ["call_optimize_search_parameters"]
    assert started[0]["toolName"] == "optimize_search_parameters"
    available = collector.chunks_of("tool-input-available")
    assert available[0]["input"]["target"]["search_name"] == "GenesByRNASeqEvidence"
    approval = collector.chunks_of("tool-approval-request")
    assert approval == [
        {
            "type": "tool-approval-request",
            "approvalId": "call_optimize_search_parameters",
            "toolCallId": "call_optimize_search_parameters",
        },
    ]

    replay = ModelMessagesTypeAdapter.validate_json(result.pending.messages_json)
    assert any(
        part.tool_name == "optimize_search_parameters"
        for msg in replay
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    )


async def test_execution_approval_reaches_the_client(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="delete_step",
            tool_args=_DELETE_ARGS,
            final_args=_RECOVERY_FINAL,
        ),
    )
    deps = _deps()

    with pinned_sub_agent(
        monkeypatch,
        "execution",
        toolsets=[execution.build_toolset()],
        instructions=_TEST_INSTRUCTIONS,
    ):
        result = await run_recovery(
            deps=deps,
            parent_tool_call_id="lead_call_recover",
            reason="drop the step that failed to push",
        )

    assert isinstance(result, SubAgentApprovalWait)
    assert result.pending.role == "execution"
    call = result.pending.approvals[0]
    assert (call.tool_name, call.tool_call_id) == ("delete_step", "call_delete_step")
    assert call.args == {"step_id": "s2"}
    assert collector.chunks_of("tool-approval-request")[0]["approvalId"] == (
        "call_delete_step"
    )


async def test_a_resumed_dispatch_runs_on_a_freshly_built_agent(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    """The answer re-enters from the stored messages, so the second half of a
    dispatch runs on the agent that half built."""
    del collector
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="delete_step",
            tool_args=_DELETE_ARGS,
            final_args=_RECOVERY_FINAL,
        ),
    )

    async def delete_step(ctx: RunContext[AgentDeps], step_id: str) -> str:
        del ctx
        deleted_step_ids.append(step_id)
        return f"deleted {step_id}"

    built: list[ExecutionAgent] = []

    def build() -> ExecutionAgent:
        agent: ExecutionAgent = Agent(
            EXECUTION_MODEL,
            output_type=[RecoveryDelta, DeferredToolRequests],
            deps_type=AgentDeps,
            instructions=_TEST_INSTRUCTIONS,
            toolsets=[
                FunctionToolset[AgentDeps](
                    tools=[Tool(delete_step, requires_approval=True)],
                ),
            ],
            name="execution",
            defer_model_check=True,
        )
        built.append(agent)
        return agent

    monkeypatch.setitem(sub_agent_tools.BUILD_SUB_AGENT_BY_ROLE, "execution", build)
    deps = _deps()

    waiting = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
    )
    assert isinstance(waiting, SubAgentApprovalWait)

    resumed = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
        resume=SubAgentResume(
            messages=ModelMessagesTypeAdapter.validate_json(
                waiting.pending.messages_json,
            ),
            results=DeferredToolResults(approvals={"call_delete_step": True}),
        ),
    )

    assert isinstance(resumed, RecoveryDelta)
    assert deleted_step_ids == ["s2"]
    assert len(built) == 2
    assert built[0] is not built[1]


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_approval_runs_the_inner_tool_and_returns_the_delta(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="delete_step",
            tool_args=_DELETE_ARGS,
            final_args=_RECOVERY_FINAL,
        ),
    )
    usage_log: list[SubAgentRunUsage] = []
    deps = _deps(usage_log)

    waiting = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
    )
    assert isinstance(waiting, SubAgentApprovalWait)
    assert deleted_step_ids == []

    resumed = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
        resume=SubAgentResume(
            messages=ModelMessagesTypeAdapter.validate_json(
                waiting.pending.messages_json,
            ),
            results=DeferredToolResults(approvals={"call_delete_step": True}),
        ),
    )

    assert isinstance(resumed, RecoveryDelta)
    assert resumed.actions_taken == ["deleted s2"]
    assert deleted_step_ids == ["s2"]
    outputs = collector.chunks_of("tool-output-available")
    assert [c["toolCallId"] for c in outputs] == ["call_delete_step"]
    # Each half of the dispatch is charged once, under the Lead's call id.
    assert [u.parent_tool_call_id for u in usage_log] == [
        "lead_call_recover",
        "lead_call_recover",
    ]
    assert all(u.usage.total_tokens > 0 for u in usage_log)


@pytest.mark.usefixtures("stub_execution_toolset")
async def test_denial_finishes_the_sub_agent_without_running_the_tool(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
    deleted_step_ids: list[str],
) -> None:
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="delete_step",
            tool_args=_DELETE_ARGS,
            final_args=_RECOVERY_FINAL,
        ),
    )
    deps = _deps()

    waiting = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
    )
    assert isinstance(waiting, SubAgentApprovalWait)

    resumed = await run_recovery(
        deps=deps,
        parent_tool_call_id="lead_call_recover",
        reason="drop the step that failed to push",
        resume=SubAgentResume(
            messages=ModelMessagesTypeAdapter.validate_json(
                waiting.pending.messages_json,
            ),
            results=DeferredToolResults(
                approvals={
                    "call_delete_step": ToolDenied(message="Keep that step."),
                },
            ),
        ),
    )

    assert isinstance(resumed, RecoveryDelta)
    assert deleted_step_ids == []
    denied = collector.chunks_of("tool-output-denied")
    assert [c["toolCallId"] for c in denied] == ["call_delete_step"]
    # A tool the user refused reads "denied", not "completed" and not "failed".
    steps = [
        chunk["data"]
        for chunk in collector.chunks_of("data-sub-agent-step")
        if chunk["data"].get("toolCallId") == "call_delete_step"
    ]
    assert [step["state"] for step in steps] == ["started", "started", "denied"]
    assert "Keep that step." in steps[-1]["resultSummary"]


async def test_the_stored_dispatch_arguments_drive_the_re_entry(
    collector: _Collector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The frame dispatch resumes from what the checkpoint holds: its tool
    name and the arguments the Lead called it with."""
    bound_criteria: list[str] = []

    async def bind_criterion(ctx: RunContext[AgentDeps], criterion_id: str) -> str:
        del ctx
        bound_criteria.append(criterion_id)
        return f"bound {criterion_id}"

    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _scripted(
            tool_name="bind_criterion",
            tool_args={"criterion_id": "c1"},
            final_args={"summary": "bound one", "disposition": "spec_ready"},
        ),
    )
    deps = _deps()
    toolset = FunctionToolset[AgentDeps](
        tools=[Tool(bind_criterion, requires_approval=True)],
    )

    with pinned_sub_agent(
        monkeypatch,
        "frame",
        toolsets=[toolset],
        instructions=_TEST_INSTRUCTIONS,
    ):
        waiting = await run_frame(
            deps=deps,
            parent_tool_call_id="lead_call_frame",
            reason="operationalize the goal",
            expected_criteria=5,
        )
        assert isinstance(waiting, SubAgentApprovalWait)
        assert waiting.pending.role == "frame"
        assert bound_criteria == []

        resumed = await resume_sub_agent(
            deps=deps,
            approval=PendingApproval(
                phase="frame",
                tool_call_id="lead_call_frame",
                tool_name="frame_problem",
                tool_args={"reason": "operationalize the goal", "expected_criteria": 5},
                sub_agent=waiting.pending,
            ),
            resume=SubAgentResume(
                messages=ModelMessagesTypeAdapter.validate_json(
                    waiting.pending.messages_json,
                ),
                results=DeferredToolResults(approvals={"call_bind_criterion": True}),
            ),
        )

    assert isinstance(resumed, FrameResult)
    assert resumed.summary == "bound one"
    assert bound_criteria == ["c1"]
    assert [c["toolCallId"] for c in collector.chunks_of("tool-output-available")] == [
        "call_bind_criterion",
    ]
