"""The guidance that keeps an imperative out of ``follow_up_question``.

A request to run, rerun, add or create - assent to an offer included - asks
for a build. A turn that hid the building tools re-classifies instead of
telling the user to retry.
"""

from __future__ import annotations

from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.lead_agent import classify_user_intent


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_the_classifier_calls_an_imperative_a_building_intent() -> None:
    guidance = _flat(classify_user_intent.__doc__ or "")

    assert "An imperative asks for a build" in guidance
    assert "rerun" in guidance
    assert "yes, do it" in guidance
    assert "None of them is a ``follow_up_question``" in guidance


def test_the_classifier_keeps_a_retry_on_the_request_s_own_intent() -> None:
    guidance = _flat(classify_user_intent.__doc__ or "")

    assert "A retry after a failed task is the same request again" in guidance


def test_the_instructions_answer_a_missing_building_tool_with_a_reclassify() -> None:
    instructions = _flat(LEAD_INSTRUCTIONS)

    assert "A missing building tool is a misclassification" in instructions
    assert "your FIRST action is ``classify_user_intent`` again" in instructions


def test_the_instructions_forbid_telling_the_user_a_tool_is_unavailable() -> None:
    instructions = _flat(LEAD_INSTRUCTIONS)

    assert "NEVER tell the user that a tool is unavailable this turn" in instructions
    assert "never ask them to retry the request" in instructions


def test_the_guidance_is_ascii_only() -> None:
    assert LEAD_INSTRUCTIONS.isascii()
    assert (classify_user_intent.__doc__ or "").isascii()
