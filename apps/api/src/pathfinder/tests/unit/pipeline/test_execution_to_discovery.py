"""Regression tests for the missing execution->discovery FSM transition.

When execution fails because the discovered searches are wrong (not just
parameters), the pipeline must be able to go back to discovery to find
different searches.  This is distinct from ``replan`` (execution->planning),
which re-uses the same discovered catalog.

These tests currently FAIL because:
    * No transition from ``execution`` to ``discovery`` is defined on
      :class:`pathfinder.ai.orchestration.pipeline.AgentPipeline`.
    * No ``needs_rediscovery`` guard exists.
    * No ``retry_discovery_from_execution`` event exists.

The fix is to add in ``pipeline.py`` beside the other cross-phase recovery
transitions (around line 124)::

    retry_discovery_from_execution = execution.to(
        discovery, cond="needs_rediscovery"
    )

    def needs_rediscovery(self) -> bool:
        return self.retry_counts.get("discovery", 0) < self.retry_budget

NOTE on type-checker friendliness: because ``needs_rediscovery`` and the
``retry_discovery_from_execution`` event do not exist on the class yet,
reflection-based access (``getattr``, ``hasattr``) is used for probing.
This is NOT the forbidden ``getattr``/``isinstance`` chain pattern (which
targets data coercion); it is the legitimate way to probe for an API
surface that a fix will introduce.
"""

from __future__ import annotations

from pathfinder.ai.orchestration.pipeline import AgentPipeline, create_pipeline

# Event name the fix is expected to introduce.  Kept as a constant so the fix
# can rename it and update the tests in one place, but also documented in the
# assertion messages.
_REDISCOVER_EVENT = "retry_discovery_from_execution"


def _advance_to_execution(pipeline: AgentPipeline) -> None:
    """Walk the FSM from the initial scoping state into execution.running."""
    pipeline.send("finish_scoping")
    pipeline.send("finish_discovery")
    pipeline.send("submit_draft")
    pipeline.send("approve")


class TestExecutionToDiscoveryTransition:
    """Verify that the execution state can fall back to discovery."""

    def test_rediscover_event_is_registered(self) -> None:
        """The fix must register a named event triggering the new transition.

        python-statemachine stores registered event ids on ``pipeline.events``.
        Checking this registry is the type-safe way to assert the transition
        has been defined without poking at state internals.
        """
        pipeline = create_pipeline()
        event_ids = {str(event) for event in pipeline.events}
        assert _REDISCOVER_EVENT in event_ids, (
            f"Expected event {_REDISCOVER_EVENT!r} to be registered on "
            f"AgentPipeline.  Current events: {sorted(event_ids)}.  Add "
            "`retry_discovery_from_execution = execution.to(discovery, "
            "cond='needs_rediscovery')` to pipeline.py."
        )

    def test_transition_lands_in_discovery_substate(self) -> None:
        """Firing the event from execution must land in discovery.searching.

        This is the behavioural equivalent of "the transition exists and
        points at discovery".  We avoid poking at State.transitions (which
        Pyright struggles to type through the python-statemachine DSL) and
        simply observe the post-send configuration.

        Discovery's initial substate is ``searching`` (see ``class discovery``
        in ``pipeline.py``).
        """
        pipeline = create_pipeline()
        _advance_to_execution(pipeline)
        assert pipeline.current_phase == "execution"

        # Ensure the guard can pass (retry budget not exhausted).
        pipeline.retry_counts["discovery"] = 0

        pipeline.send(_REDISCOVER_EVENT)

        assert pipeline.current_phase == "discovery", (
            f"Expected current_phase == 'discovery' after sending "
            f"{_REDISCOVER_EVENT!r}, got {pipeline.current_phase!r}.  "
            "This means either the transition is missing or the guard "
            "`needs_rediscovery` returned False despite the retry budget."
        )
        state_ids = {state.id for state in pipeline.configuration}
        assert "searching" in state_ids, (
            "Expected to land in discovery.searching (the initial substate), "
            f"but configuration was {sorted(state_ids)}."
        )

    def test_blocked_when_retry_budget_exhausted(self) -> None:
        """Guard must refuse the transition once the discovery budget is spent.

        To rule out the "event silently swallowed because it doesn't exist"
        case (``allow_event_without_transition`` is True), this test first
        proves the transition IS functional when the budget has room, then
        proves it stops working once the budget is exhausted.  Both halves
        share the same event name, so if the transition is missing the test
        fails on the first ``pipeline.current_phase`` assertion.
        """
        # Half 1: rediscover works when under budget -> lands in discovery.
        # Fresh pipeline so on_enter_discovery hasn't incremented the counter.
        warm_pipeline = create_pipeline()
        _advance_to_execution(warm_pipeline)
        warm_pipeline.retry_counts["discovery"] = 0
        warm_pipeline.send(_REDISCOVER_EVENT)
        assert warm_pipeline.current_phase == "discovery", (
            "Baseline: rediscover must succeed when "
            "retry_counts['discovery'] == 0.  If this fails, the transition "
            "`execution.to(discovery, cond='needs_rediscovery')` is missing."
        )

        # Half 2: same event is refused by the guard when over budget.
        blocked_pipeline = create_pipeline()
        _advance_to_execution(blocked_pipeline)
        blocked_pipeline.retry_counts["discovery"] = (
            blocked_pipeline.retry_budget + 1
        )
        blocked_pipeline.send(_REDISCOVER_EVENT)
        assert blocked_pipeline.current_phase == "execution", (
            "Rediscover must be blocked once retry_counts['discovery'] exceeds "
            "retry_budget; expected to stay in 'execution' but ended up in "
            f"{blocked_pipeline.current_phase!r}."
        )

    def test_needs_rediscovery_guard_method_exists(self) -> None:
        """The class must expose a ``needs_rediscovery`` guard matching the budget.

        Mirrors the existing pattern for ``should_replan``, ``needs_more_scoping``,
        and ``needs_more_discovery``.
        """
        pipeline = create_pipeline()

        # Below budget -> True.
        pipeline.retry_counts["discovery"] = 0
        assert pipeline.needs_rediscovery() is True, (
            "needs_rediscovery() must return True when "
            "retry_counts['discovery'] < retry_budget."
        )

        # At budget (>=) -> False.
        pipeline.retry_counts["discovery"] = pipeline.retry_budget
        assert pipeline.needs_rediscovery() is False, (
            "needs_rediscovery() must return False once "
            "retry_counts['discovery'] >= retry_budget."
        )

    def test_rediscover_increments_discovery_retry_count(self) -> None:
        """Entering discovery via the fallback should bump the tracker counter.

        PipelineTracker.on_enter_discovery increments
        ``retry_counts['discovery']``.  After one successful rediscover, the
        count must go up by 1 relative to the value just before ``send``.
        """
        pipeline = create_pipeline()
        _advance_to_execution(pipeline)
        pipeline.retry_counts["discovery"] = 0

        discovery_before = pipeline.retry_counts["discovery"]
        pipeline.send(_REDISCOVER_EVENT)

        assert pipeline.current_phase == "discovery"
        assert pipeline.retry_counts["discovery"] == discovery_before + 1, (
            "Entering discovery via rediscover must increment "
            f"retry_counts['discovery'] by 1; went from {discovery_before} "
            f"to {pipeline.retry_counts['discovery']}."
        )
