"""A dispatch that stops early reports the stop to the Lead as typed data.

A sub-agent that runs out of calls, or repeats one call until the guard ends
the run, returns no delta. The stop is recorded on the Lead's deps, rendered
in the ledger the Lead reads, and a budget stop that made progress is retried
by the dispatch rather than by the user.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import pytest
from assistant_core.capabilities.repetition_guard import ToolRepetitionGuard
from pydantic_ai import RunContext, Tool
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_dispatch, sub_agent_stream
from pathfinder.ai.lead.deltas import FrameResult
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_context import agent_deps_for
from pathfinder.ai.lead.phase_stop import PhaseStop, PhaseStopReason
from pathfinder.ai.lead.sub_agent_dispatch import frame_work_order, run_frame
from pathfinder.ai.lead.sub_agent_stream import PhaseRun, stream_sub_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.tests._support.sub_agents import pinned_sub_agent


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps() -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Find the kinases.",
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
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
    )


class _Collector:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


@pytest.fixture(autouse=True)
def collector(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    monkeypatch.setattr(
        sub_agent_stream,
        "phase_override_kwargs",
        lambda runtime, role: {},
    )
    return captured


def _tool_loop_model(tool_name: str) -> FunctionModel:
    """A model that calls one tool on every step and never finishes."""

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(
            parts=[
                ToolCallPart(tool_name=tool_name, args="{}", tool_call_id=uuid4().hex)
            ]
        )

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[dict[int, DeltaToolCall]]:
        part = _fn(messages, info).parts[0]
        assert isinstance(part, ToolCallPart)
        yield {
            0: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            ),
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


def _frame_result_model() -> FunctionModel:
    """A model that returns a FrameResult on its first step."""

    args = {"summary": "one criterion bound", "disposition": "needs_user"}

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result", args=args, tool_call_id="call_final"
                )
            ]
        )

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[dict[int, DeltaToolCall]]:
        part = _fn(messages, info).parts[0]
        assert isinstance(part, ToolCallPart)
        yield {
            0: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            ),
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


async def bind_one(ctx: RunContext[AgentDeps]) -> str:
    """Bind one more criterion into the shared draft, as FRAME's tools do."""
    draft = ctx.deps.agent_state.operational_spec_draft
    index = len(draft.criteria)
    draft.criteria.append(
        Criterion(
            id=f"c{index}",
            text=f"criterion {index}",
            search_name="GenesByText",
        ),
    )
    return "bound"


async def ping(ctx: RunContext[AgentDeps]) -> str:
    del ctx
    return "pong"


def _pinned(
    monkeypatch: pytest.MonkeyPatch, model: FunctionModel, tool: Any
) -> Iterator[None]:
    toolset = FunctionToolset[AgentDeps](tools=[Tool(tool)])
    with pinned_sub_agent(
        monkeypatch,
        "frame",
        model=model,
        toolsets=[toolset],
        instructions="Call the tool.",
    ):
        yield


@pytest.fixture
def binding_frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield from _pinned(monkeypatch, _tool_loop_model("bind_one"), bind_one)


@pytest.fixture
def looping_frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield from _pinned(monkeypatch, _tool_loop_model("ping"), ping)


@pytest.fixture
def answering_frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield from _pinned(monkeypatch, _frame_result_model(), ping)


async def _dispatch(
    deps: LeadDeps,
    declared: int = 8,
    guard: ToolRepetitionGuard | None = None,
) -> object:
    agent_deps = agent_deps_for(deps)
    if guard is not None:
        agent_deps.tool_repetition_guard = guard
    return await stream_sub_agent(
        run=PhaseRun("frame", frame_work_order("bind the criteria", ""), declared),
        agent_deps=agent_deps,
        parent_tool_call_id="call_frame_1",
        expected_output_type=FrameResult,
        deps=deps,
    )


@pytest.mark.asyncio
async def test_a_budget_stop_is_recorded_with_its_numbers(
    monkeypatch: pytest.MonkeyPatch,
    binding_frame: None,
) -> None:
    monkeypatch.setattr(
        sub_agent_stream,
        "phase_usage_limits",
        lambda declared_criteria: UsageLimits(
            request_limit=10,
            tool_calls_limit=3,
            total_tokens_limit=2_000_000,
        ),
    )
    deps = _deps()

    delta = await _dispatch(deps)

    assert delta is None
    stop = deps.last_phase_stop
    assert stop is not None
    assert stop.reason is PhaseStopReason.BUDGET
    assert stop.role == "frame"
    assert stop.tool_calls == 3
    assert stop.criteria_bound == 3
    assert stop.criteria_declared == 8


@pytest.mark.asyncio
async def test_a_repetition_stop_names_the_repeated_call(
    looping_frame: None,
) -> None:
    guard = ToolRepetitionGuard(
        read_only_tools=frozenset({"ping"}),
        threshold=2,
    )
    deps = _deps()

    delta = await _dispatch(deps, guard=guard)

    assert delta is None
    stop = deps.last_phase_stop
    assert stop is not None
    assert stop.reason is PhaseStopReason.REPEATED_CALL
    assert stop.role == "frame"


@pytest.mark.asyncio
async def test_a_clean_dispatch_records_no_stop(answering_frame: None) -> None:
    deps = _deps()

    delta = await _dispatch(deps)

    assert isinstance(delta, FrameResult)
    assert deps.last_phase_stop is None


@pytest.mark.asyncio
async def test_an_earlier_stop_does_not_reach_a_later_clean_pass(
    answering_frame: None,
) -> None:
    deps = _deps()
    deps.last_phase_stop = PhaseStop(
        role="frame",
        reason=PhaseStopReason.BUDGET,
        tool_calls=60,
        criteria_bound=3,
        criteria_declared=8,
    )

    await _dispatch(deps)

    assert deps.last_phase_stop is None


def test_the_ledger_the_lead_reads_names_the_stop() -> None:
    state = _deps().state
    stop = PhaseStop(
        role="frame",
        reason=PhaseStopReason.BUDGET,
        tool_calls=60,
        criteria_bound=3,
        criteria_declared=8,
    )

    summary = derive_ledger(state, None, phase_stop=stop).render_summary()

    assert (
        "- stopped: the framing pass stopped on its call budget after 60 calls "
        "with 3 of 8 criteria bound" in summary
    )


def test_a_repetition_stop_renders_without_criteria_counts() -> None:
    stop = PhaseStop(
        role="verification",
        reason=PhaseStopReason.REPEATED_CALL,
        tool_calls=12,
    )

    assert stop.render() == (
        "the verification pass stopped after repeating one call after 12 calls"
    )


def test_a_ledger_snapshot_keeps_the_stop_off_the_wire() -> None:
    stop = PhaseStop(role="frame", reason=PhaseStopReason.BUDGET, tool_calls=60)
    ledger = derive_ledger(_deps().state, None, phase_stop=stop)

    dumped = ledger.model_dump(by_alias=True, mode="json", exclude_none=True)

    assert "phaseStop" not in dumped


def _requirement(kind: ConstraintKind, label: str, value: str) -> Constraint:
    return Constraint(
        kind=kind,
        label=label,
        requested_value=value,
        source=ConstraintSource.USER_EXPLICIT,
    )


@pytest.fixture
def stopping_dispatches(monkeypatch: pytest.MonkeyPatch) -> list[PhaseRun]:
    """Every dispatch, each stopping on its budget after binding one criterion."""
    runs: list[PhaseRun] = []

    async def _stub(
        *, run: PhaseRun, agent_deps: AgentDeps, deps: LeadDeps, **kwargs: object
    ) -> None:
        del kwargs
        deps.last_phase_stop = None
        runs.append(run)
        draft = agent_deps.agent_state.operational_spec_draft
        index = len(draft.criteria)
        draft.criteria.append(
            Criterion(
                id=f"c{index}",
                text=f"criterion {index}",
                search_name="GenesByText",
            ),
        )
        deps.last_phase_stop = PhaseStop(
            role="frame",
            reason=PhaseStopReason.BUDGET,
            tool_calls=60,
            criteria_bound=index + 1,
            criteria_declared=run.declared_criteria,
        )

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _stub)
    return runs


@pytest.fixture
def barren_dispatches(monkeypatch: pytest.MonkeyPatch) -> list[PhaseRun]:
    """Every dispatch, each stopping on its budget having bound nothing."""
    runs: list[PhaseRun] = []

    async def _stub(*, run: PhaseRun, deps: LeadDeps, **kwargs: object) -> None:
        del kwargs
        runs.append(run)
        deps.last_phase_stop = PhaseStop(
            role="frame",
            reason=PhaseStopReason.BUDGET,
            tool_calls=60,
            criteria_bound=0,
            criteria_declared=run.declared_criteria,
        )

    monkeypatch.setattr(sub_agent_dispatch, "stream_sub_agent", _stub)
    return runs


@pytest.mark.asyncio
async def test_a_budget_stop_with_progress_is_dispatched_again(
    stopping_dispatches: list[PhaseRun],
) -> None:
    deps = _deps()
    deps.state.domain.requirements = [
        _requirement(ConstraintKind.ORGANISM, "organism", "Plasmodium falciparum"),
        _requirement(ConstraintKind.DATA_TYPE, "expression dataset", "trophozoite"),
        _requirement(ConstraintKind.PERCENTILE, "high expression", "top 10%"),
        _requirement(ConstraintKind.STATISTICAL_THRESHOLD, "dN/dS", "> 1.0"),
    ]

    result = await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("operationalize the goal", "kinases"),
        expected_criteria=3,
    )

    assert isinstance(result, FrameResult)
    assert [run.declared_criteria for run in stopping_dispatches] == [4, 4]
    assert "c0" in stopping_dispatches[1].work_order


@pytest.mark.asyncio
async def test_an_edit_continues_as_an_edit(
    stopping_dispatches: list[PhaseRun],
) -> None:
    deps = _deps()
    deps.state.domain.spec_before_turn = OperationalSpec(
        goal="find the kinases",
        criteria=[
            Criterion(id="k1", text="kinase domain", search_name="GenesByText"),
        ],
    )

    await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("change the organism", "kinases"),
        expected_criteria=3,
    )

    assert len(stopping_dispatches) == 2
    assert stopping_dispatches[1].work_order.startswith("EDIT work order:")


@pytest.mark.asyncio
async def test_the_automatic_retry_runs_once_per_turn(
    stopping_dispatches: list[PhaseRun],
) -> None:
    deps = _deps()

    await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("operationalize the goal", "kinases"),
        expected_criteria=3,
    )

    assert len(stopping_dispatches) == 2
    assert deps.frame_retried_after_stop is True


@pytest.mark.asyncio
async def test_a_stop_that_bound_nothing_is_not_dispatched_again(
    barren_dispatches: list[PhaseRun],
) -> None:
    deps = _deps()

    result = await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("operationalize the goal", "kinases"),
        expected_criteria=3,
    )

    assert isinstance(result, FrameResult)
    assert len(barren_dispatches) == 1
    assert result.disposition == "needs_user"
    assert "no criteria bound" in result.summary
