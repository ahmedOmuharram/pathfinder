"""Tests for the ``get_parameter_options`` did-you-mean return path.

The unit under test: when the model passes a parameter_id that doesn't
exist on the search, the tool must return a ``ParameterNotOnSearch``
result (NOT raise ``ModelRetry``) carrying (a) the closest matching
valid names and (b) the full set of valid names. Returning instead of
raising preserves retry budget — the model self-corrects on its next
call from the typed payload.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.ai.tools.standalone.catalog_discovery import AlreadyReadNotice
from pathfinder.services.catalog.param_formatting import ParameterNotOnSearch


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = AgentToolState()
    return ctx


def _wdk_param(name: str) -> Any:
    """Minimal WDK param stub — only the fields the tool reads from
    `all_params` are surfaced (name + dependent_params)."""
    p = MagicMock()
    p.name = name
    p.dependent_params = []
    return p


def _patch_resolve_and_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    record_type: str,
    param_names: list[str],
) -> None:
    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return record_type

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)

    fake_details = MagicMock()
    fake_details.search_data.parameters = [_wdk_param(n) for n in param_names]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=fake_details)

    def _get_client(_site_id: str) -> Any:
        return client

    monkeypatch.setattr(catalog_discovery, "get_wdk_client", _get_client)


@pytest.mark.asyncio
async def test_known_parameter_returns_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: a valid parameter_id flows through to format_typed_param
    and returns a real ParameterInfo (no exception)."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["min_pct_idents", "min_overlap_size"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByESTOverlap",
        parameter_id="min_pct_idents",
    )
    assert result is fake_info


@pytest.mark.asyncio
async def test_unknown_parameter_returns_not_on_search_with_close_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Model guesses ``minOverlap`` (English-y), real WDK name is
    ``min_overlap_size``. The tool returns ``ParameterNotOnSearch``
    carrying the close match, full valid list, and search context — the
    model self-corrects on the next call without consuming retry budget."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=[
            "min_pct_idents",
            "min_overlap_size",
            "datasets",
            "expansion_factor",
        ],
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByESTOverlap",
        parameter_id="minOverlap",
    )
    assert isinstance(result, ParameterNotOnSearch)
    assert result.requested_parameter_id == "minOverlap"
    assert result.search_name == "GenesByESTOverlap"
    assert "min_overlap_size" in result.suggestions
    assert set(result.valid_parameter_ids) == {
        "min_pct_idents",
        "min_overlap_size",
        "datasets",
        "expansion_factor",
    }
    assert "minOverlap" in result.message
    assert "GenesByESTOverlap" in result.message


@pytest.mark.asyncio
async def test_no_close_match_still_lists_all_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model's guess is so far off that get_close_matches finds
    nothing, the full valid list still comes back. The model isn't left
    blind — it gets at least the universe of options."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["taxon", "go_term"],
    )
    result = await catalog_discovery.get_parameter_options(
        _ctx(),
        search_name="GenesByGoTerm",
        parameter_id="completely_unrelated_xyz",
    )
    assert isinstance(result, ParameterNotOnSearch)
    assert result.requested_parameter_id == "completely_unrelated_xyz"
    assert set(result.valid_parameter_ids) == {"taxon", "go_term"}
    assert "completely_unrelated_xyz" in result.message
    assert "taxon" in result.message
    assert "go_term" in result.message


@pytest.mark.asyncio
async def test_second_identical_read_returns_already_read_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading the same parameter's options twice in a turn is wasteful:
    the first call returns the full ParameterInfo, the second returns an
    AlreadyReadNotice telling the model it's the same as before."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["go_term", "taxon"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    ctx = _ctx()
    first = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert first is fake_info

    second = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert isinstance(second, AlreadyReadNotice)
    assert second.search_name == "GenesByGoTerm"
    assert second.parameter_id == "go_term"


@pytest.mark.asyncio
async def test_failed_read_is_not_marked_so_retry_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ParameterNotOnSearch (wrong param name) must NOT mark the read as
    done — the model should be able to fix the name and read for real."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["go_term", "taxon"],
    )
    fake_info = MagicMock()
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )
    ctx = _ctx()
    wrong = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="goTerm",  # wrong casing
    )
    assert isinstance(wrong, ParameterNotOnSearch)

    fixed = await catalog_discovery.get_parameter_options(
        ctx,
        search_name="GenesByGoTerm",
        parameter_id="go_term",
    )
    assert fixed is fake_info
