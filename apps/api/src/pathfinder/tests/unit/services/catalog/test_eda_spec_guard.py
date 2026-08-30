"""A proposed eda_analysis_spec never reaches WDK.

The spec parameter carries a whole EDA analysis document, so the only values
that pass are the ones the EDA tools author.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from pathfinder.domain.parameters.values import ParamValue, StringValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.eda.models import EdaStringSetFilter
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKParameter,
    WDKStringParam,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog import param_validation as pv
from pathfinder.services.catalog.eda_backed import (
    COMPUTE_QUERY,
    EDA_ANALYSIS_SPEC_PARAM,
    EDA_DATASET_ID_PARAM,
    SUBSET_QUERY,
)
from pathfinder.services.eda.authoring import new_analysis, serialize_spec

_DATASET_ID = "DS_e973eadd57"
_DESEQ_SEARCH = "GenesByRNASeqpfal3D7_Pfal3D7_Febrile_temps_RNASeq_ebi_rnaSeq_RSRCDESeq"
_INVENTED_SPEC = (
    '{"data_type":"read counts",'
    '"comparison":{"case":"febrile","control":"normal"},'
    '"fold_change":{"direction":"both","minimum":2},'
    '"adjusted_p_value":{"maximum":0.05}}'
)


class _ErrorRow(BaseModel):
    """One row of a validation error payload."""

    model_config = ConfigDict(extra="ignore")
    param: str
    messages: list[str]


def _authored_spec(dataset_id: str) -> str:
    return serialize_spec(
        new_analysis(
            dataset_id=dataset_id,
            display_name="Febrile against normal",
            filters=[
                EdaStringSetFilter(
                    entity_id="EUPATH_0000096",
                    variable_id="EUPATH_0000731",
                    string_set=["febrile"],
                )
            ],
        )
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


def _response(*, search_name: str, query_name: str) -> WDKSearchResponse:
    parameters = _parameters()
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment=search_name,
            display_name=search_name,
            query_name=query_name,
            param_names=[p.name for p in parameters],
            parameters=parameters,
        ),
        validation=StepValidation.model_validate(
            {"level": "DISPLAYABLE", "isValid": True, "errors": None}
        ),
    )


def _serve(monkeypatch: pytest.MonkeyPatch, response: WDKSearchResponse) -> None:
    async def _details(
        ctx: SearchContext,
        *,
        resolved_record_type: str,
        parameters: dict[str, ParamValue],
    ) -> pv.ResolvedSearch:
        del ctx, resolved_record_type, parameters
        return pv.ResolvedSearch(response=response, values_were_read=True)

    async def _no_refresh(
        ctx: SearchContext,
        *,
        parameter_name: str,
        context_values: dict[str, ParamValue],
    ) -> list[WDKParameter]:
        del ctx, parameter_name, context_values
        return []

    monkeypatch.setattr(pv, "_resolve_search_details", _details)
    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _no_refresh)


def _callbacks() -> pv.ValidationCallbacks:
    async def _resolve(
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
        resolve_record_type_for_search=_resolve, find_record_type_hint=_hint
    )


async def _validate(search_name: str, spec: str) -> pv.ValidatedParams:
    return await pv.validate_parameters(
        SearchContext(
            site_id="plasmodb", record_type="transcript", search_name=search_name
        ),
        parameters={
            EDA_DATASET_ID_PARAM: StringValue(value=_DATASET_ID),
            EDA_ANALYSIS_SPEC_PARAM: StringValue(value=spec),
        },
        callbacks=_callbacks(),
    )


def _row(exc: ValidationError) -> _ErrorRow:
    errors = exc.errors or []
    assert len(errors) == 1
    return _ErrorRow.model_validate(errors[0])


class TestAProposedSpecIsRefused:
    @pytest.mark.asyncio
    async def test_the_invented_spec_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=_DESEQ_SEARCH, query_name=COMPUTE_QUERY),
        )

        with pytest.raises(ValidationError) as excinfo:
            await _validate(_DESEQ_SEARCH, _INVENTED_SPEC)

        assert excinfo.value.title == (
            "eda_analysis_spec is written by PathFinder, not proposed"
        )

    @pytest.mark.asyncio
    async def test_the_refusal_sends_the_model_to_the_eda_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=_DESEQ_SEARCH, query_name=COMPUTE_QUERY),
        )

        with pytest.raises(ValidationError) as excinfo:
            await _validate(_DESEQ_SEARCH, _INVENTED_SPEC)

        detail = excinfo.value.detail or ""
        assert "open_eda_analysis" in detail
        assert "run_eda_compute" in detail
        assert "create_eda_step" in detail

    @pytest.mark.asyncio
    async def test_the_refusal_names_the_spec_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=_DESEQ_SEARCH, query_name=COMPUTE_QUERY),
        )

        with pytest.raises(ValidationError) as excinfo:
            await _validate(_DESEQ_SEARCH, _INVENTED_SPEC)

        row = _row(excinfo.value)
        assert row.param == EDA_ANALYSIS_SPEC_PARAM
        assert row.messages

    @pytest.mark.asyncio
    async def test_a_spec_naming_another_dataset_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=_DESEQ_SEARCH, query_name=COMPUTE_QUERY),
        )

        with pytest.raises(ValidationError):
            await _validate(_DESEQ_SEARCH, _authored_spec("DS_66f9e70b8a"))


class TestAnAuthoredSpecPasses:
    @pytest.mark.asyncio
    async def test_a_serialized_analysis_naming_the_dataset_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=_DESEQ_SEARCH, query_name=COMPUTE_QUERY),
        )

        result = await _validate(_DESEQ_SEARCH, _authored_spec(_DATASET_ID))

        assert result.params[EDA_ANALYSIS_SPEC_PARAM] == StringValue(
            value=_authored_spec(_DATASET_ID)
        )


class TestAnEmptySpecFollowsTheQuery:
    @pytest.mark.asyncio
    async def test_the_subset_search_accepts_an_empty_spec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=SUBSET_QUERY, query_name=SUBSET_QUERY),
        )

        result = await _validate(SUBSET_QUERY, "")

        assert result.params[EDA_ANALYSIS_SPEC_PARAM] == StringValue(value="")

    @pytest.mark.asyncio
    async def test_a_compute_backed_search_refuses_an_empty_spec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(
            monkeypatch,
            _response(search_name=COMPUTE_QUERY, query_name=COMPUTE_QUERY),
        )

        with pytest.raises(ValidationError) as excinfo:
            await _validate(COMPUTE_QUERY, "")

        assert "run_eda_compute" in (excinfo.value.detail or "")
        assert _row(excinfo.value).param == EDA_ANALYSIS_SPEC_PARAM


class TestAPlainSearchIsUntouched:
    @pytest.mark.asyncio
    async def test_a_search_without_the_spec_parameter_validates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = WDKStringParam(
            name="text_expression",
            display_name="text_expression",
            allow_empty_value=True,
            initial_display_value="",
        )
        _serve(
            monkeypatch,
            WDKSearchResponse(
                search_data=WDKSearch(
                    url_segment="GenesByText",
                    display_name="GenesByText",
                    query_name="GenesByText",
                    param_names=["text_expression"],
                    parameters=[text],
                ),
                validation=StepValidation.model_validate(
                    {"level": "DISPLAYABLE", "isValid": True, "errors": None}
                ),
            ),
        )

        result = await pv.validate_parameters(
            SearchContext(
                site_id="plasmodb", record_type="transcript", search_name="GenesByText"
            ),
            parameters={"text_expression": StringValue(value="kinase")},
            callbacks=_callbacks(),
        )

        assert result.params["text_expression"] == StringValue(value="kinase")
