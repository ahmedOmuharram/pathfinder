"""Tests for the ``get_parameter_options`` did-you-mean retry path.

The unit under test: when the model passes a parameter_id that doesn't
exist on the search, the tool must raise ``ModelRetry`` with (a) the
closest matching valid names and (b) the full set of valid names. That
message is the model's prompt for the next request — if it doesn't
contain enough info to self-correct, we end up in a retry loop and the
fix didn't help.

These tests stub out the WDK client so they're hermetic and fast.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import catalog_discovery


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
async def test_unknown_parameter_raises_modelretry_with_close_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact bug we're fixing: model guesses ``minOverlap`` (English-y),
    real WDK name is ``min_overlap_size``. Retry message MUST surface the
    close match so the model self-corrects without another error round-trip."""
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
    with pytest.raises(ModelRetry) as excinfo:
        await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByESTOverlap",
            parameter_id="minOverlap",
        )
    msg = str(excinfo.value)
    # Bad value echoed back so the model knows what it tried.
    assert "minOverlap" in msg
    # Search context preserved so the model knows where it is.
    assert "GenesByESTOverlap" in msg
    # Did-you-mean must surface the closest WDK-name suggestion.
    assert "min_overlap_size" in msg
    # Full valid set is exposed so the model has the complete vocab —
    # the model can pick the right one without another guessing round.
    assert "min_pct_idents" in msg
    assert "datasets" in msg


@pytest.mark.asyncio
async def test_no_close_match_still_lists_all_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model's guess is so far off that get_close_matches finds
    nothing, the full valid list still appears. The model isn't left
    blind — it gets at least the universe of options."""
    _patch_resolve_and_client(
        monkeypatch,
        record_type="transcript",
        param_names=["taxon", "go_term"],
    )
    with pytest.raises(ModelRetry) as excinfo:
        await catalog_discovery.get_parameter_options(
            _ctx(),
            search_name="GenesByGoTerm",
            parameter_id="completely_unrelated_xyz",
        )
    msg = str(excinfo.value)
    assert "completely_unrelated_xyz" in msg
    assert "taxon" in msg
    assert "go_term" in msg
