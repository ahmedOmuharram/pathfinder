"""Strategy plan data models.

These models represent the structured strategy plan that the LLM agent builds,
the user inspects/edits via an interactive UI, and the system executes.  They
are pure data models with no I/O — part of the domain layer.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field, JsonValue

from pathfinder.platform.pydantic_base import CamelModel

# ── Enums ───────────────────────────────────────────────────────────

class PlanStatus(StrEnum):
    """Lifecycle status of a StrategyPlan."""

    DRAFT = "draft"
    PRESENTED = "presented"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETE = "complete"
    FAILED = "failed"

class StepStatus(StrEnum):
    """Readiness status of an individual PlannedStep."""

    READY = "ready"
    NEEDS_DISCOVERY = "needs_discovery"
    NEEDS_USER_INPUT = "needs_user_input"
    EXECUTING = "executing"
    COMPLETE = "complete"
    FAILED = "failed"

class StepType(StrEnum):
    """Structural type of a PlannedStep."""

    LEAF = "leaf"
    COMBINE = "combine"
    TRANSFORM = "transform"

class ParamStatus(StrEnum):
    """Resolution status of a PlannedParameter."""

    SET = "set"
    DEFAULT = "default"
    NEEDS_DISCOVERY = "needs_discovery"
    NEEDS_USER_INPUT = "needs_user_input"
    USER_SET = "user_set"

class FailureKind(StrEnum):
    """Classification of why a plan execution failed.

    Drives the FSM recovery path: ``search_invalid`` triggers
    ``retry_discovery_from_execution`` (execution -> discovery), while
    ``parameter_invalid`` triggers ``replan`` (execution -> planning).
    """

    SEARCH_INVALID = "search_invalid"
    """The chosen search is wrong for the biological question — rediscovery needed."""

    PARAMETER_INVALID = "parameter_invalid"
    """The search is right but parameters are off — replanning with the same catalog is enough."""

# ── Helpers ─────────────────────────────────────────────────────────

def _generate_plan_id() -> str:
    """Generate a plan ID: ``plan_<12 hex chars>``."""
    return f"plan_{uuid4().hex[:12]}"

def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)

# ── Data Models ─────────────────────────────────────────────────────

class PlannedParameter(CamelModel):
    """A parameter within a planned step, with its resolution status."""

    name: str
    display_name: str
    param_type: str
    value: JsonValue | None = None
    status: ParamStatus
    required: bool
    description: str | None = None
    constraints: dict[str, JsonValue] | None = None
    depends_on: list[str] = Field(default_factory=list)
    options: list[str] | None = None

class QuestionOption(CamelModel):
    """One option presented to the user for a UserQuestion."""

    label: str
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommended: bool = False

class UserQuestion(CamelModel):
    """A question the system needs to ask the user to resolve ambiguity."""

    id: str
    question: str
    context: str = ""
    related_step: str | None = None
    related_param: str | None = None
    options: list[QuestionOption] | None = None
    answer: JsonValue | None = None

class PlannedStep(CamelModel):
    """A single step in a strategy plan."""

    id: str
    search_name: str
    display_name: str
    record_type: str = "transcript"
    rationale: str = ""
    step_type: StepType
    status: StepStatus
    parameters: dict[str, PlannedParameter] = Field(default_factory=dict)
    operator: str | None = None
    expected_count: int | None = None
    actual_count: int | None = None
    wdk_step_id: int | None = None
    graph_step_id: str | None = None
    failure_reason: str | None = None

class PlannedConnection(CamelModel):
    """A directed edge between two planned steps."""

    from_step: str
    to_step: str
    input_type: str = "primary"
    operator: str | None = None

class StrategyPlan(CamelModel):
    """The full strategy plan: steps, connections, questions, metadata."""

    id: str = Field(default_factory=_generate_plan_id)
    title: str
    description: str
    rationale: str
    status: PlanStatus = PlanStatus.DRAFT
    version: int = 1
    steps: list[PlannedStep]
    connections: list[PlannedConnection]
    questions: list[UserQuestion] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def steps_in_dependency_order(self) -> list[PlannedStep]:
        """Return steps topologically sorted so dependencies come first.

        Leaf steps (no incoming connections) come first, then combine/transform
        steps whose inputs are already resolved.  Raises ``ValueError`` if
        the connection graph contains a cycle.
        """
        step_by_id = {s.id: s for s in self.steps}

        # Build adjacency: to_step depends on from_step
        dependents: dict[str, set[str]] = {s.id: set() for s in self.steps}
        for conn in self.connections:
            if conn.to_step in dependents and conn.from_step in step_by_id:
                dependents[conn.to_step].add(conn.from_step)

        # Kahn's algorithm
        ordered: list[PlannedStep] = []
        ready = [sid for sid, deps in dependents.items() if not deps]

        while ready:
            sid = ready.pop(0)
            ordered.append(step_by_id[sid])
            for other, deps in dependents.items():
                if sid in deps:
                    deps.discard(sid)
                    if not deps:
                        ready.append(other)

        if len(ordered) != len(self.steps):
            msg = "Cycle detected in plan connections"
            raise ValueError(msg)

        return ordered

    def classify_failure(self, *, planning_attempts: int = 1) -> FailureKind:
        """Classify why this plan failed.

        Conservative heuristic per the FSM recovery spec:
        * A failure reason that reads like a WDK parameter validation error
          maps to :attr:`FailureKind.PARAMETER_INVALID`.
        * A zero-result run that has already been replanned more than once
          maps to :attr:`FailureKind.SEARCH_INVALID` (the catalog choice is
          the problem, not the parameters).
        * Default -> :attr:`FailureKind.PARAMETER_INVALID`, which preserves
          the existing ``replan`` behaviour for unknown causes.

        :param planning_attempts: How many times planning has been entered
            for this turn (``state.phase_call_counts['planning']``). Used to
            decide whether a zero-result run has already exhausted the
            same-catalog replanning escape hatch.
        """
        failed_steps = [s for s in self.steps if s.status == StepStatus.FAILED]
        if not failed_steps:
            return FailureKind.PARAMETER_INVALID

        # If any step's failure reason looks like a parameter validation
        # error, trust the search and replan parameters.
        for step in failed_steps:
            reason = (step.failure_reason or "").lower()
            if _is_parameter_validation_error(reason):
                return FailureKind.PARAMETER_INVALID

        # Zero-result runs only escalate to SEARCH_INVALID after the
        # same-catalog replanning escape hatch is spent.
        zero_result = any(
            step.actual_count == 0 for step in failed_steps
        )
        if zero_result and planning_attempts > 1:
            return FailureKind.SEARCH_INVALID

        return FailureKind.PARAMETER_INVALID

_PARAMETER_ERROR_MARKERS: tuple[str, ...] = (
    "invalid parameter",
    "parameter validation",
    "invalid value for",
    "missing required parameter",
    "unknown parameter",
)

def _is_parameter_validation_error(reason: str) -> bool:
    """Return ``True`` when *reason* matches a WDK parameter-validation message."""
    return any(marker in reason for marker in _PARAMETER_ERROR_MARKERS)
