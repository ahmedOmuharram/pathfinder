from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.ai.graph.state import PhaseDisposition, PhaseOutcome


def test_note_refs_defaults_empty() -> None:
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose="ok",
        reason="moving on",
    )
    assert outcome.note_refs == []


def test_note_refs_populates() -> None:
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose="ok",
        reason="moving on",
        note_refs=["n-abc123", "n-def456"],
    )
    assert outcome.note_refs == ["n-abc123", "n-def456"]


def test_note_refs_max_length_enforced() -> None:
    with pytest.raises(ValidationError):
        PhaseOutcome(
            disposition=PhaseDisposition.HANDOFF,
            prose="ok",
            reason="moving on",
            note_refs=[f"n-{i:06x}" for i in range(11)],
        )
