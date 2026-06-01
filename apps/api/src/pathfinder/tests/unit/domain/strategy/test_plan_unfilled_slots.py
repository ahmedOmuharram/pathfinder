"""Stage A: slot-filling protocol — NEEDS_DISCOVERY and NEEDS_USER_INPUT
become first-class slot states the planning agent can emit.

The fa2deb2b failure mode this prevents: planning agent guesses values for
parameters whose vocabulary or user intent is unclear, producing a plan
that silently coerces ("hard_floor=10" → 6772.93). With this protocol,
the agent emits unfilled slots that either route back to discovery
(``needs_discovery``) or surface a question card to the user
(``needs_user_input``).

Backend invariants tested:
- PlannedStepInput.unfilled_slots round-trips through _convert_step into
  PlannedParameter rows with the right ParamStatus.
- A ``needs_user_input`` slot's UserQuestion is appended to plan.questions
  for the submit_plan card to render.
- _validate_domain_parameters allows NEEDS_DISCOVERY and NEEDS_USER_INPUT
  on required leaf params (treated as legitimate slot states, not errors).
"""

from __future__ import annotations

import pytest

from pathfinder.ai.tools.standalone._plan_models import (
    PlannedStepInput,
    UnfilledSlotInput,
    UserQuestionInput,
    _convert_step,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import NumberValue, SinglePickValue
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    StepStatus,
    StepType,
)


def _spec(
    name: str, *, allow_empty: bool = False, param_type: str = "string"
) -> ParamSpecNormalized:
    return ParamSpecNormalized(
        name=name,
        param_type=param_type,
        allow_empty_value=allow_empty,
    )


def test_unfilled_slot_needs_discovery_yields_planned_parameter() -> None:
    """A slot marked ``needs_discovery`` becomes a PlannedParameter with
    status NEEDS_DISCOVERY and no value."""
    step_input = PlannedStepInput(
        search_name="GenesByRNASeqFoldChange",
        display_name="Fold change",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"fold_change": NumberValue(value=10)},
        unfilled_slots=[
            UnfilledSlotInput(
                name="samples_fc_comp_generic",
                reason="needs_discovery",
            ),
        ],
    )
    spec_map = {
        "fold_change": _spec("fold_change", param_type="number"),
        "samples_fc_comp_generic": _spec(
            "samples_fc_comp_generic", param_type="multi-pick-vocabulary"
        ),
    }
    step = _convert_step(step_input, param_specs=spec_map)
    assert step.status == StepStatus.READY
    fold = next(p for p in step.parameters if p.name == "fold_change")
    comp = next(p for p in step.parameters if p.name == "samples_fc_comp_generic")
    assert fold.status == ParamStatus.SET
    assert fold.value == NumberValue(value=10)
    assert comp.status == ParamStatus.NEEDS_DISCOVERY
    assert comp.value is None


def test_unfilled_slot_needs_user_input_yields_planned_parameter() -> None:
    """A slot marked ``needs_user_input`` becomes a PlannedParameter with
    status NEEDS_USER_INPUT and the question is exposed for plan-level
    aggregation (submit_plan card renders it as a form field)."""
    step_input = PlannedStepInput(
        search_name="GenesByRNASeqFoldChange",
        display_name="Fold change",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"fold_change": NumberValue(value=10)},
        unfilled_slots=[
            UnfilledSlotInput(
                name="hard_floor",
                reason="needs_user_input",
                question=UserQuestionInput(
                    question="hard_floor must be one of [1693, 3386, 6772, 16932, 33864] tiers — which one matches your read-floor intent?",
                    related_param="hard_floor",
                ),
            ),
        ],
    )
    spec_map = {
        "fold_change": _spec("fold_change", param_type="number"),
        "hard_floor": _spec("hard_floor", param_type="single-pick-vocabulary"),
    }
    step = _convert_step(step_input, param_specs=spec_map)
    hf = next(p for p in step.parameters if p.name == "hard_floor")
    assert hf.status == ParamStatus.NEEDS_USER_INPUT
    assert hf.value is None


def test_unfilled_slot_needs_user_input_requires_question() -> None:
    """Pydantic refuses an UnfilledSlotInput with reason='needs_user_input'
    but no question — that combination would be a silent gap."""
    with pytest.raises(ValueError, match="question"):
        UnfilledSlotInput(
            name="hard_floor",
            reason="needs_user_input",
            question=None,
        )


def test_unfilled_slot_overrides_value_in_parameters_dict() -> None:
    """If a name appears in BOTH ``parameters`` (as a value) AND
    ``unfilled_slots`` (as a needs_*), the unfilled_slot wins. This
    prevents the agent from emitting both a guess AND a question — the
    explicit gap is the source of truth."""
    step_input = PlannedStepInput(
        search_name="GenesByRNASeqFoldChange",
        display_name="Fold change",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"hard_floor": SinglePickValue(value="10")},  # bogus guess
        unfilled_slots=[
            UnfilledSlotInput(
                name="hard_floor",
                reason="needs_user_input",
                question=UserQuestionInput(
                    question="Pick a tier",
                    related_param="hard_floor",
                ),
            ),
        ],
    )
    spec_map = {"hard_floor": _spec("hard_floor", param_type="single-pick-vocabulary")}
    step = _convert_step(step_input, param_specs=spec_map)
    params = [p for p in step.parameters if p.name == "hard_floor"]
    assert len(params) == 1
    assert params[0].status == ParamStatus.NEEDS_USER_INPUT
    assert params[0].value is None
