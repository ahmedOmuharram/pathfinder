"""Conversation FSM state — persisted in stream_projections.conversation_state.

Pure domain model. No I/O, no side effects, no imports from other layers.
Frozen: transitions return new instances via ``with_phase_change`` / ``with_plan_event``.
"""

from typing import TypedDict, Unpack

from pydantic import ConfigDict, Field

from pathfinder.platform.pydantic_base import CamelModel


class PhaseTimingSnapshot(CamelModel):
    """Timing snapshot for a single pipeline phase.

    Captured on every ``phase_change`` event that carries timing metadata
    so that the frontend can restore elapsed-time labels after a reload.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    phase: str
    status: str
    emitted_at: str | None = None
    phase_started_at: str | None = None
    phase_completed_at: str | None = None
    duration_ms: int | None = None

    def has_any_timing(self) -> bool:
        """Return True when any of the timestamp or duration fields is set."""
        return any(
            value is not None
            for value in (
                self.emitted_at,
                self.phase_started_at,
                self.phase_completed_at,
                self.duration_ms,
            )
        )

    def merged_with(self, existing: "PhaseTimingSnapshot | None") -> "PhaseTimingSnapshot":
        """Return a snapshot that falls back to ``existing`` for missing fields.

        Used when a ``completed`` event omits fields that were already captured
        on the ``started`` event — e.g. ``phase_started_at`` must survive.
        """
        if existing is None:
            return self
        return PhaseTimingSnapshot(
            phase=self.phase,
            status=self.status,
            emitted_at=self.emitted_at
            if self.emitted_at is not None
            else existing.emitted_at,
            phase_started_at=self.phase_started_at
            if self.phase_started_at is not None
            else existing.phase_started_at,
            phase_completed_at=self.phase_completed_at
            if self.phase_completed_at is not None
            else existing.phase_completed_at,
            duration_ms=self.duration_ms
            if self.duration_ms is not None
            else existing.duration_ms,
        )


class PhaseChangeKwargs(TypedDict, total=False):
    """Optional keyword arguments for :meth:`ConversationState.with_phase_change`.

    Grouping optional phase transition arguments in a ``TypedDict`` keeps
    :meth:`ConversationState.with_phase_change` within the project-wide
    max-args limit while preserving a keyword-driven API at call sites.
    """

    operation_id: str | None
    emitted_at: str | None
    phase_started_at: str | None
    phase_completed_at: str | None
    duration_ms: int | None


class PhaseChangeInput(CamelModel):
    """Validated arguments for :meth:`ConversationState.with_phase_change`.

    Pydantic enforces the known field set and type coerces inputs before the
    transition logic runs, so the domain method never deals with raw ``Any``.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    phase: str
    status: str
    operation_id: str | None = None
    emitted_at: str | None = None
    phase_started_at: str | None = None
    phase_completed_at: str | None = None
    duration_ms: int | None = None

    def to_timing_snapshot(self) -> PhaseTimingSnapshot | None:
        """Build a ``PhaseTimingSnapshot`` if any timing field is populated."""
        snapshot = PhaseTimingSnapshot(
            phase=self.phase,
            status=self.status,
            emitted_at=self.emitted_at,
            phase_started_at=self.phase_started_at,
            phase_completed_at=self.phase_completed_at,
            duration_ms=self.duration_ms,
        )
        return snapshot if snapshot.has_any_timing() else None


class ConversationState(CamelModel):
    """Minimal FSM snapshot for cross-turn resumability.

    Written by the projection handler on every phase_change,
    plan_presented, plan_approved, model_selected, and message_end event.
    Read by ``build_agent_deps`` to restore the exact pipeline state.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    current_phase: str | None = None
    phase_status: str | None = None
    intent: str | None = None
    phases_completed: list[str] = Field(default_factory=list)
    plan_id: str | None = None
    plan_status: str | None = None
    last_operation_id: str | None = None
    phase_timings: dict[str, PhaseTimingSnapshot] = Field(default_factory=dict)
    pipeline: dict[str, dict[str, str]] | None = None

    def with_phase_change(
        self,
        phase: str,
        status: str,
        **kwargs: Unpack[PhaseChangeKwargs],
    ) -> "ConversationState":
        """Return a new state reflecting a phase transition.

        The accepted keyword arguments are declared on :class:`PhaseChangeKwargs`
        (``operation_id``, ``emitted_at``, ``phase_started_at``,
        ``phase_completed_at``, ``duration_ms``) and validated through
        :class:`PhaseChangeInput` so that Pydantic enforces the known field
        set and handles type coercion.

        When any timing field is supplied, record/merge a
        ``PhaseTimingSnapshot`` for ``phase``. Existing timing values are
        preserved when the new event omits them — e.g. a ``completed`` event
        that only carries ``duration_ms`` keeps the prior
        ``phase_started_at``.
        """
        update = PhaseChangeInput.model_validate(
            {"phase": phase, "status": status, **kwargs}
        )

        completed = list(self.phases_completed)
        if status == "completed" and phase not in completed:
            completed.append(phase)

        new_timings = dict(self.phase_timings)
        snapshot = update.to_timing_snapshot()
        if snapshot is not None:
            new_timings[phase] = snapshot.merged_with(new_timings.get(phase))

        return self.model_copy(
            update={
                "current_phase": phase,
                "phase_status": status,
                "phases_completed": completed,
                "phase_timings": new_timings,
                **(
                    {"last_operation_id": update.operation_id}
                    if update.operation_id
                    else {}
                ),
            },
        )

    def with_plan_event(
        self,
        event_type: str,
        *,
        plan_id: str | None = None,
    ) -> "ConversationState":
        """Return a new state reflecting a plan lifecycle event."""
        status_map = {
            "plan_presented": "presented",
            "plan_approved": "approved",
            "plan_updated": self.plan_status,
        }
        new_status = status_map.get(event_type, self.plan_status)
        return self.model_copy(
            update={
                **({"plan_id": plan_id} if plan_id else {}),
                "plan_status": new_status,
            },
        )

    def with_pipeline(
        self, pipeline: dict[str, dict[str, str]]
    ) -> "ConversationState":
        """Return a new state with the pipeline model configuration persisted."""
        return self.model_copy(update={"pipeline": pipeline})
