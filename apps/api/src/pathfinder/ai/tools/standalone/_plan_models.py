"""Plan tool response models, input models, and helpers."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    QuestionOption,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject, JSONValue


class PlannedStepInput(BaseModel):
    """Input model for a planned step from the LLM."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:8]}")
    search_name: str
    display_name: str
    record_type: str = "transcript"
    rationale: str = ""
    step_type: StepType = StepType.LEAF
    parameters: dict[str, JSONValue] = Field(default_factory=dict)
    operator: str | None = None


class PlannedConnectionInput(BaseModel):
    """Input model for a planned connection from the LLM."""

    from_step: str
    to_step: str
    input_type: str = "primary"
    operator: str | None = None


class UserQuestionInput(BaseModel):
    """Input model for a user question from the LLM."""

    question: str
    context: str = ""
    related_step: str | None = None
    related_param: str | None = None
    options: list[dict[str, object]] | None = None


class ConnectionRef(BaseModel):
    """Reference to a connection for removal."""

    from_step: str
    to_step: str


class StepPatch(BaseModel):
    """Patch to apply to an existing planned step."""

    step_id: str
    search_name: str | None = None
    display_name: str | None = None
    parameters: dict[str, JSONValue] | None = None
    rationale: str | None = None
    operator: str | None = None


class PlanCreatedResponse(CamelModel):
    """Acknowledgment that a plan was created.

    Includes ``planning_artifact`` so the SSE event extractor can emit
    a ``planning_artifact`` event for the frontend's plan panel.
    """

    plan_id: str
    title: str
    step_count: int
    planning_artifact: JSONObject | None = None


class DecisionOptionInput(BaseModel):
    """Input model for a decision option."""

    label: str
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommended: bool = False


class DecisionOption(CamelModel):
    """A decision option."""

    label: str
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommended: bool = False


class DecisionResponse(CamelModel):
    """Response containing a decision for the user."""

    decision_id: str
    question: str
    options: list[DecisionOption] = Field(default_factory=list)
    context: str = ""
    recommendation: str | None = None


def _convert_step(s: PlannedStepInput) -> PlannedStep:
    """Convert an input step to a domain PlannedStep."""
    params: dict[str, PlannedParameter] = {}
    for name, value in s.parameters.items():
        params[name] = PlannedParameter(
            name=name,
            display_name=name,
            param_type="string",
            value=value,
            status=ParamStatus.SET if value is not None else ParamStatus.NEEDS_DISCOVERY,
            required=True,
        )
    return PlannedStep(
        id=s.id,
        search_name=s.search_name,
        display_name=s.display_name,
        record_type=s.record_type,
        rationale=s.rationale,
        step_type=s.step_type,
        status=StepStatus.READY,
        parameters=params,
        operator=s.operator,
    )


def _convert_connection(c: PlannedConnectionInput) -> PlannedConnection:
    """Convert an input connection to a domain PlannedConnection."""
    return PlannedConnection(
        from_step=c.from_step,
        to_step=c.to_step,
        input_type=c.input_type,
        operator=c.operator,
    )


def _to_str_list(val: object) -> list[str]:
    """Safely convert an object to a list of strings."""
    if isinstance(val, list):
        return [str(v) for v in val]
    return []


def _convert_question(q: UserQuestionInput) -> UserQuestion:
    """Convert an input question to a domain UserQuestion."""
    options = None
    if q.options:
        options = [
            QuestionOption(
                label=str(o.get("label", "")),
                description=str(o.get("description", "")),
                pros=_to_str_list(o.get("pros")),
                cons=_to_str_list(o.get("cons")),
                recommended=bool(o.get("recommended", False)),
            )
            for o in q.options
        ]
    return UserQuestion(
        id=f"q_{uuid4().hex[:8]}",
        question=q.question,
        context=q.context,
        related_step=q.related_step,
        related_param=q.related_param,
        options=options,
    )


def _validate_plan_topology(
    steps: list[PlannedStepInput],
    connections: list[PlannedConnectionInput],
) -> ToolErrorPayload | None:
    """Validate basic plan topology (all connection refs exist)."""
    step_ids = {s.id for s in steps}
    for conn in connections:
        if conn.from_step not in step_ids:
            return tool_error(
                "TOPOLOGY_ERROR",
                f"Connection references non-existent step: {conn.from_step}",
            )
        if conn.to_step not in step_ids:
            return tool_error(
                "TOPOLOGY_ERROR",
                f"Connection references non-existent step: {conn.to_step}",
            )
    return None


def _validate_domain_topology(plan: StrategyPlan) -> ToolErrorPayload | None:
    """Validate topology of a domain StrategyPlan."""
    step_ids = {s.id for s in plan.steps}
    for conn in plan.connections:
        if conn.from_step not in step_ids:
            return tool_error(
                "TOPOLOGY_ERROR",
                f"Connection references non-existent step: {conn.from_step}",
            )
        if conn.to_step not in step_ids:
            return tool_error(
                "TOPOLOGY_ERROR",
                f"Connection references non-existent step: {conn.to_step}",
            )
    return None


def _validate_domain_parameters(
    plan: StrategyPlan,
    agent_state: object,
) -> ToolErrorPayload | None:
    """Validate that leaf steps have required parameters set."""
    non_leaf_ids = {c.to_step for c in plan.connections}
    for step in plan.steps:
        if step.id in non_leaf_ids:
            continue
        if step.step_type == StepType.LEAF:
            missing = [
                name for name, param in step.parameters.items()
                if param.required and param.status != ParamStatus.SET
            ]
            if missing:
                return tool_error(
                    "PARAMETER_ERROR",
                    f"Step '{step.display_name}' has unset required parameters: {', '.join(missing)}",
                    stepId=step.id,
                    missingParams=cast("list[JSONValue]", missing),
                )
    return None


def _apply_step_patches(
    plan: StrategyPlan,
    patches: list[StepPatch],
) -> ToolErrorPayload | None:
    """Apply patches to steps in a plan. Returns error if step not found."""
    step_map = {s.id: s for s in plan.steps}
    for patch in patches:
        step = step_map.get(patch.step_id)
        if step is None:
            return tool_error(
                "STEP_NOT_FOUND",
                f"Step '{patch.step_id}' not found in plan.",
            )
        if patch.search_name is not None:
            step.search_name = patch.search_name
        if patch.display_name is not None:
            step.display_name = patch.display_name
        if patch.rationale is not None:
            step.rationale = patch.rationale
        if patch.operator is not None:
            step.operator = patch.operator
        if patch.parameters is not None:
            for name, value in patch.parameters.items():
                if name in step.parameters:
                    step.parameters[name].value = value
                    step.parameters[name].status = ParamStatus.SET
                else:
                    step.parameters[name] = PlannedParameter(
                        name=name,
                        display_name=name,
                        param_type="string",
                        value=value,
                        status=ParamStatus.SET,
                        required=True,
                    )
    return None
