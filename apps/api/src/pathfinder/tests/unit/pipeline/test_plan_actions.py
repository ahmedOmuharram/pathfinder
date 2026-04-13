"""Unit tests for structured plan approval mutations."""

from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)
from pathfinder.domain.strategy.plan_actions import (
    PlanParameterEdit,
    PlanQuestionAnswer,
    apply_plan_approval,
)


def _make_plan_with_questioned_param() -> StrategyPlan:
    return StrategyPlan(
        id="plan_test",
        title="Questioned plan",
        description="Test approval behavior",
        rationale="Test",
        status=PlanStatus.PRESENTED,
        steps=[
            PlannedStep(
                id="step_tm",
                search_name="GenesByTransmembraneDomains",
                display_name="At least N TM domains",
                step_type=StepType.LEAF,
                status=StepStatus.NEEDS_USER_INPUT,
                parameters={
                    "min_tm": PlannedParameter(
                        name="min_tm",
                        display_name="Minimum TM domains",
                        param_type="integer",
                        value="2",
                        status=ParamStatus.NEEDS_USER_INPUT,
                        required=True,
                        question="How many TM domains should we require?",
                    ),
                },
            )
        ],
        connections=[],
        questions=[
            UserQuestion(
                id="q_tm_threshold",
                question="How many TM domains should we require?",
                related_step="step_tm",
                related_param="min_tm",
            )
        ],
    )


def test_answer_stored_on_question_but_does_not_overwrite_param() -> None:
    plan = _make_plan_with_questioned_param()

    approved = apply_plan_approval(
        plan,
        param_edits=[],
        answers=[
            PlanQuestionAnswer(
                question_id="q_tm_threshold",
                answer="5",
            )
        ],
    )

    assert approved.status == PlanStatus.APPROVED
    assert approved.questions[0].answer == "5"
    # Parameter keeps its original value — answers never auto-promote to params
    assert approved.steps[0].parameters["min_tm"].value == "2"
    assert approved.steps[0].parameters["min_tm"].status == ParamStatus.NEEDS_USER_INPUT


def test_freeform_answer_with_related_param_does_not_set_param() -> None:
    plan = _make_plan_with_questioned_param()

    approved = apply_plan_approval(
        plan,
        param_edits=[],
        answers=[
            PlanQuestionAnswer(
                question_id="q_tm_threshold",
                answer="It is sufficient",
            )
        ],
    )

    assert approved.questions[0].answer == "It is sufficient"
    # Free-form text must never end up as a WDK parameter value
    assert approved.steps[0].parameters["min_tm"].value == "2"
    assert approved.steps[0].parameters["min_tm"].status == ParamStatus.NEEDS_USER_INPUT


def test_explicit_param_edit_is_only_way_to_change_param() -> None:
    plan = _make_plan_with_questioned_param()

    approved = apply_plan_approval(
        plan,
        param_edits=[
            PlanParameterEdit(
                step_id="step_tm",
                param_name="min_tm",
                new_value="6",
            )
        ],
        answers=[
            PlanQuestionAnswer(
                question_id="q_tm_threshold",
                answer="5",
            )
        ],
    )

    # Answer is stored on the question
    assert approved.questions[0].answer == "5"
    # Param changed ONLY because of the explicit edit, not the answer
    assert approved.steps[0].parameters["min_tm"].value == "6"
    assert approved.steps[0].parameters["min_tm"].status == ParamStatus.USER_SET
