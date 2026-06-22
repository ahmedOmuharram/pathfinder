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
    """A search whose required params are already resolved (param_vocab set) —
    the precondition for selection after the resolver guard."""
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
    """A search inspected but whose required params are NOT yet resolved."""
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
    """Discovery must `get_search_overview` first; the decision tool now
    raises ``ModelRetry`` so pydantic-ai threads the message back into the
    same step (the model self-corrects without burning a turn)."""
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
    """When other searches HAVE been inspected, the retry message must
    list them so the model can pick the right one — the model can copy
    a name verbatim from the message instead of guessing again."""
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
            search_name="GenesByGOTerm",  # close to GenesByGoTerm
            selection_status="selected",
            rationale="anchor",
        )
    msg = str(excinfo.value)
    assert "GenesByGOTerm" in msg
    # Did-you-mean suggestion list must include the close match.
    assert "GenesByGoTerm" in msg
    # Full valid set is exposed so the model has the complete vocabulary.
    assert "GenesByText" in msg


@pytest.mark.asyncio
async def test_invalid_confidence_raises_modelretry_with_bounds() -> None:
    """Confidence is a 0..1 probability. The retry message must spell out
    the valid range so the model picks a value in-bounds on the next try."""
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
    """Selecting a search whose required params have no vocab snapshot is
    refused — planning would otherwise guess the values (the go_term_evidence
    thrash). The retry message names the param and points to the resolver."""
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
    assert "resolve_search_parameters" in msg


@pytest.mark.asyncio
async def test_select_allowed_once_required_params_resolved() -> None:
    """With every required param snapshotted, selection proceeds normally."""
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
    """The guard only gates ``selected`` — candidate/rejected are bookkeeping
    that must work even on unresolved searches."""
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
    """A targeted-re-discovery replacement: selecting GenesByGoTerm with
    replaces=GenesByInterproDomain records the link and auto-rejects the old
    search, so deterministic reconciliation can swap the plan leaf."""
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


@pytest.mark.asyncio
async def test_deciding_marks_search_decided_and_hides_from_catalog() -> None:
    """A recorded decision flips ``decided`` so the search is filtered out
    of the search catalog and won't resurface — this is what stops the
    discovery loop of re-evaluating the same search repeatedly."""
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
    """Calling the decision tool again with the SAME status on an
    already-decided search returns an 'already decided' notice and does
    NOT overwrite the stored decision — the model is told to move on."""
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
    # No overwrite: the first verdict's fields are intact.
    assert stored.rationale == "first verdict"
    assert stored.selection_reason == "primary anchor"
    assert stored.confidence == 0.9


@pytest.mark.asyncio
async def test_redeciding_different_status_still_updates() -> None:
    """Changing the verdict (e.g. selected → rejected) on a decided search
    is a legitimate revision and must still apply."""
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
