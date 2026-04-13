"""Regression tests: ConversationState must preserve phase timings.

These tests assert the contract for phase timing persistence (Issue 5, Part A):

* ``ConversationState`` carries a ``phase_timings`` mapping keyed by phase name.
* Each entry records ``phase_started_at``, ``phase_completed_at``,
  ``duration_ms`` and ``emitted_at`` so that after a page refresh the frontend
  can restore the elapsed-time label for every phase that has ever fired.
* ``with_phase_change`` threads these fields through the state transition.
* Serialization uses camelCase (``phaseTimings``, ``phaseStartedAt`` ...) via
  the shared :class:`CamelModel` base.

The tests currently FAIL because the field and method parameters do not yet
exist.  To keep the file type-clean we route "future-feature" access through
``model_dump(by_alias=True)`` — the resulting dict is ``dict[str, Any]`` so
missing keys surface as assertion failures at runtime, not compile-time type
errors.  New keyword parameters are passed via ``**_kwargs(...)``, which
builds a ``dict[str, Any]`` so Pyright does not narrow the value type
against the existing ``operation_id: str | None`` parameter.
"""

from typing import Any

from pathfinder.domain.strategy.conversation_state import ConversationState


def _kwargs(**items: Any) -> dict[str, Any]:
    """Build a kwargs dict for ``**`` expansion into ``with_phase_change``.

    Returns ``dict[str, Any]`` so that mixed value types (str, int, None)
    expand cleanly against the existing typed parameters of the method.
    """
    return dict(items)


def _timings(cs: ConversationState) -> dict[str, Any]:
    """Extract the phase_timings sub-dict from a camelCase serialization.

    Using the serialized dict avoids direct access to a class attribute that
    does not yet exist on the Pydantic model.
    """
    dumped = cs.model_dump(by_alias=True, mode="json")
    timings = dumped.get("phaseTimings")
    if not isinstance(timings, dict):
        return {}
    return timings


class TestConversationStatePhaseTimingsField:
    def test_has_phase_timings_field_defaulting_to_empty_dict(self) -> None:
        cs = ConversationState()
        assert hasattr(cs, "phase_timings"), (
            "ConversationState must expose a phase_timings field"
        )
        dumped = cs.model_dump(by_alias=True, mode="json")
        assert "phaseTimings" in dumped, (
            "model_dump must serialise phaseTimings (even when empty)"
        )
        assert dumped["phaseTimings"] == {}

    def test_extra_fields_still_ignored(self) -> None:
        cs = ConversationState.model_validate({"unknownField": "value"})
        assert _timings(cs) == {}

    def test_round_trips_through_json_with_timings(self) -> None:
        cs = ConversationState().with_phase_change(
            phase="discovery",
            status="started",
            **_kwargs(
                phase_started_at="2026-04-12T10:00:00Z",
                emitted_at="2026-04-12T10:00:00Z",
            ),
        ).with_phase_change(
            phase="discovery",
            status="completed",
            **_kwargs(
                phase_completed_at="2026-04-12T10:01:30Z",
                emitted_at="2026-04-12T10:01:30Z",
                duration_ms=90_000,
            ),
        )
        dumped = cs.model_dump(by_alias=True, mode="json")
        restored = ConversationState.model_validate(dumped)
        assert restored == cs


class TestWithPhaseChangeTimings:
    def test_started_records_phase_started_at(self) -> None:
        cs = ConversationState()
        updated = cs.with_phase_change(
            phase="discovery",
            status="started",
            **_kwargs(
                phase_started_at="2026-04-12T10:00:00Z",
                emitted_at="2026-04-12T10:00:00Z",
            ),
        )
        timing = _timings(updated).get("discovery", {})
        assert timing.get("phaseStartedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("emittedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("phaseCompletedAt") is None
        assert timing.get("durationMs") is None

    def test_completed_records_phase_completed_at_and_duration(self) -> None:
        started = ConversationState().with_phase_change(
            phase="discovery",
            status="started",
            **_kwargs(
                phase_started_at="2026-04-12T10:00:00Z",
                emitted_at="2026-04-12T10:00:00Z",
            ),
        )
        completed = started.with_phase_change(
            phase="discovery",
            status="completed",
            **_kwargs(
                phase_completed_at="2026-04-12T10:01:30Z",
                emitted_at="2026-04-12T10:01:30Z",
                duration_ms=90_000,
            ),
        )
        timing = _timings(completed).get("discovery", {})
        assert timing.get("phaseStartedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("phaseCompletedAt") == "2026-04-12T10:01:30Z"
        assert timing.get("durationMs") == 90_000

    def test_completed_preserves_started_at_from_previous_state(self) -> None:
        started = ConversationState().with_phase_change(
            phase="execution",
            status="started",
            **_kwargs(phase_started_at="2026-04-12T10:00:00Z"),
        )
        completed = started.with_phase_change(
            phase="execution",
            status="completed",
            **_kwargs(
                phase_completed_at="2026-04-12T10:05:00Z",
                duration_ms=300_000,
            ),
        )
        timing = _timings(completed).get("execution", {})
        assert timing.get("phaseStartedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("phaseCompletedAt") == "2026-04-12T10:05:00Z"
        assert timing.get("durationMs") == 300_000

    def test_multiple_phases_keep_independent_entries(self) -> None:
        cs = ConversationState().with_phase_change(
            phase="scoping",
            status="started",
            **_kwargs(phase_started_at="2026-04-12T10:00:00Z"),
        ).with_phase_change(
            phase="scoping",
            status="completed",
            **_kwargs(
                phase_completed_at="2026-04-12T10:00:45Z",
                duration_ms=45_000,
            ),
        ).with_phase_change(
            phase="discovery",
            status="started",
            **_kwargs(phase_started_at="2026-04-12T10:00:45Z"),
        )
        timings = _timings(cs)
        assert set(timings.keys()) == {"scoping", "discovery"}
        assert timings["scoping"].get("durationMs") == 45_000
        assert timings["discovery"].get("durationMs") is None
        assert (
            timings["discovery"].get("phaseStartedAt")
            == "2026-04-12T10:00:45Z"
        )

    def test_without_timing_kwargs_phase_timings_stay_empty(self) -> None:
        cs = ConversationState().with_phase_change(
            phase="scoping", status="started"
        )
        assert _timings(cs) == {}
        assert cs.current_phase == "scoping"
        assert cs.phase_status == "started"


class TestPhaseTimingsCamelCaseSerialization:
    def test_phase_timings_serialize_camel_case(self) -> None:
        cs = ConversationState().with_phase_change(
            phase="execution",
            status="started",
            **_kwargs(
                phase_started_at="2026-04-12T10:00:00Z",
                emitted_at="2026-04-12T10:00:00Z",
            ),
        )
        dumped = cs.model_dump(by_alias=True, mode="json")
        assert "phaseTimings" in dumped
        execution = dumped["phaseTimings"]["execution"]
        assert execution["phaseStartedAt"] == "2026-04-12T10:00:00Z"
        assert execution["emittedAt"] == "2026-04-12T10:00:00Z"
        assert execution["phaseCompletedAt"] is None
        assert execution["durationMs"] is None

    def test_completed_timing_serializes_duration_ms(self) -> None:
        cs = ConversationState().with_phase_change(
            phase="planning",
            status="started",
            **_kwargs(phase_started_at="2026-04-12T10:00:00Z"),
        ).with_phase_change(
            phase="planning",
            status="completed",
            **_kwargs(
                phase_completed_at="2026-04-12T10:01:30Z",
                duration_ms=90_000,
            ),
        )
        dumped = cs.model_dump(by_alias=True, mode="json")
        planning = dumped["phaseTimings"]["planning"]
        assert planning["phaseStartedAt"] == "2026-04-12T10:00:00Z"
        assert planning["phaseCompletedAt"] == "2026-04-12T10:01:30Z"
        assert planning["durationMs"] == 90_000
