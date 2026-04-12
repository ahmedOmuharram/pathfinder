"""StateChart for the agent pipeline.

Each user turn creates a fresh ``AgentPipeline`` that structures phase
transitions (scoping -> discovery -> planning -> execution -> verification -> completed).
Cross-turn state lives in ``AgentDeps``, not here.
"""

from __future__ import annotations

from typing import Any

from statemachine import HistoryState, State, StateChart

from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

# Phase names as they appear in state IDs (lowercase, matching class names).
_PHASE_IDS = ("scoping", "discovery", "planning", "execution", "verification")


class AgentPipeline(StateChart[None]):
    """Hierarchical state machine governing a single pipeline turn.

    Compound states model intra-phase progression.  ``done.state.*``
    events fire automatically when a compound state's final substate
    is reached, driving the phase-to-phase flow.

    Inner classes use lowercase names to produce lowercase state IDs
    (python-statemachine convention).  Ruff N801 is suppressed via
    per-file-ignores in pyproject.toml.
    """

    # ------------------------------------------------------------------
    # Class-level config
    # ------------------------------------------------------------------
    allow_event_without_transition: bool = True
    catch_errors_as_events: bool = False

    # ------------------------------------------------------------------
    # Phase 0 — Scoping
    # ------------------------------------------------------------------
    class scoping(State.Compound):
        framing = State(initial=True)
        researching = State()
        scoping_done = State(final=True)
        h = HistoryState(type="deep")

        research = framing.to(researching)
        finish_scoping = researching.to(scoping_done) | framing.to(scoping_done)

    # ------------------------------------------------------------------
    # Phase 1 — Discovery
    # ------------------------------------------------------------------
    class discovery(State.Compound):
        searching = State(initial=True)
        analyzing = State()
        discovery_done = State(final=True)
        h = HistoryState(type="deep")

        analyze = searching.to(analyzing)
        finish_discovery = analyzing.to(discovery_done) | searching.to(discovery_done)

    # ------------------------------------------------------------------
    # Phase 2 — Planning
    # ------------------------------------------------------------------
    class planning(State.Compound):
        drafting = State(initial=True)
        awaiting_approval = State()
        revising = State()
        plan_approved = State(final=True)
        h = HistoryState(type="deep")

        submit_draft = drafting.to(awaiting_approval)
        approve = awaiting_approval.to(plan_approved)
        request_revision = awaiting_approval.to(revising)
        resubmit = revising.to(awaiting_approval)

    # ------------------------------------------------------------------
    # Phase 3 — Execution
    # ------------------------------------------------------------------
    class execution(State.Compound):
        running = State(initial=True)
        retrying = State()
        execution_done = State(final=True)
        h = HistoryState(type="deep")

        retry = running.to(retrying)
        resume = retrying.to(running)
        finish_execution = running.to(execution_done) | retrying.to(execution_done)

    # ------------------------------------------------------------------
    # Phase 4 — Verification
    # ------------------------------------------------------------------
    class verification(State.Compound):
        checking = State(initial=True)
        presenting = State()
        verification_done = State(final=True)
        h = HistoryState(type="deep")

        present = checking.to(presenting)
        finish_verification = (
            presenting.to(verification_done) | checking.to(verification_done)
        )

    # ------------------------------------------------------------------
    # Terminal states
    # ------------------------------------------------------------------
    completed = State(final=True)
    failed = State(final=True)

    # ------------------------------------------------------------------
    # Phase-to-phase transitions (auto-fired by done.state.*)
    # ------------------------------------------------------------------
    done_state_scoping = scoping.to(discovery)
    done_state_discovery = discovery.to(planning)
    done_state_planning = planning.to(execution)
    done_state_execution = execution.to(verification)
    done_state_verification = verification.to(completed)

    # ------------------------------------------------------------------
    # Cross-phase recovery
    # ------------------------------------------------------------------
    replan = execution.to(planning, cond="should_replan")
    retry_scoping = discovery.to(scoping, cond="needs_more_scoping")
    retry_discovery = planning.to(discovery, cond="needs_more_discovery")

    # Abort — transitions from each phase to failed.
    abort_scoping = scoping.to(failed)
    abort_discovery = discovery.to(failed)
    abort_planning = planning.to(failed)
    abort_execution = execution.to(failed)
    abort_verification = verification.to(failed)

    # ------------------------------------------------------------------
    # Instance state
    # ------------------------------------------------------------------
    def __init__(self, **kwargs: Any) -> None:
        self.retry_counts: dict[str, int] = {
            "scoping": 0,
            "discovery": 0,
            "planning": 0,
            "execution": 0,
        }
        self.retry_budget: int = 3
        self._transition_count: int = 0
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def current_phase(self) -> str:
        """Return the top-level phase name as a lowercase string."""
        state_ids = {s.id for s in self.configuration}
        for phase_id in _PHASE_IDS:
            if phase_id in state_ids:
                return phase_id
        if "completed" in state_ids:
            return "completed"
        if "failed" in state_ids:
            return "failed"
        return "unknown"

    @property
    def is_done(self) -> bool:
        """True when a terminal state has been reached."""
        return self.current_phase in ("completed", "failed")

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def should_replan(self) -> bool:
        count = self.retry_counts.get("execution", 0)
        return count < self.retry_budget

    def needs_more_discovery(self) -> bool:
        count = self.retry_counts.get("discovery", 0)
        return count < self.retry_budget

    def needs_more_scoping(self) -> bool:
        count = self.retry_counts.get("scoping", 0)
        return count < self.retry_budget

    def has_retries_left(self, phase: str) -> bool:
        return self.retry_counts.get(phase, 0) < self.retry_budget


class PipelineTracker:
    """Listener that tracks retry counts and transition totals.

    Passed to ``AgentPipeline(listeners=[PipelineTracker()])`` so that
    callback names stay lowercase (matching state IDs) without violating
    ruff N802 on the StateChart subclass.
    """

    def __init__(self, pipeline: AgentPipeline) -> None:
        self.pipeline = pipeline

    def on_enter_scoping(self) -> None:
        p = self.pipeline
        p.retry_counts["scoping"] = p.retry_counts.get("scoping", 0) + 1
        p._transition_count += 1
        logger.info("Pipeline entering scoping (attempt %d)", p.retry_counts["scoping"])

    def on_enter_discovery(self) -> None:
        p = self.pipeline
        p.retry_counts["discovery"] = p.retry_counts.get("discovery", 0) + 1
        p._transition_count += 1
        logger.info("Pipeline entering discovery (attempt %d)", p.retry_counts["discovery"])

    def on_enter_planning(self) -> None:
        p = self.pipeline
        p.retry_counts["planning"] = p.retry_counts.get("planning", 0) + 1
        p._transition_count += 1
        logger.info("Pipeline entering planning (attempt %d)", p.retry_counts["planning"])

    def on_enter_execution(self) -> None:
        p = self.pipeline
        p.retry_counts["execution"] = p.retry_counts.get("execution", 0) + 1
        p._transition_count += 1
        logger.info("Pipeline entering execution (attempt %d)", p.retry_counts["execution"])

    def on_enter_verification(self) -> None:
        self.pipeline._transition_count += 1
        logger.info("Pipeline entering verification")

    def on_enter_completed(self) -> None:
        self.pipeline._transition_count += 1
        logger.info("Pipeline completed after %d transitions", self.pipeline._transition_count)

    def on_enter_failed(self) -> None:
        self.pipeline._transition_count += 1
        logger.warning("Pipeline failed after %d transitions", self.pipeline._transition_count)


def create_pipeline(
    listeners: list[object] | None = None,
) -> AgentPipeline:
    """Factory that wires the ``PipelineTracker`` and optional extra listeners."""
    pipeline = AgentPipeline.__new__(AgentPipeline)
    pipeline.retry_counts = {"scoping": 0, "discovery": 0, "planning": 0, "execution": 0}
    pipeline.retry_budget = 3
    pipeline._transition_count = 0
    tracker = PipelineTracker(pipeline)
    all_listeners = [tracker, *(listeners or [])]
    AgentPipeline.__init__(pipeline, listeners=all_listeners)
    return pipeline
