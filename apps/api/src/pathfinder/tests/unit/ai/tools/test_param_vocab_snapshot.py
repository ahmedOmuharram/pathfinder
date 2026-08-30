"""``get_parameter_options`` writes the parameter vocabulary into the agent
state, so planning copies values verbatim instead of guessing them."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import (
    AgentToolState,
    ParamVocabSnapshot,
    SearchOverview,
)
from pathfinder.ai.agents.strategy_instructions import pinned_discovered_searches
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog import search_inspection
from pathfinder.services.catalog.param_formatting import ParameterInfo


def _ctx_with_state(state: AgentToolState) -> Any:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = state
    return ctx


def _wdk_param(name: str) -> Any:
    p = MagicMock()
    p.name = name
    p.dependent_params = []
    return p


def _patch_resolve_and_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    param_names: list[str],
) -> None:
    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return "transcript"

    monkeypatch.setattr(search_inspection, "resolve_search_record_type", _resolve)

    fake_details = MagicMock()
    fake_details.search_data.parameters = [_wdk_param(n) for n in param_names]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=fake_details)

    def _get_client(_site_id: str) -> Any:
        return client

    monkeypatch.setattr(search_inspection, "get_wdk_client", _get_client)


def _registered_search(name: str) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description="",
        parameter_names=["hard_floor"],
        required_params=["hard_floor"],
    )


@pytest.mark.asyncio
async def test_get_parameter_options_writes_param_vocab_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parameter read populates param_vocab with the ParameterInfo fields."""
    state = AgentToolState()
    state.register_search("RNASeqHardFloor", _registered_search("RNASeqHardFloor"))

    _patch_resolve_and_client(monkeypatch, param_names=["hard_floor"])

    fake_info = ParameterInfo(
        name="hard_floor",
        display_name="Hard Floor",
        type="number-enum",
        required=True,
        is_visible=True,
        help="Tier-quantile floor",
        value_format='{"type": "single-pick-vocabulary", "value": "<one of allowed_values>"}',
        default_value="6772.93",
        allowed_values=[
            VocabOption(value="1693.23", display="1693 reads"),
            VocabOption(value="3386.46", display="3386 reads"),
            VocabOption(value="6772.93", display="6772 reads"),
        ],
    )
    monkeypatch.setattr(
        search_inspection,
        "format_typed_param",
        lambda *args, **kw: fake_info,
    )

    result = (
        await catalog_discovery.get_parameter_options(
            _ctx_with_state(state),
            search_name="RNASeqHardFloor",
            parameter_id="hard_floor",
        )
    ).return_value
    assert result is fake_info

    overview = state.get_overview("RNASeqHardFloor")
    assert overview is not None
    assert "hard_floor" in overview.param_vocab
    snap = overview.param_vocab["hard_floor"]
    assert snap.param_type == "number-enum"
    assert snap.required is True
    assert snap.help == "Tier-quantile floor"
    assert snap.default_value == "6772.93"
    assert snap.allowed_values is not None
    values = [v.value for v in snap.allowed_values]
    assert values == ["1693.23", "3386.46", "6772.93"]


@pytest.mark.asyncio
async def test_param_vocab_snapshot_accumulates_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading a second parameter keeps the first parameter's snapshot."""
    state = AgentToolState()
    state.register_search(
        "FoldChange",
        SearchOverview(
            search_name="FoldChange",
            display_name="FoldChange",
            record_type="transcript",
            description="",
            parameter_names=["hard_floor", "fold_change"],
            required_params=["hard_floor"],
        ),
    )

    _patch_resolve_and_client(monkeypatch, param_names=["hard_floor", "fold_change"])

    info_for: dict[str, ParameterInfo] = {
        "hard_floor": ParameterInfo(
            name="hard_floor",
            display_name="Hard Floor",
            type="number-enum",
            required=True,
            is_visible=True,
            help="",
            value_format='{"type": "single-pick-vocabulary", "value": "<one of allowed_values>"}',
            default_value="6772.93",
            allowed_values=[VocabOption(value="6772.93", display="6772 reads")],
        ),
        "fold_change": ParameterInfo(
            name="fold_change",
            display_name="Fold change",
            type="number",
            required=False,
            is_visible=True,
            help="",
            value_format='{"type": "number", "value": <number>}',
            default_value="2",
        ),
    }

    def _format(filtered_param: Any, **_kwargs: Any) -> ParameterInfo:
        return info_for[filtered_param.name]

    monkeypatch.setattr(search_inspection, "format_typed_param", _format)

    ctx = _ctx_with_state(state)
    await catalog_discovery.get_parameter_options(
        ctx,
        search_name="FoldChange",
        parameter_id="hard_floor",
    )
    await catalog_discovery.get_parameter_options(
        ctx,
        search_name="FoldChange",
        parameter_id="fold_change",
    )
    overview = state.get_overview("FoldChange")
    assert overview is not None
    assert set(overview.param_vocab) == {"hard_floor", "fold_change"}


def test_pinned_discovered_searches_renders_param_vocab() -> None:
    """The pinned instruction renders the snapshot values and help text."""
    state = AgentToolState()
    overview = SearchOverview(
        search_name="GenesByRNASeqFoldChange",
        display_name="RNA-Seq Fold Change",
        record_type="transcript",
        description="",
        parameter_names=["hard_floor"],
        required_params=["hard_floor"],
        selection_status="selected",
        rationale="primary fold-change anchor",
        confidence=0.9,
    )
    overview = overview.model_copy(
        update={
            "param_vocab": {
                "hard_floor": ParamVocabSnapshot(
                    param_type="number-enum",
                    required=True,
                    help="Tier-quantile floor for read counts",
                    default_value="6772.93",
                    allowed_values=[
                        VocabOption(value="1693.23", display="1693 reads"),
                        VocabOption(value="6772.93", display="6772 reads"),
                    ],
                ),
            },
        },
    )
    state.register_search(overview.search_name, overview)

    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps = MagicMock()
    ctx.deps.agent_state = state
    rendered = pinned_discovered_searches(ctx)
    assert rendered is not None
    assert "param_vocab" in rendered
    assert "hard_floor" in rendered
    assert "1693.23" in rendered
    assert "6772.93" in rendered
    assert "Tier-quantile floor for read counts" in rendered


def test_pinned_discovered_searches_omits_vocab_for_rejected() -> None:
    """A rejected search renders its name and reason, but not its vocabulary."""
    state = AgentToolState()
    overview = SearchOverview(
        search_name="GenesByRNASeqGametocytesOnly",
        display_name="Gametocyte-only RNA-Seq",
        record_type="transcript",
        description="",
        parameter_names=["hard_floor"],
        required_params=["hard_floor"],
        selection_status="rejected",
        rationale="gametocyte-only dataset",
        selection_reason="sample vocab missing asexual blood stages",
    )
    overview = overview.model_copy(
        update={
            "param_vocab": {
                "hard_floor": ParamVocabSnapshot(
                    param_type="number-enum",
                    required=True,
                    help="Tier-quantile floor",
                    default_value="6772.93",
                    allowed_values=[VocabOption(value="6772.93", display="6772 reads")],
                ),
            },
        },
    )
    state.register_search(overview.search_name, overview)

    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps = MagicMock()
    ctx.deps.agent_state = state
    rendered = pinned_discovered_searches(ctx)
    assert rendered is not None
    assert "GenesByRNASeqGametocytesOnly" in rendered
    assert "sample vocab missing asexual blood stages" in rendered
    assert "param_vocab" not in rendered
    assert "6772.93" not in rendered
