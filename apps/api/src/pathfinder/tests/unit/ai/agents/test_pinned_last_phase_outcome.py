from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from pathfinder.ai.agents._instructions import (
    pinned_discovered_searches,
    pinned_last_phase_outcome,
)
from pathfinder.ai.agents.state import (
    AgentToolState,
    SearchOverview,
    SearchSelectionStatus,
)
from pathfinder.ai.graph.state import PhaseDisposition, PhaseOutcome


def _ctx(
    *,
    last_phase_outcome: PhaseOutcome | None = None,
    last_phase_name: str | None = None,
    discovered: dict[str, SearchOverview] | None = None,
) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.last_phase_outcome = last_phase_outcome
    ctx.deps.last_phase_name = last_phase_name
    state = AgentToolState()
    if discovered:
        state.discovered_searches.update(discovered)
    ctx.deps.agent_state = state
    return ctx


# ---- pinned_last_phase_outcome ----


def test_outcome_returns_none_when_no_prior_phase() -> None:
    assert pinned_last_phase_outcome(_ctx()) is None


def test_outcome_renders_handoff_with_target() -> None:
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            "Discovered 3 candidate searches for Plasmodium kinase activity: "
            "GenesByGoTerm (the primary anchor), GenesByMicroarray (for "
            "stage filtering), and GenesByTransmembrane (for membrane filter)."
        ),
        reason="ready to plan",
        handoff_to="planning",
        note_refs=["note_abc1", "note_abc2"],
    )
    rendered = pinned_last_phase_outcome(
        _ctx(last_phase_outcome=outcome, last_phase_name="discovery"),
    )
    assert rendered is not None
    assert "Previous phase (discovery)" in rendered
    assert "handed off" in rendered
    assert "Handed off to: planning" in rendered
    assert "Reason: ready to plan" in rendered
    # The full narrative survives so the next phase doesn't need history.
    assert "GenesByGoTerm" in rendered
    assert "GenesByTransmembrane" in rendered
    # Scratchpad citations carry forward as structured refs.
    assert "note_abc1" in rendered
    assert "note_abc2" in rendered


def test_outcome_renders_awaiting_user_without_handoff_line() -> None:
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.AWAITING_USER,
        prose="Need to know whether to include unconfirmed transcripts.",
        reason="blocking question on inclusion criteria",
    )
    rendered = pinned_last_phase_outcome(
        _ctx(last_phase_outcome=outcome, last_phase_name="scoping"),
    )
    assert rendered is not None
    assert "awaiting user reply" in rendered
    assert "Handed off to:" not in rendered
    assert "Need to know whether" in rendered


def test_outcome_falls_back_to_generic_phase_name() -> None:
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.DONE,
        prose="Done.",
        reason="finished",
    )
    rendered = pinned_last_phase_outcome(
        _ctx(last_phase_outcome=outcome, last_phase_name=None),
    )
    assert rendered is not None
    assert "Previous phase (previous phase)" in rendered
    assert "ended turn" in rendered


# ---- pinned_discovered_searches ----


def _overview(
    name: str,
    *,
    rationale: str = "",
    selection_status: SearchSelectionStatus = "candidate",
    selection_reason: str = "",
    confidence: float = 0.0,
    param_hints: dict[str, str] | None = None,
) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=f"{name} display",
        record_type="transcript",
        description="d",
        parameter_names=["taxon"],
        required_params=["taxon"],
        rationale=rationale,
        selection_status=selection_status,
        selection_reason=selection_reason,
        confidence=confidence,
        param_hints=param_hints or {},
    )


def test_discovered_returns_none_when_empty() -> None:
    assert pinned_discovered_searches(_ctx()) is None


def test_discovered_renders_basic_candidate() -> None:
    rendered = pinned_discovered_searches(
        _ctx(discovered={"GenesByGoTerm": _overview("GenesByGoTerm")}),
    )
    assert rendered is not None
    assert "## Discovered searches" in rendered
    assert "`GenesByGoTerm`" in rendered
    assert "(transcript)" in rendered
    # candidate is the default — no [status] marker, no rationale lines.
    assert "[selected]" not in rendered
    assert "[rejected]" not in rendered
    assert "why:" not in rendered


def test_discovered_renders_selected_with_full_metadata() -> None:
    overview = _overview(
        "GenesByGoTerm",
        rationale="GO:0016301 is the closest term to 'kinase activity'.",
        selection_status="selected",
        selection_reason="primary anchor for kinase filter",
        confidence=0.92,
        param_hints={"taxon": "Plasmodium", "go_term": "GO:0016301"},
    )
    rendered = pinned_discovered_searches(
        _ctx(discovered={"GenesByGoTerm": overview}),
    )
    assert rendered is not None
    assert "[selected]" in rendered
    assert "conf=0.92" in rendered
    assert "GO:0016301 is the closest term" in rendered
    assert "primary anchor for kinase filter" in rendered
    assert "required params: taxon" in rendered
    # param_hints render alphabetically so the test is stable.
    assert "hints: go_term=GO:0016301, taxon=Plasmodium" in rendered


def test_discovered_renders_rejected_with_reason() -> None:
    rendered = pinned_discovered_searches(
        _ctx(
            discovered={
                "GenesByMicroarray": _overview(
                    "GenesByMicroarray",
                    selection_status="rejected",
                    selection_reason="user wants RNA-seq data, not microarray",
                    confidence=0.1,
                ),
            },
        ),
    )
    assert rendered is not None
    assert "[rejected]" in rendered
    assert "user wants RNA-seq data" in rendered
    # Confirms rejected candidates persist so planning doesn't re-discover.
    assert "GenesByMicroarray" in rendered


def test_discovered_renders_multiple_searches_in_sorted_order() -> None:
    rendered = pinned_discovered_searches(
        _ctx(
            discovered={
                "ZSearch": _overview("ZSearch"),
                "ASearch": _overview("ASearch"),
                "MSearch": _overview("MSearch"),
            },
        ),
    )
    assert rendered is not None
    # Sorted alphabetically — deterministic so the agent sees stable ordering
    # across runs (otherwise dict insertion order changes the prompt every turn).
    a_idx = rendered.index("`ASearch`")
    m_idx = rendered.index("`MSearch`")
    z_idx = rendered.index("`ZSearch`")
    assert a_idx < m_idx < z_idx
