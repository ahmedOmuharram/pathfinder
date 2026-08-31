"""A verification verdict never says more than the build it describes.

The ledger records what was pushed. A digest that claims success over a build
that pushed nothing is rewritten to the failure the ledger holds, so the reply,
the memory auto-write and the eval extractor all read the same verdict.
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
from pathfinder.ai.graph.state import PhaseDisposition, PipelineState
from pathfinder.ai.lead import sub_agent_stream, sub_agent_tools
from pathfinder.ai.lead.deltas import VerificationDelta
from pathfinder.ai.lead.ledger import build_contradiction
from pathfinder.ai.lead.ledger_sections import BuildSection
from pathfinder.ai.lead.sub_agent_dispatch import run_verification
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.toolsets import verification
from pathfinder.domain.strategy.build_outcome import BuildOutcome, StepPushFailure
from pathfinder.domain.strategy.graph_model import StepKind, StrategyStep
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.sync_state import WDKSyncState
from pathfinder.tests._support.sub_agents import pinned_sub_agent

_SUCCESS_DIGEST: dict[str, Any] = {
    "digest": {
        "disposition": "done",
        "prose": (
            "**Verified end-to-end.** The strategy framed, built, and verified "
            "cleanly - root size looks right and the leaves are non-empty."
        ),
        "reason": "Verified successfully",
        "success": True,
    },
}


class TestTheLedgerRule:
    def test_a_turn_that_pushed_nothing_contradicts_success(self) -> None:
        # The measured state: criteria 0, pushed 0, succeeded no, no strategy.
        contradiction = build_contradiction(BuildSection(), built_step_count=0)
        assert contradiction == (
            "this turn built nothing and no step of the strategy is in VEuPathDB"
        )

    def test_a_strategy_built_on_an_earlier_turn_does_not_contradict(self) -> None:
        assert build_contradiction(BuildSection(), built_step_count=3) is None

    def test_a_partial_build_contradicts_success(self) -> None:
        section = BuildSection(
            outcome=BuildOutcome(
                pushed_step_ids=["s1"],
                failed_steps=[
                    StepPushFailure(
                        step_id="s2", search_name="GenesByText", error="422"
                    )
                ],
            ),
            pushed_count=1,
            failed_count=1,
        )
        assert build_contradiction(section, built_step_count=1) == (
            "the build pushed 1 step, failed 1, skipped 0 and left 0 empty"
        )

    def test_a_clean_build_does_not_contradict(self) -> None:
        section = BuildSection(
            outcome=BuildOutcome(pushed_step_ids=["s1", "s2"], root_count=16),
            pushed_count=2,
        )
        assert build_contradiction(section, built_step_count=2) is None


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


def _deps(session: StrategySession) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="cryptodb",
        mode="strategy",
        user_prompt="Build me a strategy for Cryptosporidium kinases.",
    )
    context = Context(
        site_id="cryptodb",
        user_id=uuid4(),
        strategy_session=session,
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(state=state, intent=None, runtime=context, retrieved_memories=[])


def _built_session() -> StrategySession:
    session = StrategySession(site_id="cryptodb")
    graph = StrategyGraph("graph-1", "Kinases", "cryptodb")
    graph.record_type = "transcript"
    graph.add_step(
        StrategyStep(id="s1", kind=StepKind.SEARCH, search_name="GenesByText"),
    )
    session.add_graph(graph)
    session.sync_state = WDKSyncState(
        wdk_step_ids={"s1": 440186113},
        step_counts={"s1": 61},
        wdk_strategy_id=330558093,
    )
    return session


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


async def test_success_over_a_zero_push_build_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = _deps(StrategySession(site_id="cryptodb"))

    delta = await _verify(monkeypatch, deps)

    assert delta.digest.success is False
    assert delta.digest.reason == (
        "Verification reported success, but this turn built nothing and no "
        "step of the strategy is in VEuPathDB."
    )
    assert "built nothing" in delta.digest.prose
    assert delta.digest.caveats == [
        "The verification verdict was refused: this turn built nothing and no "
        "step of the strategy is in VEuPathDB",
    ]
    recorded = deps.state.domain.verification_digest
    assert recorded is not None
    assert recorded.success is False


async def test_success_over_a_real_build_stands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = _deps(_built_session())
    deps.state.domain.last_build_outcome = BuildOutcome(
        pushed_step_ids=["s1"],
        wdk_strategy_id=330558093,
        root_count=61,
    )

    delta = await _verify(monkeypatch, deps)

    assert delta.digest.success is True
    assert delta.digest.disposition is PhaseDisposition.DONE
    assert delta.digest.reason == "Verified successfully"
    assert delta.digest.caveats == []
