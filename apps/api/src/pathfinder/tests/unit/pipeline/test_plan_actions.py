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


def test_apply_plan_approval_overwrites_default_param_with_answer() -> None:
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
    assert approved.steps[0].parameters["min_tm"].value == "5"
    assert approved.steps[0].parameters["min_tm"].status == ParamStatus.USER_SET
    assert approved.steps[0].status == StepStatus.READY


def test_apply_plan_approval_prefers_explicit_param_edit_over_answer() -> None:
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

    assert approved.questions[0].answer == "5"
    assert approved.steps[0].parameters["min_tm"].value == "6"
    assert approved.steps[0].parameters["min_tm"].status == ParamStatus.USER_SET
