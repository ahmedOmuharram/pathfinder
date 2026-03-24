"""Parameter-related endpoints: dependent params, validation, param specs."""

from collections.abc import Sequence

from fastapi import APIRouter

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKNumberParam,
    WDKNumberRangeParam,
    WDKParameter,
    WDKStringParam,
)
from veupath_chatbot.services import catalog
from veupath_chatbot.transport.http.schemas import (
    DependentParamsRequest,
    ParamSpecResponse,
    ParamSpecsRequest,
    SearchValidationRequest,
    SearchValidationResponse,
)

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


def _build_param_specs_from_list(
    params: Sequence[WDKParameter],
) -> list[ParamSpecResponse]:
    """Convert a list of WDK parameters to normalized ParamSpecResponse objects."""
    results: list[ParamSpecResponse] = []
    for param in params:
        # Enum-specific fields
        vocabulary = param.vocabulary if isinstance(param, WDKEnumParam) else None
        display_type = param.display_type if isinstance(param, WDKEnumParam) else None
        min_selected_count = (
            param.min_selected_count if isinstance(param, WDKEnumParam) else None
        )
        max_selected_raw = (
            param.max_selected_count if isinstance(param, WDKEnumParam) else None
        )
        max_selected_count = (
            max_selected_raw
            if isinstance(max_selected_raw, int) and max_selected_raw >= 0
            else None
        )
        count_only_leaves = (
            param.count_only_leaves if isinstance(param, WDKEnumParam) else False
        )

        # Number-specific fields
        min_value = (
            param.min
            if isinstance(param, (WDKNumberParam, WDKNumberRangeParam))
            else None
        )
        max_value = (
            param.max
            if isinstance(param, (WDKNumberParam, WDKNumberRangeParam))
            else None
        )
        increment = (
            param.increment
            if isinstance(param, (WDKNumberParam, WDKNumberRangeParam))
            else None
        )

        # String-specific fields
        is_number = param.is_number if isinstance(param, WDKStringParam) else False

        is_multi = param.type == "multi-pick-vocabulary"

        results.append(
            ParamSpecResponse.model_validate(
                {
                    "name": param.name,
                    "displayName": param.display_name or None,
                    "type": param.type,
                    "allowEmptyValue": param.allow_empty_value,
                    "allowMultipleValues": is_multi,
                    "multiPick": is_multi,
                    "minSelectedCount": min_selected_count,
                    "maxSelectedCount": max_selected_count,
                    "countOnlyLeaves": count_only_leaves,
                    "initialDisplayValue": param.initial_display_value,
                    "vocabulary": vocabulary,
                    "min": min_value,
                    "max": max_value,
                    "isNumber": is_number,
                    "increment": increment,
                    "displayType": display_type,
                    "isVisible": param.is_visible,
                    "group": param.group or None,
                    "dependentParams": list(param.dependent_params),
                    "help": param.help,
                }
            ),
        )
    results.sort(key=lambda s: s.name)
    return results


def _build_param_specs(search: WDKSearch) -> list[ParamSpecResponse]:
    return _build_param_specs_from_list(search.parameters or [])


@router.post(
    "/{siteId}/searches/{recordType}/{searchName}/validate",
    response_model=SearchValidationResponse,
)
async def validate_search_params(
    siteId: str,
    recordType: str,
    searchName: str,
    payload: SearchValidationRequest,
) -> SearchValidationResponse:
    """Validate search parameters (UI-friendly)."""
    result = await catalog.validate_search_params(
        SearchContext(siteId, recordType, searchName),
        context_values=payload.context_values or {},
    )
    return SearchValidationResponse.model_validate(result)


@router.post(
    "/{siteId}/searches/{recordType}/{searchName}/param-specs",
    response_model=list[ParamSpecResponse],
)
async def get_param_specs_with_context(
    siteId: str,
    recordType: str,
    searchName: str,
    payload: ParamSpecsRequest,
) -> list[ParamSpecResponse]:
    """Return normalized parameter specs, using contextual WDK vocab when provided."""
    response = await catalog.expand_search_details_with_params(
        SearchContext(siteId, recordType, searchName),
        payload.context_values or {},
    )
    return _build_param_specs(response.search_data)


@router.post(
    "/{siteId}/searches/{recordType}/{searchName}/refreshed-dependent-params",
    response_model=list[ParamSpecResponse],
)
async def refresh_dependent_params(
    siteId: str,
    recordType: str,
    searchName: str,
    payload: DependentParamsRequest,
) -> list[ParamSpecResponse]:
    """Refresh dependent parameter vocabularies after a param value changes."""
    params = await catalog.get_refreshed_dependent_params(
        SearchContext(siteId, recordType, searchName),
        parameter_name=payload.parameter_name,
        context_values=payload.context_values or {},
    )
    return _build_param_specs_from_list(params)
