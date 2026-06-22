"""When the user replies to scoping's blocking clarifying questions, the frame
must be re-scoped so the answer folds into the STRUCTURED frame fields
(organism_scope, record_type, …). Otherwise discovery trusts the stale frame
default and silently ignores the user's explicit override — the conv-L bug
where 'ALL Plasmodium' was dropped in favor of the turn-1 'P. falciparum 3D7'
default because scoping never re-ran.
"""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.lead_node import _rescope_on_clarification_reply
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
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


def test_reply_to_blocking_questions_forces_rescope() -> None:
    state = _state(
        problem_frame=_frame_with_blocking(),
        user_prompt="Use ALL Plasmodium species, not just 3D7.",
    )
    _rescope_on_clarification_reply(state)
    # Frame is cleared so the Lead re-runs scoping and rebuilds organism_scope
    # from the user's answer instead of trusting the stale default.
    assert state.problem_frame is None


def test_no_rescope_when_frame_has_no_blocking_questions() -> None:
    frame = ProblemFrame(
        user_goal="g",
        interpreted_goal="g",
        organism_scope="Plasmodium falciparum 3D7",
    )
    state = _state(problem_frame=frame, user_prompt="anything")
    _rescope_on_clarification_reply(state)
    assert state.problem_frame is frame  # untouched


def test_no_rescope_when_no_user_reply() -> None:
    frame = _frame_with_blocking()
    state = _state(problem_frame=frame, user_prompt="")
    _rescope_on_clarification_reply(state)
    assert state.problem_frame is frame  # nothing to fold in
