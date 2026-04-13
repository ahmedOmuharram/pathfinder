"""Regression tests: the projection handler records phase timings.

Covers Issue 5, Part B: the ``phase_change`` projection handler must pass the
``emittedAt`` / ``phaseStartedAt`` / ``phaseCompletedAt`` / ``durationMs`` fields
from :class:`PhaseChangeEventData` into
:meth:`ConversationState.with_phase_change`, so that
``stream_projections.conversation_state`` (and therefore the REST response
built by ``build_projection_response``) carries phase timings across page
refreshes.

These tests currently FAIL because ``_extract_phase_change`` drops the timing
fields and ``ConversationState`` has no ``phase_timings`` attribute.  Access
to the missing field is routed through ``model_dump(by_alias=True)`` so the
file stays type-clean; the missing data surfaces as runtime assertion
failures, not compile-time errors.
"""

from typing import Any

from pathfinder.domain.strategy.conversation_state import ConversationState
from pathfinder.platform.projection import _build_conversation_state_update
from pathfinder.platform.types import JSONObject, JSONValue


def _phase_change_event(**overrides: JSONValue) -> JSONObject:
    event: JSONObject = {
        "phase": "discovery",
        "status": "started",
        "emittedAt": "2026-04-12T10:00:00Z",
        "phaseStartedAt": "2026-04-12T10:00:00Z",
    }
    for key, value in overrides.items():
        event[key] = value
    return event


def _timings(cs: ConversationState) -> dict[str, Any]:
    dumped = cs.model_dump(by_alias=True, mode="json")
    timings = dumped.get("phaseTimings")
    if not isinstance(timings, dict):
        return {}
    return timings


class TestProjectionRecordsPhaseTimings:
    def test_started_event_creates_phase_timing_entry(self) -> None:
        result = _build_conversation_state_update(
            ConversationState(),
            "phase_change",
            _phase_change_event(),
        )
        assert result is not None
        timings = _timings(result)
        assert "discovery" in timings
        timing = timings["discovery"]
        assert timing.get("phaseStartedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("emittedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("phaseCompletedAt") is None
        assert timing.get("durationMs") is None

    def test_completed_event_records_duration_and_completed_at(self) -> None:
        started = _build_conversation_state_update(
            ConversationState(),
            "phase_change",
            _phase_change_event(),
        )
        assert started is not None
        completed = _build_conversation_state_update(
            started,
            "phase_change",
            _phase_change_event(
                status="completed",
                emittedAt="2026-04-12T10:01:30Z",
                phaseStartedAt="2026-04-12T10:00:00Z",
                phaseCompletedAt="2026-04-12T10:01:30Z",
                durationMs=90_000,
            ),
        )
        assert completed is not None
        timing = _timings(completed).get("discovery", {})
        assert timing.get("phaseStartedAt") == "2026-04-12T10:00:00Z"
        assert timing.get("phaseCompletedAt") == "2026-04-12T10:01:30Z"
        assert timing.get("durationMs") == 90_000
        assert timing.get("emittedAt") == "2026-04-12T10:01:30Z"

    def test_second_phase_does_not_overwrite_first_phase_timing(self) -> None:
        scoping_done = _build_conversation_state_update(
            ConversationState(),
            "phase_change",
            _phase_change_event(
                phase="scoping",
                status="completed",
                emittedAt="2026-04-12T10:00:45Z",
                phaseStartedAt="2026-04-12T10:00:00Z",
                phaseCompletedAt="2026-04-12T10:00:45Z",
                durationMs=45_000,
            ),
        )
        assert scoping_done is not None
        discovery_started = _build_conversation_state_update(
            scoping_done,
            "phase_change",
            _phase_change_event(
                phase="discovery",
                status="started",
                emittedAt="2026-04-12T10:00:45Z",
                phaseStartedAt="2026-04-12T10:00:45Z",
            ),
        )
        assert discovery_started is not None
        timings = _timings(discovery_started)
        assert set(timings.keys()) == {"scoping", "discovery"}
        assert timings["scoping"].get("durationMs") == 45_000
        assert (
            timings["scoping"].get("phaseCompletedAt")
            == "2026-04-12T10:00:45Z"
        )
        assert (
            timings["discovery"].get("phaseStartedAt")
            == "2026-04-12T10:00:45Z"
        )

    def test_phase_timings_survive_model_dump_for_projection_column(
        self,
    ) -> None:
        result = _build_conversation_state_update(
            ConversationState(),
            "phase_change",
            _phase_change_event(
                phase="execution",
                status="completed",
                emittedAt="2026-04-12T10:05:00Z",
                phaseStartedAt="2026-04-12T10:00:00Z",
                phaseCompletedAt="2026-04-12T10:05:00Z",
                durationMs=300_000,
            ),
        )
        assert result is not None
        dumped = result.model_dump(by_alias=True, mode="json")
        assert "phaseTimings" in dumped
        execution = dumped["phaseTimings"]["execution"]
        assert execution["phaseStartedAt"] == "2026-04-12T10:00:00Z"
        assert execution["phaseCompletedAt"] == "2026-04-12T10:05:00Z"
        assert execution["durationMs"] == 300_000
        assert execution["emittedAt"] == "2026-04-12T10:05:00Z"

    def test_event_without_timings_still_updates_phase_state(self) -> None:
        result = _build_conversation_state_update(
            ConversationState(),
            "phase_change",
            {"phase": "scoping", "status": "started"},
        )
        assert result is not None
        assert result.current_phase == "scoping"
        assert result.phase_status == "started"
        assert _timings(result) == {}
