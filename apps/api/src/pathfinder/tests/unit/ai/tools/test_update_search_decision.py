"""Tests for the update_search_decision discovery tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents._instructions import pinned_discovered_searches
from pathfinder.ai.agents.state import (
    AgentToolState,
    ParamVocabSnapshot,
    SearchOverview,
)
from pathfinder.ai.tools.standalone.catalog_selection import (
    update_search_decision,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption


def _taxon_vocab() -> dict[str, ParamVocabSnapshot]:
    return {
        "taxon": ParamVocabSnapshot(
            param_type="multi-pick-vocabulary",
            required=True,
            help="organisms",
            allowed_values=[VocabOption(value="Plasmodium", display="Plasmodium")],
        ),
    }


def _seed_overview(name: str, record_type: str = "transcript") -> SearchOverview:
    """A search whose required params are resolved, which selection requires."""
    return SearchOverview(
        search_name=name,
        display_name=f"{name} display",
        record_type=record_type,
        description="seeded by get_search_overview",
        parameter_names=["taxon"],
        required_params=["taxon"],
        param_vocab=_taxon_vocab(),
    )


def _unresolved_overview(name: str) -> SearchOverview:
    """A search that is inspected but whose required params are unresolved."""
    return SearchOverview(
        search_name=name,
        display_name=f"{name} display",
        record_type="transcript",
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
async def test_unknown_search_with_no_discoveries_yet_raises_modelretry() -> None:
    """An undiscovered search raises ModelRetry that names the overview tool."""
    ctx = _ctx_with({})
    with pytest.raises(ModelRetry) as excinfo:
        await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor for kinase activity filter",
        )
    msg = str(excinfo.value)
    assert "GenesByGoTerm" in msg
    assert "get_search_overview" in msg


@pytest.mark.asyncio
async def test_unknown_search_with_other_discoveries_includes_did_you_mean() -> None:
    """The retry message lists the inspected searches so the model can copy a name."""
    ctx = _ctx_with(
        {
            "GenesByGoTerm": _seed_overview("GenesByGoTerm"),
            "GenesByGoTermSimilar": _seed_overview("GenesByGoTermSimilar"),
            "GenesByText": _seed_overview("GenesByText"),
        },
    )
    with pytest.raises(ModelRetry) as excinfo:
        await update_search_decision(
            ctx,
            search_name="GenesByGOTerm",
            selection_status="selected",
            rationale="anchor",
        )
    msg = str(excinfo.value)
    assert "GenesByGOTerm" in msg
    # The suggestion list holds the close match.
    assert "GenesByGoTerm" in msg
    # The full valid set is exposed.
    assert "GenesByText" in msg


@pytest.mark.asyncio
async def test_invalid_confidence_raises_modelretry_with_bounds() -> None:
    """Confidence is a probability from 0 to 1, and the retry message states the range."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    with pytest.raises(ModelRetry) as excinfo:
        await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor",
            confidence=1.5,
        )
    msg = str(excinfo.value)
    assert "0" in msg
    assert "1" in msg
    assert "1.5" in msg


@pytest.mark.asyncio
async def test_select_blocked_when_required_param_unresolved() -> None:
    """Selection is refused when a required param has no vocabulary snapshot. The
    retry message names the param and the tool that reads the search."""
    ctx = _ctx_with({"GenesByGoTerm": _unresolved_overview("GenesByGoTerm")})
    with pytest.raises(ModelRetry) as excinfo:
        await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor",
            confidence=0.9,
        )
    msg = str(excinfo.value)
    assert "taxon" in msg
    assert "get_search_overview" in msg


@pytest.mark.asyncio
async def test_select_allowed_once_required_params_resolved() -> None:
    """Selection proceeds when every required param has a snapshot."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=0.9,
    )
    assert isinstance(result, str)
    assert "selected decision for GenesByGoTerm" in result


@pytest.mark.asyncio
async def test_candidate_and_rejected_not_blocked_by_resolver_guard() -> None:
    """The guard gates only the selected status. Candidate and rejected always apply."""
    for status in ("candidate", "rejected"):
        ctx = _ctx_with({"GenesByGoTerm": _unresolved_overview("GenesByGoTerm")})
        result = await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status=status,  # type: ignore[arg-type]
            rationale="bookkeeping",
            confidence=0.4,
        )
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_select_with_replaces_records_link_and_rejects_old() -> None:
    """A replacement records the link and rejects the replaced search."""
    ctx = _ctx_with(
        {
            "GenesByGoTerm": _seed_overview("GenesByGoTerm"),
            "GenesByInterproDomain": _seed_overview("GenesByInterproDomain"),
        },
    )
    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=0.9,
        replaces="GenesByInterproDomain",
    )
    state = ctx.deps.agent_state
    go = state.get_overview("GenesByGoTerm")
    assert go is not None
    assert go.replaces == "GenesByInterproDomain"
    old = state.get_overview("GenesByInterproDomain")
    assert old is not None
    assert old.selection_status == "rejected"


@pytest.mark.asyncio
async def test_replaces_unknown_search_raises_modelretry() -> None:
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    with pytest.raises(ModelRetry) as excinfo:
        await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor",
            confidence=0.9,
            replaces="GenesByNeverInspected",
        )
    assert "GenesByNeverInspected" in str(excinfo.value)


@pytest.mark.asyncio
async def test_replaces_self_raises_modelretry() -> None:
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    with pytest.raises(ModelRetry):
        await update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor",
            confidence=0.9,
            replaces="GenesByGoTerm",
        )


@pytest.mark.asyncio
async def test_commits_selected_decision_with_full_metadata() -> None:
    """A selected decision stores every field, and the pinned render shows them."""
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
    # The update keeps the other seeded fields.
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
    """A rejected decision stays in state with its status and reason."""
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
    """The latest call wins and replaces the previous fields."""
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
    # The earlier rationale is fully replaced.
    assert "initial pass" not in stored.rationale


@pytest.mark.asyncio
async def test_deciding_marks_search_decided_and_hides_from_catalog() -> None:
    """A recorded decision sets decided, which hides the search from the catalog."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    state = ctx.deps.agent_state
    assert state.decided_search_names() == set()

    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=0.9,
    )
    stored = state.get_overview("GenesByGoTerm")
    assert stored is not None
    assert stored.decided is True
    assert state.decided_search_names() == {"GenesByGoTerm"}


@pytest.mark.asyncio
async def test_redeciding_same_status_is_a_no_op() -> None:
    """A repeated status on a decided search returns a notice and keeps the decision."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="first verdict",
        selection_reason="primary anchor",
        confidence=0.9,
    )
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="second time around",
        selection_reason="changed my mind text",
        confidence=0.3,
    )
    assert isinstance(result, str)
    assert "already decided" in result.lower()

    stored = ctx.deps.agent_state.get_overview("GenesByGoTerm")
    assert stored is not None
    # The first verdict's fields stay intact.
    assert stored.rationale == "first verdict"
    assert stored.selection_reason == "primary anchor"
    assert stored.confidence == 0.9


@pytest.mark.asyncio
async def test_redeciding_different_status_still_updates() -> None:
    """A changed status on a decided search still applies."""
    ctx = _ctx_with({"GenesByGoTerm": _seed_overview("GenesByGoTerm")})
    await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=0.9,
    )
    result = await update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="rejected",
        rationale="actually a dead end",
        confidence=0.2,
    )
    assert "already decided" not in result.lower()
    stored = ctx.deps.agent_state.get_overview("GenesByGoTerm")
    assert stored is not None
    assert stored.selection_status == "rejected"
    assert stored.confidence == 0.2
