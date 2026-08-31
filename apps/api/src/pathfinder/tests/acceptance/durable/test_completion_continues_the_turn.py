"""Acceptance: a durable tool is a deferred tool.

The turn that calls one ends deferred, and the worker's completion opens a NEW
turn that answers the parked call. Nothing before the call runs a second time.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from assistant_core.graph.turn_state import DurableTaskResult
from pydantic_ai import Agent, DeferredToolRequests, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph import _lead_model
from pathfinder.ai.graph._lead_capture import _LeadRunCapture
from pathfinder.ai.graph.lead_node import _drive_lead_stream
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_stream, sub_agent_tools
from pathfinder.ai.lead.lead_agent import LEAD_MODEL, LeadAgent, LeadResponse
from pathfinder.ai.lead.sub_agent_dispatch import verify_strategy
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools import durable
from pathfinder.ai.tools.standalone.eda_compute import run_eda_compute
from pathfinder.ai.tools.toolsets import verification
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.tests._support.sub_agents import pinned_sub_agent

_TASK_ID = UUID("0c6100d2-0000-4000-8000-000000000001")
_DATASET = "DS_e973eadd57"
_ANALYSIS = "13FVNaz"
_GENE_SET = "gs-1"

_COMPUTE_ARGS: dict[str, Any] = {
    "identifier_variable": {
        "entityId": "EUPATH_0000609",
        "variableId": "VEUPATHDB_GENE_ID",
    },
    "value_variable": {
        "entityId": "EUPATH_0000609",
        "variableId": "SEQUENCE_READ_COUNT",
    },
    "comparator_variable": {
        "entityId": "EUPATH_0000096",
        "variableId": "VAR_febrile",
    },
    "group_a_labels": ["normal"],
    "group_b_labels": ["febrile"],
    "method": "DESeq",
}

_COMPUTE_RESULT: dict[str, Any] = {
    "genesTested": 5511,
    "retainedUp": 529,
    "retainedDown": 1014,
}

_ENRICHMENT_RESULT: dict[str, Any] = {
    "geneSetId": _GENE_SET,
    "geneSetName": "febrile up",
    "geneCount": 1543,
    "totalSignificantTerms": 7,
    "analysisTypesRun": ["go_process"],
    "enrichmentResults": [{"goId": "GO:0004672", "goTerm": "protein kinase"}],
}

_VERIFICATION_FINAL: dict[str, Any] = {
    "digest": {
        "disposition": "done",
        "prose": "7 enriched terms confirm the set",
        "reason": "enrichment returned",
        "success": True,
    },
}
_LEAD_FINAL: dict[str, Any] = {"prose": "scripted", "nextState": "await_user"}
_INSTRUCTIONS = "Call the tool the script names, then return the typed output."


class _Collector:
    """Stands in for the langgraph stream writer."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)

    def mark(self) -> int:
        return len(self.payloads)

    def chunks(self, *, after: int = 0) -> list[dict[str, Any]]:
        return [p["chunk"] for p in self.payloads[after:] if "chunk" in p]

    def chunks_of(self, chunk_type: str, *, after: int = 0) -> list[dict[str, Any]]:
        return [c for c in self.chunks(after=after) if c.get("type") == chunk_type]


class _Deferred:
    """Records what the durable decorator handed the worker."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.jobs: list[dict[str, Any]] = []

    def configure_task(self, **kwargs: Any) -> _Deferred:
        self.jobs.append(kwargs)
        return self

    async def defer_async(self, **kwargs: Any) -> None:
        self.jobs[-1] = {**self.jobs[-1], **kwargs}


@pytest.fixture
def deferred(monkeypatch: pytest.MonkeyPatch) -> _Deferred:
    recorder = _Deferred()

    async def _create(**kwargs: Any) -> UUID:
        recorder.created.append(kwargs)
        return _TASK_ID

    monkeypatch.setattr(durable, "create_background_task", _create)
    monkeypatch.setattr(durable, "procrastinate_app", recorder)
    return recorder


@pytest.fixture
def writer(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    monkeypatch.setattr(durable, "get_stream_writer", lambda: captured)
    return captured


def _tool_calls(messages: list[ModelMessage]) -> list[ToolCallPart]:
    return [
        part
        for msg in messages
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    ]


def _model(part_for: Any) -> FunctionModel:
    def _parts(messages: list[ModelMessage]) -> list[ToolCallPart]:
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


def _eda_journey_model() -> FunctionModel:
    """Open one analysis, compute on it, export one step, then answer."""

    def _part(messages: list[ModelMessage]) -> ToolCallPart:
        called = {c.tool_name for c in _tool_calls(messages)}
        if "open_eda_analysis" not in called:
            return ToolCallPart(
                tool_name="open_eda_analysis",
                args={"dataset_id": _DATASET},
                tool_call_id="call_open",
            )
        if "run_eda_compute" not in called:
            return ToolCallPart(
                tool_name="run_eda_compute",
                args=_COMPUTE_ARGS,
                tool_call_id="call_compute",
            )
        if "create_eda_step" not in called:
            return ToolCallPart(
                tool_name="create_eda_step",
                args={"analysis_id": _ANALYSIS},
                tool_call_id="call_step",
            )
        return ToolCallPart(
            tool_name="final_result",
            args=_LEAD_FINAL,
            tool_call_id=f"call_final_{uuid4().hex[:8]}",
        )

    return _model(_part)


def _one_call_model(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    final_args: dict[str, Any],
) -> FunctionModel:
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

    return _model(_part)


def _quota_offline() -> AsyncSession:
    msg = "no database in this acceptance test"
    raise OperationalError(msg, None, Exception(msg))


def _state() -> PipelineState:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Give me the genes 2-fold up in febrile samples as a step.",
        user_message_id=uuid4(),
    )
    state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1"],
        failed_steps=[],
        root_count=16,
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
    agent: LeadAgent,
) -> _LeadRunCapture:
    capture = _LeadRunCapture()
    await _drive_lead_stream(
        state=state,
        agent=agent,
        deps=deps,
        capture=capture,
        writer=writer,
        message_id=uuid4(),
    )
    return capture


@pytest.fixture
def eda_calls() -> dict[str, list[str]]:
    return {"opened": [], "stepped": []}


@pytest.fixture
def eda_lead_agent(eda_calls: dict[str, list[str]]) -> LeadAgent:
    """A Lead that opens an analysis, computes on it, and exports a step."""

    async def open_eda_analysis(ctx: RunContext[LeadDeps], dataset_id: str) -> str:
        del ctx
        eda_calls["opened"].append(dataset_id)
        return f"Analysis {_ANALYSIS} open on {dataset_id}"

    async def create_eda_step(ctx: RunContext[LeadDeps], analysis_id: str) -> str:
        del ctx
        eda_calls["stepped"].append(analysis_id)
        return f"Step created from {analysis_id}"

    agent: LeadAgent = Agent(
        LEAD_MODEL,
        output_type=[LeadResponse, DeferredToolRequests],
        deps_type=LeadDeps,
        instructions=_INSTRUCTIONS,
        tools=[
            Tool(open_eda_analysis),
            Tool(run_eda_compute, sequential=True, max_retries=3),
            Tool(create_eda_step),
        ],
        retries=3,
        name="lead",
        defer_model_check=True,
    )
    return agent


@pytest.fixture
def verify_lead_agent() -> LeadAgent:
    agent: LeadAgent = Agent(
        LEAD_MODEL,
        output_type=[LeadResponse, DeferredToolRequests],
        deps_type=LeadDeps,
        instructions=_INSTRUCTIONS,
        tools=[Tool(verify_strategy)],
        retries=3,
        name="lead",
        defer_model_check=True,
    )
    return agent


@pytest.fixture
def scripted_eda_lead(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(_lead_model, "get_mock_model", _eda_journey_model)
    return


@pytest.mark.usefixtures("scripted_eda_lead")
async def test_the_call_ends_the_turn_deferred_and_defers_exactly_one_job(
    writer: _Collector,
    deferred: _Deferred,
    eda_calls: dict[str, list[str]],
    eda_lead_agent: LeadAgent,
) -> None:
    state = _state()
    deps = _deps(state)

    capture = await _drive(
        state=state,
        deps=deps,
        writer=writer,
        agent=eda_lead_agent,
    )

    assert eda_calls["opened"] == [_DATASET]
    assert eda_calls["stepped"] == []
    assert len(deferred.jobs) == 1
    assert deferred.jobs[0]["name"] == "durable:run_eda_compute"
    assert capture.response is None
    parked = capture.pending_durable_call
    assert parked is not None
    assert parked.task_id == _TASK_ID
    assert parked.tool_call_id == "call_compute"
    assert parked.tool_name == "run_eda_compute"
    assert parked.sub_agent is None
    started = writer.chunks_of("data-background-task-started")
    assert [c["data"]["taskId"] for c in started] == [str(_TASK_ID)]
    assert started[0]["data"]["toolName"] == "run_eda_compute"


@pytest.mark.usefixtures("scripted_eda_lead")
async def test_the_completion_turn_answers_the_call_without_replaying_the_first(
    writer: _Collector,
    deferred: _Deferred,
    eda_calls: dict[str, list[str]],
    eda_lead_agent: LeadAgent,
) -> None:
    state = _state()
    deps = _deps(state)
    first = await _drive(
        state=state,
        deps=deps,
        writer=writer,
        agent=eda_lead_agent,
    )
    parked = first.pending_durable_call
    assert parked is not None

    boundary = writer.mark()
    resumed_state = _state()
    resumed_state.pending_durable_call = parked
    resumed_state.durable_result = DurableTaskResult(
        task_id=_TASK_ID,
        status="success",
        result=_COMPUTE_RESULT,
    )
    second = await _drive(
        state=resumed_state,
        deps=_deps(resumed_state),
        writer=writer,
        agent=eda_lead_agent,
    )

    assert eda_calls["opened"] == [_DATASET]
    assert eda_calls["stepped"] == [_ANALYSIS]
    assert len(deferred.jobs) == 1
    assert second.pending_durable_call is None
    assert second.response is not None
    assert second.response.prose == "scripted"

    outputs = writer.chunks_of("tool-output-available", after=boundary)
    assert next(c["toolCallId"] for c in outputs) == "call_compute"
    summaries = writer.chunks_of("data-tool-summary", after=boundary)
    assert [c["data"]["toolCallId"] for c in summaries] == ["call_compute"]
    assert "5,511 genes tested" in summaries[0]["data"]["summary"]
    inputs = writer.chunks_of("tool-input-available", after=boundary)
    assert "call_open" not in [c["toolCallId"] for c in inputs]


async def test_a_durable_call_inside_the_verify_sub_agent_finishes_on_completion(
    writer: _Collector,
    deferred: _Deferred,
    monkeypatch: pytest.MonkeyPatch,
    verify_lead_agent: LeadAgent,
) -> None:
    monkeypatch.setattr(
        _lead_model,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="verify_strategy",
            tool_args={"reason": "check the build"},
            final_args=_LEAD_FINAL,
        ),
    )
    monkeypatch.setattr(
        sub_agent_tools,
        "get_mock_model",
        lambda: _one_call_model(
            tool_name="run_gene_set_enrichment",
            tool_args={"gene_set_id": _GENE_SET},
            final_args=_VERIFICATION_FINAL,
        ),
    )
    state = _state()
    deps = _deps(state)

    with pinned_sub_agent(
        monkeypatch,
        "verification",
        toolsets=[verification.build_toolset()],
        instructions=_INSTRUCTIONS,
    ):
        first = await _drive(
            state=state,
            deps=deps,
            writer=writer,
            agent=verify_lead_agent,
        )
        parked = first.pending_durable_call
        assert parked is not None
        assert parked.tool_name == "verify_strategy"
        assert parked.tool_call_id == "call_verify_strategy"
        assert parked.sub_agent is not None
        assert parked.sub_agent.role == "verification"
        inner = parked.sub_agent.approvals[0]
        assert inner.tool_name == "run_gene_set_enrichment"
        assert len(deferred.jobs) == 1

        boundary = writer.mark()
        resumed_state = _state()
        resumed_state.pending_durable_call = parked
        resumed_state.durable_result = DurableTaskResult(
            task_id=_TASK_ID,
            status="success",
            result=_ENRICHMENT_RESULT,
        )
        resumed_deps = _deps(resumed_state)
        second = await _drive(
            state=resumed_state,
            deps=resumed_deps,
            writer=writer,
            agent=verify_lead_agent,
        )

    assert len(deferred.jobs) == 1
    assert second.pending_durable_call is None
    digest = resumed_state.domain.verification_digest
    assert digest is not None
    assert digest.prose == "7 enriched terms confirm the set"
    assert digest.success is True
    enrichment = writer.chunks_of("data-enrichment-results", after=boundary)
    assert [c["data"]["geneSetId"] for c in enrichment] == [_GENE_SET]
