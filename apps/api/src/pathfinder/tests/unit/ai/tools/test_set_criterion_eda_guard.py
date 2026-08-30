"""set_criterion refuses a proposed EDA analysis spec and names the EDA tools."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.ai.tools.standalone.frame_spec import set_criterion
from pathfinder.domain.parameters.values import ParamValue, StringValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.catalog import param_validation as pv
from pathfinder.services.catalog import searches
from pathfinder.services.catalog.eda_backed import (
    COMPUTE_QUERY,
    EDA_ANALYSIS_SPEC_PARAM,
    EDA_DATASET_ID_PARAM,
)
from pathfinder.services.catalog.param_dag import ResolvedParams
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
)

_DATASET_ID = "DS_e973eadd57"
_DESEQ_SEARCH = "GenesByRNASeqpfal3D7_Pfal3D7_Febrile_temps_RNASeq_ebi_rnaSeq_RSRCDESeq"
_INVENTED_SPEC = (
    '{"data_type":"read counts",'
    '"comparison":{"case":"febrile","control":"normal"},'
    '"fold_change":{"direction":"both","minimum":2},'
    '"adjusted_p_value":{"maximum":0.05}}'
)


def _parameters() -> list[WDKParameter]:
    return [
        WDKStringParam(
            name=EDA_DATASET_ID_PARAM,
            display_name=EDA_DATASET_ID_PARAM,
            allow_empty_value=True,
            initial_display_value="",
        ),
        WDKStringParam(
            name=EDA_ANALYSIS_SPEC_PARAM,
            display_name=EDA_ANALYSIS_SPEC_PARAM,
            allow_empty_value=True,
            initial_display_value="",
        ),
    ]


def _definition() -> WDKSearch:
    parameters = _parameters()
    return WDKSearch(
        url_segment=_DESEQ_SEARCH,
        display_name=_DESEQ_SEARCH,
        query_name=COMPUTE_QUERY,
        param_names=[p.name for p in parameters],
        parameters=parameters,
    )


def _response() -> WDKSearchResponse:
    return WDKSearchResponse(
        search_data=_definition(),
        validation=StepValidation.model_validate(
            {"level": "DISPLAYABLE", "isValid": True, "errors": None}
        ),
    )


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    graph = MagicMock()
    graph.record_type = "transcript"
    ctx.deps.strategy_session.get_graph.return_value = graph
    return ctx


def _serve(monkeypatch: pytest.MonkeyPatch, spec_value: str) -> None:
    """Answer every read on the params path with the DESeq definition."""
    infos = format_param_info_typed(_parameters())

    def _fetch_at(*_args: object) -> object:
        async def fetch_at(_context: dict[str, str]) -> list[ParameterInfo]:
            return infos

        return fetch_at

    async def _details(
        ctx: SearchContext, **_kw: object
    ) -> tuple[WDKSearchResponse, str]:
        return _response(), ctx.record_type

    async def _resolve(**_kw: object) -> ResolvedParams:
        return ResolvedParams(
            params={
                EDA_DATASET_ID_PARAM: StringValue(value=_DATASET_ID),
                EDA_ANALYSIS_SPEC_PARAM: StringValue(value=spec_value),
            },
            open_slots=[],
            unresolved_required=[],
        )

    async def _search_details(
        _record_type: str, name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del name, expand_params
        return _response()

    client = MagicMock()
    client.get_search_details = _search_details
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(frame_spec, "wdk_fetch_at", _fetch_at)
    monkeypatch.setattr(frame_spec, "fetch_search_details", _details)
    monkeypatch.setattr(frame_spec, "resolve_params_with_intent", _resolve)
    monkeypatch.setattr(frame_spec, "make_validation_callbacks", _callbacks)
    _serve_wdk(monkeypatch)


def _callbacks(site_id: str, **_kw: object) -> pv.ValidationCallbacks:
    del site_id

    async def _record_type(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = False,
    ) -> str | None:
        del search_name, require_match, allow_fallback
        return record_type

    async def _hint(search_name: str, record_type: str | None) -> str | None:
        del search_name, record_type
        return None

    return pv.ValidationCallbacks(
        resolve_record_type_for_search=_record_type, find_record_type_hint=_hint
    )


def _serve_wdk(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolved(
        ctx: SearchContext,
        *,
        resolved_record_type: str,
        parameters: dict[str, ParamValue],
    ) -> pv.ResolvedSearch:
        del ctx, resolved_record_type, parameters
        return pv.ResolvedSearch(response=_response(), values_were_read=True)

    async def _no_refresh(
        ctx: SearchContext,
        *,
        parameter_name: str,
        context_values: dict[str, ParamValue],
    ) -> list[WDKParameter]:
        del ctx, parameter_name, context_values
        return []

    monkeypatch.setattr(pv, "_resolve_search_details", _resolved)
    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _no_refresh)


async def _call(state: AgentToolState, spec_value: str) -> object:
    return (
        await set_criterion(
            _ctx(state),
            criterion_id="c_deseq",
            text="genes up in febrile against normal",
            search_name=_DESEQ_SEARCH,
            params={
                EDA_DATASET_ID_PARAM: _DATASET_ID,
                EDA_ANALYSIS_SPEC_PARAM: spec_value,
            },
        )
    ).return_value


class TestAProposedSpecComesBackAsARetry:
    @pytest.mark.asyncio
    async def test_the_retry_names_the_eda_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = AgentToolState()
        _serve(monkeypatch, _INVENTED_SPEC)

        with pytest.raises(ModelRetry) as excinfo:
            await _call(state, _INVENTED_SPEC)

        message = str(excinfo.value)
        assert "open_eda_analysis" in message
        assert "set_eda_filters" in message
        assert "run_eda_compute" in message
        assert "create_eda_step" in message

    @pytest.mark.asyncio
    async def test_the_retry_names_the_spec_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = AgentToolState()
        _serve(monkeypatch, _INVENTED_SPEC)

        with pytest.raises(ModelRetry) as excinfo:
            await _call(state, _INVENTED_SPEC)

        assert EDA_ANALYSIS_SPEC_PARAM in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_the_criterion_is_not_bound(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = AgentToolState()
        _serve(monkeypatch, _INVENTED_SPEC)

        with pytest.raises(ModelRetry):
            await _call(state, _INVENTED_SPEC)

        assert state.operational_spec_draft.criteria == []
