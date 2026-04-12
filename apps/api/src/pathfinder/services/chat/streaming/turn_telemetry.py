"""Telemetry models for streamed chat turns."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pathfinder.ai.orchestration.classifier import Intent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class TurnLatencySummary(CamelModel):
    """Typed latency payload for a streamed turn (SSE, logs, metrics)."""

    time_to_first_assistant_delta_ms: int | None = None
    time_to_first_assistant_message_ms: int | None = None
    time_to_first_tool_call_ms: int | None = None
    approval_wait_ms: int | None = None
    resume_after_approval_ms: int | None = None
    execution_duration_ms: int | None = None


class TurnFailureContext(CamelModel):
    """Structured failure context emitted when a turn errors out."""

    error_type: str
    phase: str | None = None
    state_machine_phase: str | None = None
    intent: str
    run_kind: str
    recoverable: bool = False
    contract_violation: bool = False
    recovery_count: int = 0


@dataclass(frozen=True)
class _PhaseStartedAt:
    wallclock: datetime
    monotonic: float


@dataclass(frozen=True)
class PhaseTimingSnapshot:
    """Structured phase timing data shared across SSE, logs, and metrics."""

    phase: str
    status: str
    attempt: int
    emitted_at: str
    phase_started_at: str | None
    phase_completed_at: str | None
    duration_ms: int | None

    def as_summary(self) -> JSONObject:
        return {
            "phase": self.phase,
            "status": self.status,
            "attempt": self.attempt,
            "emittedAt": self.emitted_at,
            "phaseStartedAt": self.phase_started_at,
            "phaseCompletedAt": self.phase_completed_at,
            "durationMs": self.duration_ms,
        }


@dataclass
class PhaseTimingTracker:
    """Track wall-clock and elapsed timing for each pipeline phase."""

    _phase_starts: dict[str, _PhaseStartedAt] = field(default_factory=dict)
    _phase_attempts: dict[str, int] = field(default_factory=dict)
    _terminal_history: list[PhaseTimingSnapshot] = field(default_factory=list)

    def start(self, phase: str) -> PhaseTimingSnapshot:
        now = datetime.now(UTC)
        attempt = self._phase_attempts.get(phase, 0) + 1
        self._phase_attempts[phase] = attempt
        self._phase_starts[phase] = _PhaseStartedAt(
            wallclock=now,
            monotonic=time.monotonic(),
        )
        iso_now = now.isoformat()
        return PhaseTimingSnapshot(
            phase=phase,
            status="started",
            attempt=attempt,
            emitted_at=iso_now,
            phase_started_at=iso_now,
            phase_completed_at=None,
            duration_ms=0,
        )

    def snapshot(self, phase: str, status: str) -> PhaseTimingSnapshot:
        now = datetime.now(UTC)
        started = self._phase_starts.get(phase)
        attempt = self._phase_attempts.get(phase, 0)
        phase_started_at = (
            started.wallclock.isoformat() if started is not None else None
        )
        duration_ms = (
            round((time.monotonic() - started.monotonic) * 1000)
            if started is not None
            else None
        )
        snapshot = PhaseTimingSnapshot(
            phase=phase,
            status=status,
            attempt=attempt,
            emitted_at=now.isoformat(),
            phase_started_at=phase_started_at,
            phase_completed_at=None if status == "started" else now.isoformat(),
            duration_ms=0 if status == "started" and started is not None else duration_ms,
        )
        if status != "started":
            self._terminal_history.append(snapshot)
        return snapshot

    def terminal_history(self) -> list[PhaseTimingSnapshot]:
        return list(self._terminal_history)

    def latest_terminal(self, phase: str) -> PhaseTimingSnapshot | None:
        """Return the most recent terminal snapshot for ``phase`` if present."""
        for snapshot in reversed(self._terminal_history):
            if snapshot.phase == phase:
                return snapshot
        return None


@dataclass(frozen=True)
class PhaseEventContext:
    """Stable observability context for one pipeline phase attempt."""

    intent: Intent
    model_id: str
    run_kind: str


@dataclass(frozen=True)
class PhaseSpanContext:
    """Stable span metadata for one pipeline phase observation."""

    phase: str
    event: PhaseEventContext
    message_group_id: str | None


@dataclass(frozen=True)
class RecoveryEvent:
    """A structured recovery that happened during a turn."""

    phase: str
    kind: str
    summary: str
    metadata: JSONObject = field(default_factory=dict)
    recorded_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_payload(self) -> JSONObject:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "summary": self.summary,
            "metadata": self.metadata,
            "recordedAt": self.recorded_at,
        }


def _relative_ms(start: float, end: float | None) -> int | None:
    if end is None:
        return None
    return round((end - start) * 1000)


@dataclass
class TurnRuntimeTelemetry:
    """Mutable turn-scoped latency and recovery markers."""

    first_assistant_delta_at_monotonic: float | None = None
    first_assistant_message_at_monotonic: float | None = None
    first_tool_call_at_monotonic: float | None = None
    approval_wait_ms: int | None = None
    resume_after_approval_ms: int | None = None
    recoveries: list[RecoveryEvent] = field(default_factory=list)

    def mark_first_assistant_delta(self, value: float | None) -> None:
        if value is not None and self.first_assistant_delta_at_monotonic is None:
            self.first_assistant_delta_at_monotonic = value

    def mark_first_assistant_message(self, value: float | None) -> None:
        if value is not None and self.first_assistant_message_at_monotonic is None:
            self.first_assistant_message_at_monotonic = value

    def mark_first_tool_call(self, value: float | None) -> None:
        if value is not None and self.first_tool_call_at_monotonic is None:
            self.first_tool_call_at_monotonic = value

    def record_recovery(
        self,
        *,
        phase: str,
        kind: str,
        summary: str,
        metadata: JSONObject | None = None,
    ) -> None:
        self.recoveries.append(
            RecoveryEvent(
                phase=phase,
                kind=kind,
                summary=summary,
                metadata=metadata or {},
            )
        )

    def recoveries_for_phase(self, phase: str) -> list[JSONObject]:
        return [
            recovery.as_payload()
            for recovery in self.recoveries
            if recovery.phase == phase
        ]

    def latency_summary(
        self,
        *,
        turn_started_monotonic: float,
        phase_timings: PhaseTimingTracker,
    ) -> TurnLatencySummary:
        execution_snapshot = phase_timings.latest_terminal("execution")
        return TurnLatencySummary(
            time_to_first_assistant_delta_ms=_relative_ms(
                turn_started_monotonic,
                self.first_assistant_delta_at_monotonic,
            ),
            time_to_first_assistant_message_ms=_relative_ms(
                turn_started_monotonic,
                self.first_assistant_message_at_monotonic,
            ),
            time_to_first_tool_call_ms=_relative_ms(
                turn_started_monotonic,
                self.first_tool_call_at_monotonic,
            ),
            approval_wait_ms=self.approval_wait_ms,
            resume_after_approval_ms=self.resume_after_approval_ms,
            execution_duration_ms=(
                execution_snapshot.duration_ms if execution_snapshot is not None else None
            ),
        )


@dataclass(frozen=True)
class TurnTelemetryContext:
    """Observability context for one streamed turn."""

    deps: AgentDeps
    intent: Intent
    model_id: str
    run_kind: str
    phase_timings: PhaseTimingTracker
    turn_started_at: datetime
    turn_started_monotonic: float
    runtime: TurnRuntimeTelemetry
