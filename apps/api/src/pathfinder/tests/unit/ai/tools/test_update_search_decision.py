"""Direct tests for the ``update_search_decision`` discovery tool.

These hit the real tool function with a synthesized ``RunContext`` so the
test exercises the actual mutation path that pydantic-ai will execute when
the discovery agent calls it. We assert on the resulting ``SearchOverview``
fields and the rendered ``pinned_discovered_searches`` string — i.e. what
downstream phases will actually see.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents._instructions import pinned_discovered_searches
from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.tools.standalone.catalog_discovery import (
    update_search_decision,
)
from pathfinder.platform.tool_errors import ToolErrorPayload


def _seed_overview(name: str, record_type: str = "transcript") -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=f"{name} display",
        record_type=record_type,
        description="seeded by get_search_overview",
        parameter_names=["taxon"],
        required_params=["taxon"],
    )


def _ctx_with(overviews: dict[str, SearchOverview]) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    state = AgentToolState()
    state.discovered_searches.update(overviews)
    ctx.deps.agent_state = state
    return ctx


@pytest.mark.asyncio
async def test_rejects_unknown_search() -> None:
    """Discovery must `get_search_overview` first; the decision tool fails
    loudly if it's called for a search the agent never inspected — that's
    the only contract that prevents discovered_searches from being filled
    with hallucinated names."""
    ctx = _ctx_with({})
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor for kinase activity filter",
    )
    assert isinstance(result, ToolErrorPayload)
    assert result.code == "SEARCH_NOT_DISCOVERED"
    assert "get_search_overview" in result.message


@pytest.mark.asyncio
async def test_rejects_invalid_confidence() -> None:
    """Confidence is a 0..1 probability; out-of-range values are caller bugs
    and must surface as tool errors, not silently clamp."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=1.5,
    )
    assert isinstance(result, ToolErrorPayload)
    assert result.code == "INVALID_CONFIDENCE"


@pytest.mark.asyncio
async def test_commits_selected_decision_with_full_metadata() -> None:
    """The happy path: discovery commits ``selected`` with full reasoning,
    and the SearchOverview in agent_state reflects every field. The
    pinned_discovered_searches render must surface those fields verbatim
    so the planner can read discovery's verdict without any tool history."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="GO:0016301 is the closest term to kinase activity",
        selection_reason="primary anchor for kinase filter",
        confidence=0.92,
        param_hints={"taxon": "Plasmodium", "go_term": "GO:0016301"},
    )
    assert isinstance(result, str)
    assert "selected decision for GenesByGoTerm" in result
    assert "0.92" in result

    stored = ctx.deps.agent_state.get_overview("GenesByGoTerm")
    assert stored is not None
    assert stored.selection_status == "selected"
    assert stored.rationale == "GO:0016301 is the closest term to kinase activity"
    assert stored.selection_reason == "primary anchor for kinase filter"
    assert stored.confidence == 0.92
    assert stored.param_hints == {"taxon": "Plasmodium", "go_term": "GO:0016301"}
    # Other fields preserved from the seed overview (no destructive update).
    assert stored.parameter_names == ["taxon"]
    assert stored.record_type == "transcript"

    rendered = pinned_discovered_searches(ctx)
    assert rendered is not None
    assert "[selected]" in rendered
    assert "conf=0.92" in rendered
    assert "GO:0016301 is the closest term" in rendered
    assert "primary anchor for kinase filter" in rendered
    assert "go_term=GO:0016301, taxon=Plasmodium" in rendered


@pytest.mark.asyncio
async def test_commits_rejected_decision_persists_for_planning() -> None:
    """Recording rejected candidates is the whole point — keeps planning
    from re-discovering the same dead ends. The overview must remain in
    agent_state with status=rejected and the reason."""
    ctx = _ctx_with({"GenesByMicroarray": _seed_overview("GenesByMicroarray")})
    result = await update_search_decision(
        ctx,
        search_name="GenesByMicroarray",
        selection_status="rejected",
        rationale="microarray expression search",
        selection_reason="user wants RNA-seq, not microarray",
        confidence=0.1,
    )
    assert isinstance(result, str)

    stored = ctx.deps.agent_state.get_overview("GenesByMicroarray")
    assert stored is not None
    assert stored.selection_status == "rejected"
    assert "user wants RNA-seq" in stored.selection_reason

    rendered = pinned_discovered_searches(ctx)
    assert rendered is not None
    assert "[rejected]" in rendered
    assert "GenesByMicroarray" in rendered
    assert "user wants RNA-seq" in rendered


@pytest.mark.asyncio
async def test_decision_can_be_revised() -> None:
    """An agent may downgrade or upgrade a search after seeing more
    evidence. The latest call wins; previous fields are fully replaced
    so planning never sees stale rationale fragments."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="candidate",
        rationale="initial pass — looks plausible",
        confidence=0.5,
    )
    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="confirmed: GO:0016301 hits 142 Plasmodium kinases",
        selection_reason="best anchor after vocab inspection",
        confidence=0.95,
    )
    stored = ctx.deps.agent_state.get_overview("GenesByGoTerm")
    assert stored is not None
    assert stored.selection_status == "selected"
    assert stored.confidence == 0.95
    assert "confirmed: GO:0016301" in stored.rationale
    assert "best anchor" in stored.selection_reason
    # The earlier rationale is fully replaced — no stale fragments leak.
    assert "initial pass" not in stored.rationale
