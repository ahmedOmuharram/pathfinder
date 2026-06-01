"""Apply user-supplied slot answers to a ``StrategyPlan`` and refuse
submission if any slot is still unresolved.

Pure domain logic — no I/O, no agent context. Used by the Lead's
``submit_plan_for_approval`` deferred tool body when the user approves
the plan card.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.graph.state import PlanSlotAnswer
from pathfinder.domain.parameters.values import from_decoded
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlanStatus,
    StrategyPlan,
)


def apply_plan_slot_answers(
    plan: StrategyPlan,
    answers: list[PlanSlotAnswer],
) -> None:
    """Promote NEEDS_USER_INPUT params to USER_SET using the form answers.

    Mutates ``plan`` in place. Mirrors answers onto ``plan.questions`` so
    follow-up renderings show the user-supplied value.
    """
    if not answers:
        return
    step_map = {s.id: s for s in plan.steps}
    for ans in answers:
        step = step_map.get(ans.step_id)
        if step is None:
            continue
        param = next(
            (p for p in step.parameters if p.name == ans.param_name),
            None,
        )
        if param is None:
            continue
        param.value = from_decoded(param.param_type, ans.value)
        param.status = ParamStatus.USER_SET
    answered_keys = {(a.step_id, a.param_name) for a in answers}
    for q in plan.questions:
        if q.related_step is None or q.related_param is None:
            continue
        key = (q.related_step, q.related_param)
        if key in answered_keys:
            value = next(a.value for a in answers if (a.step_id, a.param_name) == key)
            q.answer = value


def assert_no_unresolved_slots(plan: StrategyPlan) -> None:
    """Raise ``ModelRetry`` if any param is still NEEDS_DISCOVERY/NEEDS_USER_INPUT.

    Distinct from ``plan_to_spec._refuse_if_unresolved_slots`` which
    raises ``PlanTopologyError``: that one is the deterministic-build
    guard, this one is the agent-loop guard (the LLM gets the message
    back as a retry).
    """
    blocking: list[tuple[str, str, ParamStatus]] = [
        (step.id, p.name, p.status)
        for step in plan.steps
        for p in step.parameters
        if p.status in (ParamStatus.NEEDS_DISCOVERY, ParamStatus.NEEDS_USER_INPUT)
    ]
    if not blocking:
        return
    summary = ", ".join(
        f"{sid}.{pname}={status.value}" for sid, pname, status in blocking
    )
    msg = (
        f"UNRESOLVED_SLOTS: Plan has unresolved slots — {summary}. "
        "NEEDS_DISCOVERY: route back to discovery to enumerate vocab. "
        "NEEDS_USER_INPUT: the user did not fill the form field; "
        "rephrase the question or convert to NEEDS_DISCOVERY."
    )
    raise ModelRetry(msg)


def mark_plan_approved(plan: StrategyPlan) -> None:
    plan.status = PlanStatus.APPROVED
    plan.updated_at = datetime.now(UTC)
