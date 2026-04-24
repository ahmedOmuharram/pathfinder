"""Plan tool response models, input models, and helpers."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
)

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    PlanTopologyError,
    QuestionOption,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.domain.strategy.types import DecodedParamsField
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONArray, JSONObject


class PlannedStepInput(BaseModel):
    """Input model for a planned step from the LLM."""

    model_config = ConfigDict()

    id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:8]}")
    search_name: str
    display_name: str
    record_type: str = "transcript"
    rationale: str = ""
    step_type: StepType = StepType.LEAF
    parameters: DecodedParamsField = Field(default_factory=dict)
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
    options: list[DecisionOptionInput] | None = None

class ConnectionRef(BaseModel):
    """Reference to a connection for removal."""

    from_step: str
    to_step: str

class StepPatch(BaseModel):
    """Patch to apply to an existing planned step."""

    step_id: str
    search_name: str | None = None
    display_name: str | None = None
    parameters: DecodedParamsField | None = None
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

def _convert_step(
    s: PlannedStepInput,
    *,
    param_specs: dict[str, ParamSpecNormalized] | None = None,
) -> PlannedStep:
    """Convert an input step to a domain PlannedStep.

    When *param_specs* is provided (keyed by parameter name), real WDK
    metadata (param_type, description, depends_on, required) is used
    instead of the default ``"string"`` placeholder.
    """
    params: list[PlannedParameter] = [
        _build_param(name, value, param_specs.get(name) if param_specs else None)
        for name, value in s.parameters.items()
    ]
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

def _build_param(
    name: str,
    value: JsonValue,
    spec: ParamSpecNormalized | None,
) -> PlannedParameter:
    """Build a PlannedParameter, enriching from the WDK spec.

    The spec is mandatory. Silent fallback to ``param_type="string"`` is
    forbidden because the frontend widget registry requires real WDK types
    (treebox, typeahead, select, checkbox, number, ...) to render the
    correct input. A bogus "string" type corrupts the UI layer.
    """
    if spec is None:
        msg = (
            f"Cannot build PlannedParameter for {name!r}: no WDK ParamSpec "
            "available. Callers must supply a spec (or run discovery first). "
            "Silent fallback to param_type='string' is forbidden — the "
            "frontend widget registry requires real WDK types to render "
            "the correct input."
        )
        raise ValueError(msg)
    return PlannedParameter(
        name=name,
        display_name=name,
        param_type=spec.param_type,
        value=value,
        status=ParamStatus.SET if value is not None else ParamStatus.NEEDS_DISCOVERY,
        required=not spec.allow_empty_value,
        description=spec.help,
        depends_on=list(spec.dependent_params),
        constraints=_build_constraints(spec),
        options=_extract_vocab_values(spec.vocabulary),
    )

def _build_constraints(spec: ParamSpecNormalized) -> dict[str, JsonValue] | None:
    """Build a constraints dict from WDK spec metadata."""
    constraints: dict[str, JsonValue] = {}
    if spec.display_type:
        constraints["displayType"] = spec.display_type
    if spec.is_number:
        constraints["isNumber"] = True
    if spec.min is not None:
        constraints["min"] = spec.min
    if spec.max is not None:
        constraints["max"] = spec.max
    if spec.increment is not None:
        constraints["increment"] = spec.increment
    if spec.min_selected_count is not None:
        constraints["minSelectedCount"] = spec.min_selected_count
    if spec.max_selected_count is not None:
        constraints["maxSelectedCount"] = spec.max_selected_count
    if spec.max_length is not None:
        constraints["maxLength"] = spec.max_length
    return constraints or None

class _VocabItem(BaseModel):
    """WDK vocabulary list entry shape: ``{"value": str, "display": ..., ...}``.

    ``extra="ignore"`` forward-compatible with new WDK fields.  A raw string
    is also accepted via the ``str`` arm of the union in ``_VOCAB_ADAPTER``.
    """

    model_config = ConfigDict(extra="ignore")
    value: str

_VOCAB_ADAPTER: TypeAdapter[list[_VocabItem | str]] = TypeAdapter(
    list[_VocabItem | str]
)

def _extract_vocab_values(
    vocabulary: JSONObject | JSONArray | None,
) -> list[str] | None:
    """Extract vocabulary option values from a WDK vocabulary payload.

    Routes validation through a typed ``TypeAdapter[list[_VocabItem | str]]``
    so the isinstance discrimination happens inside Pydantic rather than
    being scattered at the call site.
    """
    if vocabulary is None:
        return None
    try:
        items = _VOCAB_ADAPTER.validate_python(vocabulary)
    except ValidationError:
        return None
    values = [entry if isinstance(entry, str) else entry.value for entry in items]
    return values or None

def _convert_connection(c: PlannedConnectionInput) -> PlannedConnection:
    """Convert an input connection to a domain PlannedConnection."""
    return PlannedConnection(
        from_step=c.from_step,
        to_step=c.to_step,
        input_type=c.input_type,
        operator=c.operator,
    )

def _convert_question(q: UserQuestionInput) -> UserQuestion:
    """Convert an input question to a domain UserQuestion.

    ``q.options`` is already ``list[DecisionOptionInput] | None`` — Pydantic
    has coerced, validated, and defaulted every field.  No dict.get chains
    or isinstance checks needed at this layer.
    """
    options = (
        [
            QuestionOption(
                label=o.label,
                description=o.description,
                pros=list(o.pros),
                cons=list(o.cons),
                recommended=o.recommended,
            )
            for o in q.options
        ]
        if q.options
        else None
    )
    return UserQuestion(
        id=f"q_{uuid4().hex[:8]}",
        question=q.question.strip(),
        context=q.context.strip(),
        related_step=q.related_step,
        related_param=q.related_param,
        options=options,
    )

def _validate_domain_topology(plan: StrategyPlan) -> ToolErrorPayload | None:
    """Re-run topology invariants after in-place mutation of a plan."""
    try:
        plan.verify_topology()
    except PlanTopologyError as exc:
        return tool_error("TOPOLOGY_ERROR", str(exc))
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
                param.name for param in step.parameters
                if param.required and param.status != ParamStatus.SET
            ]
            if missing:
                return tool_error(
                    "PARAMETER_ERROR",
                    f"Step '{step.display_name}' has unset required parameters: {', '.join(missing)}",
                    stepId=step.id,
                    missingParams=cast("list[JsonValue]", missing),
                )
    return None

def _apply_step_patches(
    plan: StrategyPlan,
    patches: list[StepPatch],
    *,
    specs_by_search: dict[str, dict[str, ParamSpecNormalized]] | None = None,
) -> ToolErrorPayload | None:
    """Apply patches to steps in a plan. Returns error if step not found.

    *specs_by_search* maps ``search_name → {param_name → spec}`` so that
    newly added parameters get real WDK metadata.
    """
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
            param_specs = (
                specs_by_search.get(step.search_name)
                if specs_by_search
                else None
            )
            for name, value in patch.parameters.items():
                existing = next(
                    (p for p in step.parameters if p.name == name), None,
                )
                if existing is not None:
                    existing.value = value
                    existing.status = ParamStatus.SET
                else:
                    spec = param_specs.get(name) if param_specs else None
                    step.parameters.append(_build_param(name, value, spec))
    return None
