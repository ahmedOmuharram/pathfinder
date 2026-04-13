"""Regression tests for Issue 2: Ghost steps during planning phase.

The planning phase has a dedicated toolset at
``pathfinder.ai.tools.toolsets.planning`` that deliberately EXCLUDES
step-creation tools (``create_leaf_step``, ``combine_steps``,
``transform_step``) plus other WDK-mutating tools. Plan tools
(``create_plan``, ``submit_plan``, ``update_plan``) operate on an
in-memory :class:`StrategyPlan` only — they MUST NOT call WDK.

``submit_plan`` emits a ``graph_plan`` SSE event that has the same
shape as ``graph_snapshot``. If the frontend (or a backwards-compat
shim) ever treats ``graph_plan`` like ``graph_snapshot`` and applies
it to the real strategy graph, planned steps appear as real WDK
steps (ghost steps). These tests guarantee the backend never
contributes to that bug path.
"""

from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import (
    PlannedConnectionInput,
    PlannedStepInput,
    StepPatch,
)
from pathfinder.ai.tools.standalone.plan import (
    create_plan,
    submit_plan,
    update_plan,
)
from pathfinder.ai.tools.toolsets.planning import build_toolset
from pathfinder.domain.strategy.plan import StepType
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.step_creation import StepCreationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    """Build AgentDeps with a real StrategySession and an event queue."""
    session = StrategySession(site_id=site_id)
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=queue,
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _leaf_step(
    step_id: str,
    search_name: str,
) -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name=search_name,
        display_name=f"Step: {search_name}",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )


def _combine_step(step_id: str) -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="__combine__",
        display_name="Combine",
        record_type="transcript",
        step_type=StepType.COMBINE,
        operator="INTERSECT",
    )


def _connection(from_step: str, to_step: str) -> PlannedConnectionInput:
    return PlannedConnectionInput(
        from_step=from_step,
        to_step=to_step,
        input_type="primary",
    )


def _drain_events(deps: AgentDeps) -> list[JSONObject]:
    """Drain all events emitted during a test."""
    events: list[JSONObject] = []
    queue = deps.event_queue
    if queue is None:
        return events
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


class _CallCounter:
    """Async-compatible spy that records calls and never calls WDK."""

    def __init__(self, return_value: object | None = None) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.return_value = return_value

    async def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self.return_value

    @property
    def call_count(self) -> int:
        return len(self.calls)


def _install_wdk_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, _CallCounter]:
    """Patch the WDK-mutating entry points and return the spies.

    Patches every module that imports ``push_step_to_wdk`` or
    ``create_step``, so that if *any* code path in the plan tools
    were to reach them, the test would detect it.
    """
    spies: dict[str, _CallCounter] = {}

    push_spy = _CallCounter(return_value=(None, None, None))
    # step_wdk_push.push_step_to_wdk is the SSOT entry point.
    monkeypatch.setattr(
        "pathfinder.services.strategies.step_wdk_push.push_step_to_wdk",
        push_spy,
    )
    # step_creation.push_step_to_wdk is an imported reference used inside
    # create_step's body — patch it too to catch the bug even if that
    # binding were ever invoked.
    monkeypatch.setattr(
        "pathfinder.services.strategies.step_creation.push_step_to_wdk",
        push_spy,
    )
    spies["push_step_to_wdk"] = push_spy

    create_step_spy = _CallCounter(
        return_value=StepCreationResult(step=None, step_id=None, error=None),
    )
    monkeypatch.setattr(
        "pathfinder.services.strategies.step_creation.create_step",
        create_step_spy,
    )
    spies["create_step"] = create_step_spy

    return spies


# ---------------------------------------------------------------------------
# Toolset membership
# ---------------------------------------------------------------------------


def test_planning_toolset_excludes_wdk_mutating_tools() -> None:
    """Planning toolset must NOT include any WDK-mutating or step-creation tool."""
    toolset = build_toolset()
    tool_names = set(toolset.tools.keys())

    forbidden = {
        "create_leaf_step",
        "combine_steps",
        "transform_step",
        "update_step",
        "delete_step",
        "add_step_filter",
        "add_step_analysis",
        "add_step_report",
        "undo_last_change",
    }
    intersection = tool_names & forbidden
    assert intersection == set(), (
        f"Planning toolset leaks WDK-mutating tools: {sorted(intersection)}. "
        "These tools belong to execution phase — exposing them during "
        "planning produces ghost WDK steps."
    )


def test_planning_toolset_includes_expected_tools() -> None:
    """Planning toolset must include exactly the 10 plan-only tools."""
    toolset = build_toolset()
    tool_names = set(toolset.tools.keys())

    expected = {
        "create_plan",
        "update_plan",
        "submit_plan",
        "get_plan",
        "present_decision",
        "finish_planning",
        "think",
        "get_strategy",
        "resolve_gene_ids_to_records",
        "set_conversation_title",
    }
    assert tool_names == expected, (
        f"Planning toolset membership drifted.\n"
        f"  missing: {sorted(expected - tool_names)}\n"
        f"  extra:   {sorted(tool_names - expected)}"
    )


# ---------------------------------------------------------------------------
# Tool-level behavior: plan tools must NOT push to WDK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_plan_does_not_push_to_wdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_plan for 2 leaves + 1 combine must not touch WDK or add graph steps."""
    spies = _install_wdk_spies(monkeypatch)
    deps = _make_deps()
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Intersect organism + location",
        description="Two leaves intersected",
        rationale="Test",
        steps=[
            _leaf_step("step_a", "GenesByTaxon"),
            _leaf_step("step_b", "GenesByLocation"),
            _combine_step("step_c"),
        ],
        connections=[
            _connection("step_a", "step_c"),
            _connection("step_b", "step_c"),
        ],
    )

    assert spies["push_step_to_wdk"].call_count == 0, (
        f"push_step_to_wdk was invoked during create_plan: "
        f"{spies['push_step_to_wdk'].calls}"
    )
    assert spies["create_step"].call_count == 0, (
        f"create_step was invoked during create_plan: "
        f"{spies['create_step'].calls}"
    )

    # The strategy_session graph must not gain any steps.
    graph = deps.strategy_session.graph
    if graph is not None:
        assert graph.steps == {}, (
            f"StrategyGraph gained {len(graph.steps)} steps during "
            f"planning — ghost steps leaked into the real graph."
        )
        assert graph.roots == set(), (
            f"StrategyGraph gained roots during planning: {graph.roots}"
        )


@pytest.mark.asyncio
async def test_submit_plan_does_not_push_to_wdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_plan + submit_plan must leave WDK untouched."""
    spies = _install_wdk_spies(monkeypatch)
    deps = _make_deps()
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Submit test",
        description="Submit test",
        rationale="Test",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
        connections=[],
    )

    await submit_plan(ctx)

    assert spies["push_step_to_wdk"].call_count == 0
    assert spies["create_step"].call_count == 0

    graph = deps.strategy_session.graph
    if graph is not None:
        assert graph.steps == {}
        assert graph.roots == set()


@pytest.mark.asyncio
async def test_update_plan_does_not_push_to_wdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_plan + update_plan with step patches must leave WDK untouched."""
    spies = _install_wdk_spies(monkeypatch)
    deps = _make_deps()
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Update test",
        description="Update test",
        rationale="Test",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
        connections=[],
    )

    patch = StepPatch(
        step_id="step_a",
        parameters={"organism": '["Plasmodium vivax"]'},
    )
    await update_plan(ctx, step_updates=[patch])

    # update_plan with add_steps must also not push.
    await update_plan(
        ctx,
        add_steps=[_leaf_step("step_b", "GenesByLocation")],
    )

    assert spies["push_step_to_wdk"].call_count == 0, (
        f"push_step_to_wdk was invoked during update_plan: "
        f"{spies['push_step_to_wdk'].calls}"
    )
    assert spies["create_step"].call_count == 0

    graph = deps.strategy_session.graph
    if graph is not None:
        assert graph.steps == {}
        assert graph.roots == set()


# ---------------------------------------------------------------------------
# Event-emission behavior: submit_plan emits graph_plan, not graph_snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_plan_emits_graph_plan_event_not_graph_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """submit_plan must emit ONLY graph_plan (+ plan_presented).

    The ``graph_plan`` payload is the proposed plan. No ``graph_snapshot``
    may be emitted during planning — a ``graph_snapshot`` would cause
    the frontend to call ``applyGraphSnapshot`` and mount planned
    steps as real WDK steps in the strategy graph.
    """
    _install_wdk_spies(monkeypatch)
    deps = _make_deps()
    ctx = _make_ctx(deps)

    await create_plan(
        ctx,
        title="Event test",
        description="Verify graph_plan (not graph_snapshot) is emitted",
        rationale="Test",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
        connections=[],
    )

    await submit_plan(ctx)

    events = _drain_events(deps)
    event_types = [cast("str", ev["type"]) for ev in events]

    # Must contain exactly one graph_plan event.
    graph_plan_count = event_types.count("graph_plan")
    assert graph_plan_count == 1, (
        f"Expected exactly 1 graph_plan event, got {graph_plan_count}. "
        f"All event types: {event_types}"
    )

    # Must contain plan_presented too.
    assert "plan_presented" in event_types, (
        f"Missing plan_presented event. Got: {event_types}"
    )

    # Must NOT emit graph_snapshot during planning.
    graph_snapshot_count = event_types.count("graph_snapshot")
    assert graph_snapshot_count == 0, (
        f"submit_plan emitted {graph_snapshot_count} graph_snapshot "
        f"event(s). Planning must only emit graph_plan. If graph_snapshot "
        f"is emitted here, the frontend will mount planned steps as real "
        f"WDK steps (ghost steps). All event types: {event_types}"
    )

    # Must NOT emit strategy_update or strategy_link (WDK-execution events).
    for forbidden_type in ("strategy_update", "strategy_link"):
        assert forbidden_type not in event_types, (
            f"submit_plan emitted {forbidden_type!r} — this is a "
            f"WDK-execution event and must not fire during planning. "
            f"All event types: {event_types}"
        )

    # Verify the graph_plan payload shape the frontend expects.
    graph_plan_event = next(ev for ev in events if ev["type"] == "graph_plan")
    data = cast("JSONObject", graph_plan_event["data"])
    assert "plan" in data, (
        f"graph_plan event missing 'plan' key. Data: {data}"
    )
    plan_payload = cast("JSONObject", data["plan"])
    assert "recordType" in plan_payload
    assert "root" in plan_payload
