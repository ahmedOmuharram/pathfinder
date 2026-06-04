from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast
from uuid import uuid4

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.tools import RunContext

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.scratchpad.toolset import _loop_hidden_read_tools
from pathfinder.ai.tools.toolsets.execution import (
    _get_strategy_repeated_without_mutation,
)
from pathfinder.ai.tools.toolsets.planning import (
    _loop_hidden_reads,
    _plan_state_gated,
)
from pathfinder.domain.strategy.plan import StrategyPlan


def _tc(name: str) -> ToolCallPart:
    return ToolCallPart(tool_name=name, args={}, tool_call_id=uuid4().hex[:8])


def _resp(*names: str) -> ModelResponse:
    return ModelResponse(parts=[_tc(n) for n in names])


@dataclass
class _FakeDeps:
    agent_state: AgentToolState


@dataclass
class _FakeCtx:
    messages: list[ModelMessage] = field(default_factory=list)
    deps: _FakeDeps | None = None


def _ctx(names: list[str]) -> RunContext[AgentDeps]:
    messages: list[ModelMessage] = [_resp(n) for n in names]
    return cast("RunContext[AgentDeps]", _FakeCtx(messages=messages))


def _ctx_with_plan(active_plan: StrategyPlan | None) -> RunContext[AgentDeps]:
    deps = _FakeDeps(agent_state=AgentToolState(active_plan=active_plan))
    return cast("RunContext[AgentDeps]", _FakeCtx(messages=[], deps=deps))


def _make_plan() -> StrategyPlan:
    return StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[],
        connections=[],
    )


class TestScratchpadLoopFilter:
    def test_empty_history(self) -> None:
        assert _loop_hidden_read_tools(_ctx([])) == frozenset()

    def test_single_search_not_hidden(self) -> None:
        assert _loop_hidden_read_tools(_ctx(["search_notes"])) == frozenset()

    def test_two_consecutive_searches_hides(self) -> None:
        assert "search_notes" in _loop_hidden_read_tools(
            _ctx(["search_notes", "search_notes"]),
        )

    def test_mutation_then_two_searches_still_hides(self) -> None:
        assert "search_notes" in _loop_hidden_read_tools(
            _ctx(["note", "search_notes", "search_notes"]),
        )

    def test_mutation_breaks_streak(self) -> None:
        assert (
            _loop_hidden_read_tools(
                _ctx(["search_notes", "note", "search_notes"]),
            )
            == frozenset()
        )

    def test_non_read_non_mutation_breaks_streak(self) -> None:
        assert (
            _loop_hidden_read_tools(
                _ctx(["search_notes", "search_notes", "think", "search_notes"]),
            )
            == frozenset()
        )

    def test_distinct_read_tools_counted_separately(self) -> None:
        assert (
            _loop_hidden_read_tools(
                _ctx(["search_notes", "list_notes"]),
            )
            == frozenset()
        )

    def test_each_read_tool_hidden_on_its_own_streak(self) -> None:
        assert "list_notes" in _loop_hidden_read_tools(
            _ctx(["list_notes", "list_notes"]),
        )
        assert "read_note" in _loop_hidden_read_tools(
            _ctx(["read_note", "read_note"]),
        )


class TestExecutionGetStrategyFilter:
    def test_empty(self) -> None:
        assert _get_strategy_repeated_without_mutation(_ctx([])) is False

    def test_one_get_strategy(self) -> None:
        assert (
            _get_strategy_repeated_without_mutation(
                _ctx(["get_strategy"]),
            )
            is False
        )

    def test_two_consecutive_fires(self) -> None:
        assert (
            _get_strategy_repeated_without_mutation(
                _ctx(["get_strategy", "get_strategy"]),
            )
            is True
        )

    def test_prior_mutation_then_two_gets_still_fires(self) -> None:
        assert (
            _get_strategy_repeated_without_mutation(
                _ctx(["create_leaf_step", "get_strategy", "get_strategy"]),
            )
            is True
        )

    def test_mutation_breaks_streak(self) -> None:
        assert (
            _get_strategy_repeated_without_mutation(
                _ctx(["get_strategy", "create_leaf_step", "get_strategy"]),
            )
            is False
        )


class TestPlanningLoopFilter:
    def test_empty(self) -> None:
        assert _loop_hidden_reads(_ctx([])) == frozenset()

    def test_two_get_plans_hides(self) -> None:
        assert "get_plan" in _loop_hidden_reads(
            _ctx(["get_plan", "get_plan"]),
        )

    def test_two_get_strategies_hides(self) -> None:
        assert "get_strategy" in _loop_hidden_reads(
            _ctx(["get_strategy", "get_strategy"]),
        )

    def test_prior_create_plan_then_two_reads_still_hides(self) -> None:
        assert "get_plan" in _loop_hidden_reads(
            _ctx(["create_plan", "get_plan", "get_plan"]),
        )

    def test_create_plan_breaks_streak(self) -> None:
        assert (
            _loop_hidden_reads(
                _ctx(["get_plan", "create_plan", "get_plan"]),
            )
            == frozenset()
        )

    def test_distinct_reads_not_combined(self) -> None:
        assert (
            _loop_hidden_reads(
                _ctx(["get_plan", "get_strategy"]),
            )
            == frozenset()
        )


class TestPlanStateGated:
    def test_no_active_plan_hides_update_plan(self) -> None:
        ctx = _ctx_with_plan(None)
        assert _plan_state_gated(ctx) == frozenset({"update_plan"})

    def test_active_plan_hides_create_plan(self) -> None:
        ctx = _ctx_with_plan(_make_plan())
        assert _plan_state_gated(ctx) == frozenset({"create_plan"})
