"""The prose that says something was preserved reads the computed diff.

A "the rest is unchanged" sentence written from the model's memory was wrong on
a measured run while the strategy on screen said otherwise.
"""

from __future__ import annotations

from pathfinder.ai.agents.frame import _FRAME_INSTRUCTIONS
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS


def _normalized(text: str) -> str:
    return " ".join(text.split())


def test_the_lead_writes_a_preservation_claim_from_the_ledger_diff() -> None:
    assert "ledger.frame.diff" in LEAD_INSTRUCTIONS
    assert "preserved" in LEAD_INSTRUCTIONS


def test_frame_states_a_disposition_for_every_criterion_already_there() -> None:
    normalized = _normalized(_FRAME_INSTRUCTIONS)
    assert "changes" in normalized
    assert "kept" in normalized
    assert "dropped" in normalized


def test_frame_is_told_not_to_re_bind_an_untouched_criterion() -> None:
    normalized = _normalized(_FRAME_INSTRUCTIONS)
    assert "does not mention is kept" in normalized
    assert "must not be re-bound" in normalized
