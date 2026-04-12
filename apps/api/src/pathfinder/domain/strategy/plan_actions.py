"""Structured plan-action models and plan mutation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlanStatus,
    StepStatus,
    StrategyPlan,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONValue

PlanActionType = Literal["approve", "reject", "suggest_changes"]


class PlanParameterEdit(CamelModel):
    """A structured parameter edit collected from the plan UI."""

    step_id: str
    param_name: str
    new_value: JSONValue


class PlanQuestionAnswer(CamelModel):
    """A structured answer collected from the plan UI."""

    question_id: str
    answer: JSONValue


class PlanActionContext(CamelModel):
    """Structured plan-action context carried through the backend."""

    action: PlanActionType
    plan_id: str
    source_trace_id: str | None = None
    source_message_group_id: str | None = None
    source: str | None = None
    answered_question_ids: list[str] = Field(default_factory=list)
    edited_params: list[str] = Field(default_factory=list)
    presented_at: datetime | None = None
    approved_at: datetime | None = None
    approval_wait_ms: int | None = None


def _refresh_step_statuses(plan: StrategyPlan) -> None:
    """Recompute step readiness after user answers/edits are applied."""
    answered_questions = {
        question.id
        for question in plan.questions
        if question.answer is not None
    }

    for step in plan.steps:
        if step.status in (
            StepStatus.COMPLETE,
            StepStatus.EXECUTING,
            StepStatus.FAILED,
        ):
            continue

        has_needs_discovery = any(
            parameter.status == ParamStatus.NEEDS_DISCOVERY
            for parameter in step.parameters.values()
        )
        if has_needs_discovery:
            step.status = StepStatus.NEEDS_DISCOVERY
            continue

        unanswered_for_step = any(
            question.answer is None
            and question.related_step == step.id
            and question.id not in answered_questions
            for question in plan.questions
        )
        has_unset_required_param = any(
            parameter.required
            and (
                parameter.value is None
                or parameter.status == ParamStatus.NEEDS_USER_INPUT
            )
            for parameter in step.parameters.values()
        )
        if unanswered_for_step or has_unset_required_param:
            step.status = StepStatus.NEEDS_USER_INPUT
            continue

        step.status = StepStatus.READY


def apply_plan_approval(
    plan: StrategyPlan,
    *,
    param_edits: list[PlanParameterEdit],
    answers: list[PlanQuestionAnswer],
) -> StrategyPlan:
    """Apply UI answers/edits to a presented plan and mark it approved."""
    step_by_id = {step.id: step for step in plan.steps}
    question_by_id = {question.id: question for question in plan.questions}
    explicitly_edited_params = {
        (edit.step_id, edit.param_name) for edit in param_edits
    }

    for answer in answers:
        question = question_by_id.get(answer.question_id)
        if question is None:
            raise ValidationError(
                title="Invalid plan answer",
                detail=f"Unknown question '{answer.question_id}'.",
            )
        question.answer = answer.answer
        if question.related_step and question.related_param:
            step = step_by_id.get(question.related_step)
            if step is not None:
                parameter = step.parameters.get(question.related_param)
                if (
                    parameter is not None
                    and (question.related_step, question.related_param)
                    not in explicitly_edited_params
                ):
                    parameter.value = answer.answer
                    parameter.status = ParamStatus.USER_SET

    for edit in param_edits:
        step = step_by_id.get(edit.step_id)
        if step is None:
            raise ValidationError(
                title="Invalid plan parameter edit",
                detail=f"Unknown step '{edit.step_id}'.",
            )
        parameter = step.parameters.get(edit.param_name)
        if parameter is None:
            raise ValidationError(
                title="Invalid plan parameter edit",
                detail=(
                    f"Unknown parameter '{edit.param_name}' on step '{edit.step_id}'."
                ),
            )
        parameter.value = edit.new_value
        parameter.status = ParamStatus.USER_SET

    _refresh_step_statuses(plan)
    plan.status = PlanStatus.APPROVED
    plan.updated_at = datetime.now(UTC)
    return plan
