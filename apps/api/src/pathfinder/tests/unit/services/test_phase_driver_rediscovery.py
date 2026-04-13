"""Regression tests for ``_run_execution_state_phase`` classification logic.

When execution fails, the phase driver currently has only two exits:
    * plan.status == FAILED and should_replan() -> ``replan`` (exec->planning)
    * otherwise                                  -> ``finish_execution`` (->verification)

The fix must introduce a third exit for failures caused by the wrong
SEARCH being chosen (not a bad parameter).  Those failures re-running
planning with the same discovered searches are futile, so the driver
needs to:

    1. Inspect a *failure-type* signal populated during execution.
    2. Send the new ``retry_discovery_from_execution`` event so the
       state machine falls back to discovery.

These tests communicate the signal via ``deps.turn_metadata["failureKind"]``
— an already-typed ``JSONObject`` on :class:`AgentDeps` — so the fix
does not require schema changes to :class:`StrategyPlan`.  The fix
agent is free to compute the failure kind elsewhere (e.g. a dedicated
``PlanFailureKind`` enum on ``StrategyPlan``) as long as the
observable behaviour matches:

    * ``failureKind == "search_invalid"`` -> send ``retry_discovery_from_execution``
    * ``failureKind == "parameter_invalid"`` (or absent) -> send ``replan``
    * plan.status == COMPLETE -> send ``finish_execution``

These tests FAIL today because:
    * ``_run_execution_state_phase`` unconditionally chooses between
      ``replan`` and ``finish_execution``; it never emits
      ``retry_discovery_from_execution``.
    * There is no ``retry_discovery_from_execution`` transition in
      :class:`AgentPipeline` (see
      :mod:`pathfinder.tests.unit.pipeline.test_execution_to_discovery`).

TODO for the fix agent:
    * Add the missing FSM transition (see the pipeline-level regression
      test module referenced above).
    * Teach ``run_execution_phase`` (or a small helper) to populate
      ``deps.turn_metadata["failureKind"]`` when it detects the error
      came from a bad search vs. a bad parameter.
    * Update ``_run_execution_state_phase`` to branch on that signal
      before falling through to ``replan``.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.pipeline import AgentPipeline, create_pipeline
from pathfinder.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.phase_driver import _run_execution_state_phase
from pathfinder.services.chat.streaming.phase_runner import PhaseConfig

# Event names the fix is expected to introduce / keep.  Kept as constants so
# the fix can rename and the tests update in one place.
_REDISCOVER_EVENT = "retry_discovery_from_execution"
_REPLAN_EVENT = "replan"
_FINISH_EVENT = "finish_execution"


def _make_deps() -> AgentDeps:
    """AgentDeps with a live StrategySession and AgentToolState."""
    session = StrategySession(site_id="plasmodb")
    session.create_graph("Rediscovery Test Strategy")
    return AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _make_config(deps: AgentDeps) -> PhaseConfig:
    return PhaseConfig(
        phase="execution",
        prompt="",
        deps=deps,
        queue=asyncio.Queue(),
        message_id="execution-msg",
        counters=TurnCounters(),
        message_group_id="group-1",
        model_id="mock/deterministic",
        reasoning_effort="low",
    )


def _make_failed_plan() -> StrategyPlan:
    """Minimal plan with status=FAILED and one failed leaf step."""
    return StrategyPlan(
        title="Rediscovery test",
        description="Fail on purpose",
        rationale="Exercise failure classification",
        status=PlanStatus.FAILED,
        steps=[
            PlannedStep(
                id="step_a",
                search_name="GenesByTaxon",
                display_name="Genes by Taxon",
                step_type=StepType.LEAF,
                status=StepStatus.FAILED,
                failure_reason="simulated failure",
            ),
        ],
        connections=[],
    )


def _make_complete_plan() -> StrategyPlan:
    """Minimal plan whose single step completed successfully."""
    return StrategyPlan(
        title="Success test",
        description="Complete on purpose",
        rationale="Exercise success path",
        status=PlanStatus.COMPLETE,
        steps=[
            PlannedStep(
                id="step_a",
                search_name="GenesByTaxon",
                display_name="Genes by Taxon",
                step_type=StepType.LEAF,
                status=StepStatus.COMPLETE,
            ),
        ],
        connections=[],
    )


def _advance_to_execution(pipeline: AgentPipeline) -> None:
    pipeline.send("finish_scoping")
    pipeline.send("finish_discovery")
    pipeline.send("submit_draft")
    pipeline.send("approve")


def _wrap_send(sm: AgentPipeline) -> MagicMock:
    """Replace ``sm.send`` with a MagicMock that forwards to the real method.

    Returns the mock so callers can inspect ``call_args``.  The real method
    still runs, so the state machine advances normally — we just get a
    recording of which events were fired.
    """
    real_send = sm.send
    mock = MagicMock(side_effect=real_send)
    sm.send = mock
    return mock


class TestPhaseDriverRediscoveryClassification:
    """``_run_execution_state_phase`` must classify execution failures."""

    async def test_execution_failure_with_search_level_error_sends_rediscover(
        self,
    ) -> None:
        """Search-level failure => rediscover event, not replan.

        This is the core regression: today the driver only sends ``replan``
        when the plan is FAILED.  After the fix it must inspect a
        failure-classification signal (this test writes it into
        ``deps.turn_metadata['failureKind']``) and send
        ``retry_discovery_from_execution`` when the failure is SEARCH-level.
        """
        deps = _make_deps()
        deps.turn_metadata["failureKind"] = "search_invalid"
        deps.agent_state.active_plan = _make_failed_plan()

        sm = create_pipeline()
        _advance_to_execution(sm)
        assert sm.current_phase == "execution"

        send_mock = _wrap_send(sm)

        with patch(
            "pathfinder.services.chat.streaming.phase_driver.run_execution_phase",
            new=AsyncMock(return_value=None),
        ):
            await _run_execution_state_phase(sm, _make_config(deps))

        events_sent = [call.args[0] for call in send_mock.call_args_list]
        assert _REDISCOVER_EVENT in events_sent, (
            f"Expected driver to send {_REDISCOVER_EVENT!r} for a SEARCH-level "
            f"failure (turn_metadata['failureKind']='search_invalid'), but saw "
            f"events {events_sent}.  Update _run_execution_state_phase to "
            "branch on the failure classification before falling through to "
            "replan."
        )
        assert _REPLAN_EVENT not in events_sent, (
            "Driver must NOT send 'replan' when the failure is search-level — "
            "replanning with the same discovered searches is futile."
        )
        assert sm.current_phase == "discovery", (
            "After rediscover the pipeline must be in 'discovery'; ended up "
            f"in {sm.current_phase!r}."
        )

    async def test_execution_failure_with_parameter_error_sends_replan(
        self,
    ) -> None:
        """Parameter-level failure keeps the existing ``replan`` behaviour."""
        deps = _make_deps()
        deps.turn_metadata["failureKind"] = "parameter_invalid"
        deps.agent_state.active_plan = _make_failed_plan()

        sm = create_pipeline()
        _advance_to_execution(sm)

        send_mock = _wrap_send(sm)

        with patch(
            "pathfinder.services.chat.streaming.phase_driver.run_execution_phase",
            new=AsyncMock(return_value=None),
        ):
            await _run_execution_state_phase(sm, _make_config(deps))

        events_sent = [call.args[0] for call in send_mock.call_args_list]
        assert _REPLAN_EVENT in events_sent, (
            f"Expected driver to send {_REPLAN_EVENT!r} for a parameter-level "
            f"failure, but saw events {events_sent}."
        )
        assert _REDISCOVER_EVENT not in events_sent, (
            "Driver must NOT send rediscover when the failure is parameter-level; "
            "the existing discovered-search catalog is still valid."
        )
        assert sm.current_phase == "planning", (
            "After replan the pipeline must be in 'planning'; ended up in "
            f"{sm.current_phase!r}."
        )

    async def test_execution_success_sends_finish_execution(self) -> None:
        """Successful completion still goes to verification via ``finish_execution``."""
        deps = _make_deps()
        deps.agent_state.active_plan = _make_complete_plan()

        sm = create_pipeline()
        _advance_to_execution(sm)

        send_mock = _wrap_send(sm)

        with patch(
            "pathfinder.services.chat.streaming.phase_driver.run_execution_phase",
            new=AsyncMock(return_value=None),
        ):
            await _run_execution_state_phase(sm, _make_config(deps))

        events_sent = [call.args[0] for call in send_mock.call_args_list]
        assert events_sent == [_FINISH_EVENT], (
            f"Expected the driver to send exactly [{_FINISH_EVENT!r}] on a "
            f"COMPLETE plan, but saw {events_sent}."
        )
        assert sm.current_phase == "verification", (
            "After finish_execution the pipeline must be in 'verification'; "
            f"ended up in {sm.current_phase!r}."
        )

    async def test_search_failure_respects_discovery_retry_budget(self) -> None:
        """When discovery budget is exhausted the driver must NOT rediscover.

        Even for search-level failures, if the discovery retry budget is
        already spent the driver has to fall back to either ``replan`` or
        ``finish_execution`` (the fix agent chooses the semantics).  The
        load-bearing claim is: a search-level failure with an exhausted
        budget MUST NOT leave the pipeline in 'discovery'.
        """
        deps = _make_deps()
        deps.turn_metadata["failureKind"] = "search_invalid"
        deps.agent_state.active_plan = _make_failed_plan()

        sm = create_pipeline()
        _advance_to_execution(sm)
        # Exhaust the discovery retry budget — ``needs_rediscovery`` (to be
        # added by the fix) must return False.
        sm.retry_counts["discovery"] = sm.retry_budget + 1

        send_mock = _wrap_send(sm)

        with patch(
            "pathfinder.services.chat.streaming.phase_driver.run_execution_phase",
            new=AsyncMock(return_value=None),
        ):
            await _run_execution_state_phase(sm, _make_config(deps))

        events_sent = [call.args[0] for call in send_mock.call_args_list]
        # The driver may still *send* the rediscover event (and let the guard
        # block it), but the resulting state must NOT be 'discovery'.
        assert sm.current_phase != "discovery", (
            "Rediscover must be blocked when the discovery budget is "
            "exhausted — the guard on the new transition refuses the event.  "
            f"Events sent: {events_sent}.  Final phase: {sm.current_phase!r}."
        )


class TestPhaseDriverPlanAbsent:
    """Edge case: no active plan on deps — must not crash or reclassify."""

    async def test_execution_with_no_active_plan_sends_finish_execution(
        self,
    ) -> None:
        """If ``deps.agent_state.active_plan`` is None the driver must
        still send ``finish_execution`` — rediscover only applies when there
        IS a plan AND it has a search-level failure.
        """
        deps = _make_deps()
        deps.agent_state.active_plan = None

        sm = create_pipeline()
        _advance_to_execution(sm)

        send_mock = _wrap_send(sm)

        with patch(
            "pathfinder.services.chat.streaming.phase_driver.run_execution_phase",
            new=AsyncMock(return_value=None),
        ):
            await _run_execution_state_phase(sm, _make_config(deps))

        events_sent = [call.args[0] for call in send_mock.call_args_list]
        assert events_sent == [_FINISH_EVENT], (
            f"Expected driver to send exactly [{_FINISH_EVENT!r}] when "
            f"active_plan is None, but saw {events_sent}."
        )
