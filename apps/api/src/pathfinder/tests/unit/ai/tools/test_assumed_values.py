"""A value FRAME chose that the request does not state is recorded, not narrated."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.ai.tools.standalone.frame_spec import set_criterion
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.operational_spec import AssumedValue
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.services.catalog import search_inspection, searches
from pathfinder.services.catalog.param_dag import ParamFetcher
from pathfinder.services.catalog.param_formatting import FilterFieldInfo, ParameterInfo
from pathfinder.services.catalog.param_validation import ValidatedParams

_SEARCH = "GenesByMicroarrayDerisi"


def _pi(
    name: str,
    param_type: str = "string",
    *,
    options: list[VocabOption] | None = None,
    filter_fields: list[FilterFieldInfo] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=None,
        vocab_leaves=options or [],
        filter_fields=filter_fields or [],
    )


_SAMPLE_WINDOWS = [
    VocabOption(value="17-30h", display="17-30 hours"),
    VocabOption(value="1-16h", display="1-16 hours"),
]
_FILTER_FIELD = FilterFieldInfo(
    term="Sample type", display="Sample type", type="string", values=["a", "b"]
)


def _params(_context: dict[str, str]) -> list[ParameterInfo]:
    return [
        _pi("min_expression_percentile"),
        _pi(
            "samples_percentile_generic",
            "single-pick-vocabulary",
            options=_SAMPLE_WINDOWS,
        ),
        _pi("ref_samples", "filter", filter_fields=[_FILTER_FIELD]),
        _pi("comp_samples", "filter", filter_fields=[_FILTER_FIELD]),
    ]


@pytest.fixture(autouse=True)
def _serve(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fetch_at(*_args: object) -> ParamFetcher:
        async def fetch_at(_context: dict[str, str]) -> list[ParameterInfo]:
            return _params({})

        return fetch_at

    monkeypatch.setattr(frame_spec, "wdk_fetch_at", _fetch_at)

    async def _details(
        record_type: str, name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        return WDKSearchResponse(
            searchData=WDKSearch(urlSegment=name),
            validation=StepValidation(level="NONE", is_valid=False),
        )

    client = MagicMock()
    client.get_search_details = _details
    client.get_search_details_with_params = _details
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(search_inspection, "get_wdk_client", lambda _site: client)

    async def _catalog_details(
        search: SearchContext, **_kw: object
    ) -> tuple[WDKSearchResponse, str]:
        return (
            WDKSearchResponse(
                searchData=WDKSearch(urlSegment=search.search_name),
                validation=StepValidation(level="NONE", is_valid=False),
            ),
            search.record_type,
        )

    monkeypatch.setattr(frame_spec, "fetch_search_details", _catalog_details)

    async def _validated(_search: object, **_kw: object) -> ValidatedParams:
        return ValidatedParams(valid=True, substituted=[])

    monkeypatch.setattr(frame_spec, "validate_parameters", _validated)


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    graph = MagicMock()
    graph.record_type = "transcript"
    ctx.deps.strategy_session.get_graph.return_value = graph
    return ctx


_TROPHOZOITE = AssumedValue(
    param_name="samples_percentile_generic",
    value="17-30h",
    reason="the request says trophozoite and this window covers 17-30 hours",
)


async def _bind(
    state: AgentToolState,
    *,
    params: dict[str, str | list[str] | None],
    assumed: list[AssumedValue],
) -> None:
    await set_criterion(
        _ctx(state),
        criterion_id="c1",
        text="top 10 percent of trophozoite expression",
        search_name=_SEARCH,
        params=params,
        assumed=assumed,
    )


_STATED: dict[str, str | list[str] | None] = {
    "min_expression_percentile": "90",
    "samples_percentile_generic": "17-30h",
    "ref_samples": "Sample type=a",
    "comp_samples": "Sample type=b",
}


@pytest.mark.asyncio
async def test_a_declared_assumption_is_recorded_on_the_criterion() -> None:
    state = AgentToolState()

    await _bind(state, params=dict(_STATED), assumed=[_TROPHOZOITE])

    [criterion] = state.operational_spec_draft.criteria
    assert criterion.assumptions == [_TROPHOZOITE]


@pytest.mark.asyncio
async def test_a_criterion_without_assumptions_records_none() -> None:
    state = AgentToolState()

    await _bind(state, params=dict(_STATED), assumed=[])

    [criterion] = state.operational_spec_draft.criteria
    assert criterion.assumptions == []


@pytest.mark.asyncio
async def test_an_assumption_on_a_contrast_half_is_a_retry() -> None:
    state = AgentToolState()
    assumed = [
        AssumedValue(
            param_name="comp_samples", value="Sample type=b", reason="looks sensible"
        )
    ]

    with pytest.raises(ModelRetry) as info:
        await _bind(state, params=dict(_STATED), assumed=assumed)

    message = str(info.value)
    assert "comp_samples" in message
    assert "contrast" in message
    assert state.operational_spec_draft.criteria == []


@pytest.mark.asyncio
async def test_an_assumption_for_an_unknown_parameter_is_a_retry() -> None:
    state = AgentToolState()
    assumed = [
        AssumedValue(param_name="samples_percentile", value="17-30h", reason="typo")
    ]

    with pytest.raises(ModelRetry) as info:
        await _bind(state, params=dict(_STATED), assumed=assumed)

    assert "samples_percentile" in str(info.value)
    assert state.operational_spec_draft.criteria == []


@pytest.mark.asyncio
async def test_an_assumption_for_a_parameter_left_null_is_a_retry() -> None:
    state = AgentToolState()
    params = dict(_STATED)
    params["samples_percentile_generic"] = None

    with pytest.raises(ModelRetry) as info:
        await _bind(state, params=params, assumed=[_TROPHOZOITE])

    message = str(info.value)
    assert "samples_percentile_generic" in message
    assert state.operational_spec_draft.criteria == []
