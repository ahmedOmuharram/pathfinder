from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import PlanSlotAnswer, UserQuestionAnswer
from pathfinder.devtools.gates import (
    BodyCtx,
    approval_body,
    consult_body,
    detect_gate,
    plan_slots_body,
)

_CTX = BodyCtx(conversation_id=uuid4(), site_id="vectorbase", mode="strategy")


def test_detect_none_when_no_pending() -> None:
    gate = detect_gate(
        pending_approval=None, tool_args={}, plan_open_slots=[], durable_task=None
    )
    assert gate.kind == "none"


def test_detect_generic_approval() -> None:
    gate = detect_gate(
        pending_approval=("delete_step", "c1"),
        tool_args={},
        plan_open_slots=[],
        durable_task=None,
    )
    assert gate.kind == "approval"
    assert gate.tool == "delete_step"
    assert gate.tool_call_id == "c1"


def test_detect_consult_parses_questions() -> None:
    gate = detect_gate(
        pending_approval=("consult_user", "c2"),
        tool_args={
            "c2": {
                "questions": [
                    {
                        "id": "strain",
                        "prompt": "Which strain?",
                        "kind": "single_choice",
                        "options": [
                            {"label": "Liverpool", "recommended": True},
                            {"label": "Rockefeller"},
                        ],
                    }
                ]
            }
        },
        plan_open_slots=[],
        durable_task=None,
    )
    assert gate.kind == "consult"
    assert gate.tool_call_id == "c2"
    assert gate.consult_questions[0].id == "strain"
    assert gate.consult_questions[0].options[0].label == "Liverpool"
    assert gate.consult_questions[0].options[0].recommended is True


def test_detect_submit_plan_with_slots() -> None:
    gate = detect_gate(
        pending_approval=("submit_plan_for_approval", "c3"),
        tool_args={},
        plan_open_slots=[
            {"stepId": "s1", "paramName": "organism", "question": "Which organism?"}
        ],
        durable_task=None,
    )
    assert gate.kind == "approval"
    assert gate.tool == "submit_plan_for_approval"
    assert gate.plan_slots[0].step_id == "s1"
    assert gate.plan_slots[0].param_name == "organism"


def test_detect_durable_task() -> None:
    gate = detect_gate(
        pending_approval=None,
        tool_args={},
        plan_open_slots=[],
        durable_task=("task-123", "geneset_enrichment"),
    )
    assert gate.kind == "durable"
    assert gate.task_id == "task-123"
    assert gate.task_tool == "geneset_enrichment"


def test_approval_body_builds_responded_part() -> None:
    body = approval_body(
        _CTX,
        message_id=uuid4(),
        tool="delete_step",
        tool_call_id="c1",
        approved=False,
        reason="not now",
    )
    msg = body.messages[0]
    assert msg.role == "assistant"
    part = msg.parts[0]
    assert part.type == "tool-delete_step"
    assert part.approval.approved is False
    assert part.approval.reason == "not now"


def test_consult_body_has_approval_and_answers() -> None:
    answers = [
        UserQuestionAnswer(
            question_id="strain", prompt="Which strain?", chosen_labels=["Liverpool"]
        )
    ]
    body = consult_body(_CTX, message_id=uuid4(), tool_call_id="c2", answers=answers)
    types = [p.type for p in body.messages[0].parts]
    assert "tool-consult_user" in types
    assert "data-user-question-answers" in types
    data_part = next(
        p for p in body.messages[0].parts if p.type == "data-user-question-answers"
    )
    assert data_part.data["toolCallId"] == "c2"
    assert data_part.data["answers"][0]["chosenLabels"] == ["Liverpool"]


def test_plan_slots_body_has_approval_and_answers() -> None:
    answers = [
        PlanSlotAnswer(step_id="s1", param_name="organism", value="Aedes aegypti")
    ]
    body = plan_slots_body(
        _CTX,
        message_id=uuid4(),
        tool="submit_plan_for_approval",
        tool_call_id="c3",
        approved=True,
        answers=answers,
    )
    types = [p.type for p in body.messages[0].parts]
    assert "tool-submit_plan_for_approval" in types
    assert "data-plan-slot-answers" in types
    data_part = next(
        p for p in body.messages[0].parts if p.type == "data-plan-slot-answers"
    )
    assert data_part.data["answers"][0]["stepId"] == "s1"
