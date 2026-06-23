"""When the user replies to scoping's blocking questions, the frame must be
RE-SCOPED so the answer folds into the structured fields — but the frame must
SURVIVE (it is scoping's only cross-turn memory). Clearing it made scoping
amnesiac and re-ask the same questions forever (conversation 5edf9e38). So we
set a transient ``rescope_requested`` flag and keep the frame.
"""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.lead_node import _request_rescope_on_clarification_reply
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    PendingApproval,
    PipelineState,
    ProblemFrame,
)


def _state(**kwargs: object) -> PipelineState:
    base: dict[str, object] = {
        "conversation_id": uuid4(),
        "user_id": uuid4(),
        "site_id": "plasmodb",
        "mode": "strategy",
    }
    base.update(kwargs)
    return PipelineState(**base)  # type: ignore[arg-type]


def _frame_with_blocking() -> ProblemFrame:
    return ProblemFrame(
        user_goal="kinases",
        interpreted_goal="Find all Plasmodium kinases",
        organism_scope="Plasmodium falciparum 3D7",
        blocking_questions=[
            ClarificationQuestion(question="Which Plasmodium strain?"),
        ],
    )


def test_reply_to_blocking_questions_requests_rescope_and_keeps_frame() -> None:
    frame = _frame_with_blocking()
    state = _state(
        problem_frame=frame,
        user_prompt="Use ALL Plasmodium species, not just 3D7.",
    )
    _request_rescope_on_clarification_reply(state)
    assert state.rescope_requested is True
    # The frame SURVIVES so scoping keeps its memory and merges the answer.
    assert state.problem_frame is frame


def test_no_rescope_when_frame_has_no_blocking_questions() -> None:
    frame = ProblemFrame(
        user_goal="g",
        interpreted_goal="g",
        organism_scope="Plasmodium falciparum 3D7",
    )
    state = _state(problem_frame=frame, user_prompt="anything")
    _request_rescope_on_clarification_reply(state)
    assert state.rescope_requested is False
    assert state.problem_frame is frame


def test_no_rescope_when_no_user_reply() -> None:
    state = _state(problem_frame=_frame_with_blocking(), user_prompt="")
    _request_rescope_on_clarification_reply(state)
    assert state.rescope_requested is False


def test_no_rescope_during_pending_approval() -> None:
    state = _state(
        problem_frame=_frame_with_blocking(),
        user_prompt="approve",
        pending_approval=PendingApproval(
            phase="lead",
            tool_call_id="c1",
            tool_name="submit_plan_for_approval",
            tool_args={},
        ),
    )
    _request_rescope_on_clarification_reply(state)
    assert state.rescope_requested is False


def test_flag_is_reset_when_condition_no_longer_holds() -> None:
    # A stale True flag from a prior turn must be cleared when this turn has
    # nothing to re-scope (no blocking questions).
    state = _state(
        problem_frame=ProblemFrame(user_goal="g", interpreted_goal="g"),
        user_prompt="hi",
        rescope_requested=True,
    )
    _request_rescope_on_clarification_reply(state)
    assert state.rescope_requested is False
