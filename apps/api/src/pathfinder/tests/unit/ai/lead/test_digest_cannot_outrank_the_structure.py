"""A verification verdict never blesses a tree the user did not ask for.

The build check reads what was pushed; it cannot see that the spec's own
structure answers another question. A success over a violated combination is
rewritten to the failure the structure holds, and carries its cause.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import FailureCause, PipelineState
from pathfinder.ai.lead import sub_agent_stream, sub_agent_tools
from pathfinder.ai.lead.deltas import VerificationDelta
from pathfinder.ai.lead.ledger import structure_contradiction
from pathfinder.ai.lead.sub_agent_dispatch import run_verification
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.toolsets import verification
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.domain.strategy.graph_model import StepKind, StrategyStep
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.sync_state import WDKSyncState
from pathfinder.tests._support.sub_agents import pinned_sub_agent

_COMBINATION = "mass spectrometry evidence OR DeRisi expression"

_CRITERIA = [
    Criterion(
        id="c_ms",
        text="trophozoite mass spectrometry evidence",
        search_name="GenesByMassSpec",
    ),
    Criterion(
        id="c_derisi",
        text="DeRisi timecourse expression",
        search_name="GenesByRNASeqEvidence",
    ),
]

_SUCCESS_DIGEST: dict[str, Any] = {
    "digest": {
        "disposition": "done",
        "prose": (
            "**Verified end-to-end.** The empty result is explained by the "
            "downstream combination; relaxing the peptide threshold would fill it."
        ),
        "reason": "Verified successfully",
        "success": True,
    },
}


def _requirement() -> Constraint:
    return Constraint(
        kind=ConstraintKind.COMBINATION,
        requested_value=_COMBINATION,
        label="how the evidence combines",
        source=ConstraintSource.USER_EXPLICIT,
    )


def _spec(operator: CombineOp) -> OperationalSpec:
    return OperationalSpec(
        goal="kinase drug targets",
        criteria=list(_CRITERIA),
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=operator,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="c_ms"),
                    StructureNode(kind="leaf", criterion_id="c_derisi"),
                ],
            )
        ),
    )


class TestTheStructureRule:
    def test_an_intersected_or_contradicts_success(self) -> None:
        contradiction = structure_contradiction(
            [_requirement()], _spec(CombineOp.INTERSECT)
        )

        assert contradiction is not None
        assert _COMBINATION in contradiction
        assert "UNION" in contradiction
        assert "INTERSECT" in contradiction

    def test_a_unioned_or_does_not_contradict(self) -> None:
        assert structure_contradiction([_requirement()], _spec(CombineOp.UNION)) is None

    def test_a_thread_with_no_spec_does_not_contradict(self) -> None:
        assert structure_contradiction([_requirement()], None) is None

    def test_a_thread_that_stated_no_combination_does_not_contradict(self) -> None:
        assert structure_contradiction([], _spec(CombineOp.INTERSECT)) is None


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _scripted() -> FunctionModel:
    def _part() -> ToolCallPart:
        return ToolCallPart(
            tool_name="final_result",
            args=_SUCCESS_DIGEST,
            tool_call_id="call_final",
        )

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[_part()])

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        part = _part()
        yield {
            0: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            ),
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


class _Collector:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


@pytest.fixture(autouse=True)
def collector(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    return captured


def _built_session() -> StrategySession:
    session = StrategySession(site_id="plasmodb")
    graph = StrategyGraph("graph-1", "Kinase drug targets", "plasmodb")
    graph.record_type = "transcript"
    graph.add_step(
        StrategyStep(id="s1", kind=StepKind.SEARCH, search_name="GenesByMassSpec"),
    )
    session.add_graph(graph)
    session.sync_state = WDKSyncState(
        wdk_step_ids={"s1": 440186113},
        step_counts={"s1": 12},
        wdk_strategy_id=330423363,
    )
    return session


def _deps(operator: CombineOp) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Kinases with mass spec evidence or DeRisi expression.",
    )
    state.domain.operational_spec = _spec(operator)
    state.domain.requirements = [_requirement()]
    state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1"],
        wdk_strategy_id=330423363,
        root_count=12,
    )
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=_built_session(),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(state=state, intent=None, runtime=context, retrieved_memories=[])


async def _verify(monkeypatch: pytest.MonkeyPatch, deps: LeadDeps) -> VerificationDelta:
    monkeypatch.setattr(sub_agent_tools, "get_mock_model", _scripted)
    with pinned_sub_agent(
        monkeypatch,
        "verification",
        toolsets=[verification.build_toolset()],
        instructions="Return the digest the script names.",
    ):
        result = await run_verification(
            deps=deps,
            parent_tool_call_id="lead_call_verify",
            reason="check the strategy",
        )
    assert isinstance(result, VerificationDelta)
    return result


async def test_success_over_a_violated_combination_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = _deps(CombineOp.INTERSECT)

    delta = await _verify(monkeypatch, deps)

    assert delta.digest.success is False
    assert delta.digest.failure_cause is FailureCause.STRUCTURE_VIOLATION
    assert _COMBINATION in delta.digest.reason
    assert "INTERSECT" in delta.digest.prose
    assert deps.state.turn_markers.verified is False


async def test_success_over_the_stated_combination_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = _deps(CombineOp.UNION)

    delta = await _verify(monkeypatch, deps)

    assert delta.digest.success is True
    assert delta.digest.failure_cause is None
