"""Tests for standalone catalog tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.catalog import (
    get_record_types,
    list_searches,
    search_for_searches,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.catalog.models import RecordTypeInfo, SearchMatch


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.catalog.catalog.get_record_types",
    new_callable=AsyncMock,
)
async def test_get_record_types_returns_site_record_types(
    mock_get_rt: AsyncMock,
) -> None:
    mock_get_rt.return_value = [
        RecordTypeInfo(
            name="transcript",
            display_name="Genes",
            description="Gene/transcript records",
        ),
        RecordTypeInfo(
            name="isolate",
            display_name="Isolates",
            description="Population isolate records",
        ),
    ]
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await get_record_types(ctx)

    assert len(result) == 2
    assert result[0]["name"] == "transcript"
    assert result[0]["displayName"] == "Genes"
    assert result[0]["description"] == "Gene/transcript records"
    assert result[1]["name"] == "isolate"
    assert result[1]["displayName"] == "Isolates"
    mock_get_rt.assert_awaited_once_with("plasmodb")


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.catalog.catalog.search_for_searches",
    new_callable=AsyncMock,
)
async def test_search_for_searches_returns_matches_with_universal(
    mock_search: AsyncMock,
) -> None:
    mock_search.return_value = [
        SearchMatch(
            name="GenesByTaxon",
            display_name="Genes by Taxon",
            description="Find genes by organism taxonomy",
            record_type="transcript",
            category="general",
            returns="transcript",
            relevance=0.85,
        ),
    ]
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await search_for_searches(
        ctx,
        query="find genes by organism taxonomy plasmodium falciparum",
    )

    # Should include the matched search plus universal searches
    names = [str(r["name"]) for r in result]
    assert "GenesByTaxon" in names
    assert "GenesByText" in names  # universal search appended

    taxon_result = next(r for r in result if r["name"] == "GenesByTaxon")
    assert taxon_result["displayName"] == "Genes by Taxon"
    assert taxon_result["relevance"] == 0.85
    assert taxon_result["recordType"] == "transcript"


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.catalog.catalog.search_for_searches",
    new_callable=AsyncMock,
)
async def test_search_for_searches_hides_already_decided(
    mock_search: AsyncMock,
) -> None:
    """A search the model has already recorded a decision on must be
    filtered out of the catalog so it can't resurface and trigger another
    round of evaluation — with a note flagging how many were hidden."""
    mock_search.return_value = [
        SearchMatch(
            name="GenesByTaxon",
            display_name="Genes by Taxon",
            description="Find genes by organism taxonomy",
            record_type="transcript",
            category="general",
            returns="transcript",
            relevance=0.85,
        ),
        SearchMatch(
            name="GenesByGoTerm",
            display_name="Genes by GO Term",
            description="Find genes by GO term",
            record_type="transcript",
            category="general",
            returns="transcript",
            relevance=0.8,
        ),
    ]
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="decided already",
            parameter_names=["taxon"],
            required_params=["taxon"],
            selection_status="selected",
            decided=True,
        ),
    )
    ctx = _make_ctx(deps)

    result = await search_for_searches(
        ctx,
        query="find genes by organism taxonomy or go term plasmodium",
    )

    names = [str(r.get("name")) for r in result]
    assert "GenesByTaxon" not in names  # decided → hidden
    assert "GenesByGoTerm" in names  # undecided → still shown

    notes = [str(r["note"]) for r in result if "note" in r]
    assert len(notes) == 1
    assert "GenesByTaxon" in notes[0]


@pytest.mark.asyncio
async def test_search_for_searches_rejects_vague_query() -> None:
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await search_for_searches(ctx, query="genes")

    assert len(result) == 1
    assert result[0]["error"] == "query_too_vague"


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.catalog.catalog.list_searches",
    new_callable=AsyncMock,
)
async def test_list_searches_for_record_type(
    mock_list: AsyncMock,
) -> None:
    mock_list.return_value = [
        {"name": "GenesByTaxon", "displayName": "Genes by Taxon"},
        {"name": "GenesByLocation", "displayName": "Genes by Genomic Location"},
        {"name": "GenesByText", "displayName": "Gene Text Search"},
    ]
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await list_searches(ctx, record_type="transcript")

    assert len(result) == 3
    assert result[0]["name"] == "GenesByTaxon"
    assert result[2]["name"] == "GenesByText"
    mock_list.assert_awaited_once_with("plasmodb", "transcript")


@pytest.mark.asyncio
@patch(
    "pathfinder.ai.tools.standalone.catalog.catalog.list_searches",
    new_callable=AsyncMock,
)
async def test_list_searches_hides_already_decided(
    mock_list: AsyncMock,
) -> None:
    """Decided searches are also stripped from the names-only fallback so
    they can't resurface through any catalog path."""
    mock_list.return_value = [
        {"name": "GenesByTaxon", "displayName": "Genes by Taxon"},
        {"name": "GenesByText", "displayName": "Gene Text Search"},
    ]
    deps = _make_deps()
    deps.agent_state.register_search(
        "GenesByTaxon",
        SearchOverview(
            search_name="GenesByTaxon",
            display_name="Genes by Taxon",
            record_type="transcript",
            description="decided already",
            parameter_names=["taxon"],
            required_params=["taxon"],
            selection_status="rejected",
            decided=True,
        ),
    )
    ctx = _make_ctx(deps)

    result = await list_searches(ctx, record_type="transcript")

    names = [r["name"] for r in result]
    assert names == ["GenesByText"]
