"""Strategy plan data models.

These models represent the structured strategy plan that the LLM agent builds,
the user inspects/edits via an interactive UI, and the system executes.  They
are pure data models with no I/O — part of the domain layer.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONValue

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
    value: JSONValue | None = None
    status: ParamStatus
    required: bool
    description: str | None = None
    constraints: dict[str, JSONValue] | None = None
    depends_on: list[str] = Field(default_factory=list)
    vocabulary_summary: str | None = None
    question: str | None = None
    options: list[str] | None = None
    rationale: str | None = None


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
    answer: JSONValue | None = None


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
