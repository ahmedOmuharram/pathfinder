"""Plan tool response models, input models, and helpers."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)
from pydantic_ai.exceptions import ModelRetry

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import (
    ParamValue,
    as_param_kind,
    coerce_param_value,
)
from pathfinder.domain.parameters.wdk_vocab import WDKVocabulary, flatten_vocab
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME
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
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject

UnfilledSlotReason = Literal["needs_discovery", "needs_user_input"]
_PARAM_STATUS_FOR_REASON: dict[UnfilledSlotReason, ParamStatus] = {
    "needs_discovery": ParamStatus.NEEDS_DISCOVERY,
    "needs_user_input": ParamStatus.NEEDS_USER_INPUT,
}


class UnfilledSlotInput(BaseModel):
    """A parameter slot the planning agent cannot fill from discovery.

    The planner emits one of these when (a) the parameter's vocabulary is
    unknown and discovery must enumerate it (``needs_discovery``), or (b)
    the vocabulary is known but the user's intent does not map cleanly
    to one option and the user must answer (``needs_user_input``). For
    ``needs_user_input``, ``question`` is required so the submit_plan
    card can render a form field; for ``needs_discovery``, the supervisor
    routes back to discovery scoped to this parameter.
    """

    name: str
    reason: UnfilledSlotReason
    question: UserQuestionInput | None = None

    @model_validator(mode="after")
    def _question_required_for_user_input(self) -> UnfilledSlotInput:
        if self.reason == "needs_user_input" and self.question is None:
            msg = (
                "UnfilledSlotInput.question is required when "
                "reason='needs_user_input' — the question is what the "
                "submit_plan card renders as a form field for the user."
            )
            raise ValueError(msg)
        return self


_OPERATOR_STRINGS_AS_SEARCH_NAME: frozenset[str] = frozenset(
    {
        "intersect",
        "union",
        "minus",
        "rminus",
        "lonly",
        "ronly",
        "colocate",
    }
)


class PlannedStepInput(BaseModel):
    """Input model for a planned step from the LLM."""

    model_config = ConfigDict()

    id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:8]}")
    search_name: str
    display_name: str
    record_type: str = "transcript"
    rationale: str = ""
    step_type: StepType = StepType.LEAF
    parameters: dict[str, ParamValue] = Field(
        default_factory=dict,
        description=(
            "Each value MUST be wrapped in its typed shape (`type` discriminator). "
            "Use the `valueFormat` field from `get_search_overview` per param. "
            'Example: `{"organism": {"type": "multi-pick-vocabulary", "values": ["Pf3D7"]}}`.'
        ),
    )
    unfilled_slots: list[UnfilledSlotInput] = Field(default_factory=list)
    operator: str | None = None
    left_id: str | None = Field(
        default=None,
        description="For step_type='combine' ONLY: the id of the FIRST input "
        "step. The two inputs are wired automatically — do not author "
        "connections by hand.",
    )
    right_id: str | None = Field(
        default=None,
        description="For step_type='combine' ONLY: the id of the SECOND input step.",
    )
    input_id: str | None = Field(
        default=None,
        description="For step_type='transform' ONLY: the id of the single "
        "input step this transform consumes.",
    )

    @model_validator(mode="after")
    def _normalize_combine_search_name(self) -> PlannedStepInput:
        if self.step_type != StepType.COMBINE:
            return self
        if (
            self.search_name.lower() in _OPERATOR_STRINGS_AS_SEARCH_NAME
            or not self.search_name
        ):
            self.search_name = COMBINE_SEARCH_NAME
        return self


class UserQuestionInput(BaseModel):
    """Input model for a user question from the LLM."""

    question: str
    context: str = ""
    related_step: str | None = None
    related_param: str | None = None
    options: list[DecisionOptionInput] | None = None


class StepPatch(BaseModel):
    """Patch to apply to an existing planned step."""

    step_id: str
    search_name: str | None = None
    display_name: str | None = None
    parameters: dict[str, ParamValue] | None = Field(
        default=None,
        description=(
            "Each value MUST be wrapped in its typed shape (`type` discriminator). "
            "See `valueFormat` from `get_search_overview` for the per-param template."
        ),
    )
    unfilled_slots: list[UnfilledSlotInput] | None = None
    rationale: str | None = None
    operator: str | None = None
    left_id: str | None = Field(
        default=None,
        description="Re-wire a combine step's FIRST input to this step id.",
    )
    right_id: str | None = Field(
        default=None,
        description="Re-wire a combine step's SECOND input to this step id.",
    )
    input_id: str | None = Field(
        default=None,
        description="Re-wire a transform step's input to this step id.",
    )


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


def _convert_step(
    s: PlannedStepInput,
    *,
    param_specs: dict[str, ParamSpecNormalized] | None = None,
) -> PlannedStep:
    """Convert an input step to a domain PlannedStep.

    When *param_specs* is provided (keyed by parameter name), real WDK
    metadata (param_type, description, depends_on, required) is used
    instead of the default ``"string"`` placeholder. ``unfilled_slots``
    overrides ``parameters``: if a name appears in both, the slot wins
    (the explicit gap is the source of truth — prevents the agent from
    emitting a guess AND a question for the same param).
    """
    unfilled_by_name = {slot.name: slot for slot in s.unfilled_slots}
    params: list[PlannedParameter] = []
    for name, value in s.parameters.items():
        if name in unfilled_by_name:
            continue
        spec = param_specs.get(name) if param_specs else None
        params.append(_build_param(name, value, spec))
    for slot in s.unfilled_slots:
        spec = param_specs.get(slot.name) if param_specs else None
        params.append(_build_unfilled_param(slot, spec))
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
        left_id=s.left_id,
        right_id=s.right_id,
        input_id=s.input_id,
    )


def derive_connections(steps: list[PlannedStep]) -> list[PlannedConnection]:
    """Derive plan connections from each step's declared inputs (combine:
    left_id/right_id; transform: input_id)."""
    conns: list[PlannedConnection] = []
    for step in steps:
        if step.step_type == StepType.COMBINE:
            if step.left_id:
                conns.append(
                    PlannedConnection(
                        from_step=step.left_id,
                        to_step=step.id,
                        input_type="primary",
                        operator=step.operator,
                    )
                )
            if step.right_id:
                conns.append(
                    PlannedConnection(
                        from_step=step.right_id,
                        to_step=step.id,
                        input_type="secondary",
                        operator=step.operator,
                    )
                )
        elif step.step_type == StepType.TRANSFORM and step.input_id:
            conns.append(
                PlannedConnection(
                    from_step=step.input_id,
                    to_step=step.id,
                    input_type="primary",
                    operator=step.operator,
                )
            )
    return conns


def _build_unfilled_param(
    slot: UnfilledSlotInput,
    spec: ParamSpecNormalized | None,
) -> PlannedParameter:
    """Construct a PlannedParameter for an unfilled slot.

    Spec is required (same rationale as ``_build_param``): the frontend
    widget registry needs the real WDK type to render the right form
    control. Only the status differs from a SET param.
    """
    if spec is None:
        msg = (
            f"Cannot build PlannedParameter for unfilled slot {slot.name!r}: "
            "no WDK ParamSpec available. Discovery must inspect the search "
            "before planning emits unfilled slots for it."
        )
        raise ValueError(msg)
    kind = as_param_kind(spec.param_type)
    return PlannedParameter(
        name=slot.name,
        display_name=slot.name,
        param_type=kind,
        value=None,
        status=_PARAM_STATUS_FOR_REASON[slot.reason],
        required=not spec.allow_empty_value,
        description=spec.help,
        depends_on=list(spec.dependent_params),
        constraints=_build_constraints(spec),
        options=_extract_vocab_values(spec.vocabulary),
    )


def _build_param(
    name: str,
    value: ParamValue | None,
    spec: ParamSpecNormalized | None,
) -> PlannedParameter:
    if spec is None:
        msg = (
            f"Cannot build PlannedParameter for {name!r}: no WDK ParamSpec "
            "available. Callers must supply a spec (or run discovery first)."
        )
        raise ValueError(msg)
    kind = as_param_kind(spec.param_type)
    if value is not None:
        try:
            value = coerce_param_value(value, kind)
        except ValueError as exc:
            msg = (
                f"PlannedParameter {name!r}: {exc}. Wrap it as "
                f"{{'type': {kind!r}, ...}} — see the param's valueFormat."
            )
            raise ValueError(msg) from exc
    return PlannedParameter(
        name=name,
        display_name=name,
        param_type=kind,
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


def _extract_vocab_values(
    vocabulary: WDKVocabulary | None,
) -> list[str] | None:
    """Extract vocabulary option values from a typed WDK vocabulary."""
    values = [option.value for option in flatten_vocab(vocabulary)]
    return values or None


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


def _validate_domain_topology(plan: StrategyPlan) -> None:
    """Re-run topology invariants after in-place mutation of a plan."""
    try:
        plan.verify_topology()
    except PlanTopologyError as exc:
        msg = f"TOPOLOGY_ERROR: {exc}"
        raise ModelRetry(msg) from exc


def _validate_domain_parameters(
    plan: StrategyPlan,
    agent_state: object,
) -> None:
    """Validate that leaf steps have required parameters set.

    NEEDS_DISCOVERY and NEEDS_USER_INPUT count as legitimate slot states —
    they're the explicit-gap protocol from Stage A, not errors. The
    submit-time guard in ``submit_plan`` and the execution-time refusal
    in ``build_strategy_from_spec`` enforce that NEEDS_* are resolved
    before the plan ships to WDK; ``_validate_domain_parameters`` only
    catches *silently* unset required params.
    """
    legit_unset = {ParamStatus.NEEDS_DISCOVERY, ParamStatus.NEEDS_USER_INPUT}
    non_leaf_ids = {c.to_step for c in plan.connections}
    for step in plan.steps:
        if step.id in non_leaf_ids:
            continue
        if step.step_type == StepType.LEAF:
            missing = [
                param.name
                for param in step.parameters
                if param.required
                and param.status != ParamStatus.SET
                and param.status not in legit_unset
            ]
            if missing:
                msg = (
                    f"PARAMETER_ERROR: Step '{step.display_name}' (id={step.id}) "
                    f"has unset required parameters: {', '.join(missing)}. "
                    "Use update_plan with step_updates to set them."
                )
                raise ModelRetry(msg)


def _apply_step_patches(
    plan: StrategyPlan,
    patches: list[StepPatch],
    *,
    specs_by_search: dict[str, dict[str, ParamSpecNormalized]] | None = None,
) -> None:
    """Apply patches to steps in a plan. Raises ModelRetry if step not found.

    *specs_by_search* maps ``search_name → {param_name → spec}`` so that
    newly added parameters get real WDK metadata.
    """
    step_map = {s.id: s for s in plan.steps}
    for patch in patches:
        step = step_map.get(patch.step_id)
        if step is None:
            msg = (
                f"STEP_NOT_FOUND: Step '{patch.step_id}' not found in plan. "
                f"Valid step ids: {sorted(step_map.keys())}."
            )
            raise ModelRetry(msg)
        _apply_metadata_patch(step, patch)
        param_specs = specs_by_search.get(step.search_name) if specs_by_search else None
        if patch.parameters is not None:
            _apply_parameters_patch(step, patch.parameters, param_specs)
        if patch.unfilled_slots is not None:
            _apply_unfilled_slots_patch(step, patch.unfilled_slots, param_specs)


def _apply_metadata_patch(step: PlannedStep, patch: StepPatch) -> None:
    if patch.search_name is not None:
        step.search_name = patch.search_name
    if patch.display_name is not None:
        step.display_name = patch.display_name
    if patch.rationale is not None:
        step.rationale = patch.rationale
    if patch.operator is not None:
        step.operator = patch.operator
    if patch.left_id is not None:
        step.left_id = patch.left_id
    if patch.right_id is not None:
        step.right_id = patch.right_id
    if patch.input_id is not None:
        step.input_id = patch.input_id


def _apply_parameters_patch(
    step: PlannedStep,
    parameters: dict[str, ParamValue],
    param_specs: dict[str, ParamSpecNormalized] | None,
) -> None:
    for name, value in parameters.items():
        existing = next(
            (p for p in step.parameters if p.name == name),
            None,
        )
        if existing is not None:
            existing.value = coerce_param_value(value, existing.param_type)
            existing.status = ParamStatus.SET
        else:
            spec = param_specs.get(name) if param_specs else None
            step.parameters.append(_build_param(name, value, spec))


def _apply_unfilled_slots_patch(
    step: PlannedStep,
    slots: list[UnfilledSlotInput],
    param_specs: dict[str, ParamSpecNormalized] | None,
) -> None:
    for slot in slots:
        spec = param_specs.get(slot.name) if param_specs else None
        existing = next(
            (p for p in step.parameters if p.name == slot.name),
            None,
        )
        rebuilt = _build_unfilled_param(slot, spec)
        if existing is not None:
            existing.value = None
            existing.status = rebuilt.status
            existing.param_type = rebuilt.param_type
        else:
            step.parameters.append(rebuilt)
