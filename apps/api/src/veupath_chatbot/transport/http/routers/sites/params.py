"""Parameter-related endpoints: dependent params, validation, param specs."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter

from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services import catalog
from veupath_chatbot.transport.http.schemas import (
    DependentParamsRequest,
    DependentParamsResponse,
    ParamSpecResponse,
    ParamSpecsRequest,
    SearchValidationRequest,
    SearchValidationResponse,
)

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


def _build_param_specs(payload: JSONObject) -> list[ParamSpecResponse]:
    from veupath_chatbot.domain.parameters.specs import (
        adapt_param_specs,
        extract_param_specs,
    )

    spec_map = adapt_param_specs(payload)
    raw_specs = extract_param_specs(payload)
    by_name = {
        s.get("name"): s for s in raw_specs if isinstance(s, dict) and s.get("name")
    }
    results: list[ParamSpecResponse] = []
    for name, normalized in spec_map.items():
        raw = by_name.get(name, {})
        if not isinstance(raw, dict):
            raw = {}
        display_name_raw = (
            raw.get("displayName") or raw.get("display") or raw.get("label")
        )
        display_name = display_name_raw if isinstance(display_name_raw, str) else None
        allow_multiple_raw = raw.get("allowMultipleValues")
        allow_multiple = (
            bool(allow_multiple_raw) if isinstance(allow_multiple_raw, bool) else None
        )
        multi_pick_raw = raw.get("multiPick")
        multi_pick = bool(multi_pick_raw) if isinstance(multi_pick_raw, bool) else None
        vocabulary_raw = raw.get("vocabulary")
        initial_display_value = raw.get("initialDisplayValue")
        min_val = raw.get("min") or raw.get("minValue") or raw.get("numberMin")
        max_val = raw.get("max") or raw.get("maxValue") or raw.get("numberMax")
        if min_val is not None and not isinstance(min_val, (int, float)):
            min_val = None
        if max_val is not None and not isinstance(max_val, (int, float)):
            max_val = None
        min_value = float(min_val) if min_val is not None else None
        max_value = float(max_val) if max_val is not None else None

        is_number_raw = raw.get("isNumber")
        is_number = bool(is_number_raw) if isinstance(is_number_raw, bool) else False

        increment_raw = raw.get("increment") or raw.get("step")
        increment = (
            float(increment_raw) if isinstance(increment_raw, (int, float)) else None
        )

        results.append(
            ParamSpecResponse(
                name=name,
                displayName=display_name,
                type=normalized.param_type,
                allowEmptyValue=normalized.allow_empty_value,
                allowMultipleValues=allow_multiple,
                multiPick=multi_pick,
                minSelectedCount=normalized.min_selected_count,
                maxSelectedCount=normalized.max_selected_count,
                countOnlyLeaves=normalized.count_only_leaves,
                initialDisplayValue=initial_display_value,
                vocabulary=vocabulary_raw,
                min=min_value,
                max=max_value,
                isNumber=is_number,
                increment=increment,
            )
        )
    results.sort(key=lambda s: s.name)
    return results


@router.post(
    "/{siteId}/searches/{recordType}/{searchName}/dependent-params",
    response_model=DependentParamsResponse,
)
async def get_dependent_params(
    siteId: str,
    recordType: str,
    searchName: str,
    payload: DependentParamsRequest,
) -> DependentParamsResponse:
    """Get dependent parameter vocabulary values."""
    client = get_wdk_client(siteId)
    try:
        result = await client.get_refreshed_dependent_params(
            recordType,
            searchName,
            payload.parameter_name,
            payload.context_values,
        )
        return cast(DependentParamsResponse, result)
    except WDKError as exc:
        if siteId != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            result = await portal_client.get_refreshed_dependent_params(
                recordType,
                searchName,
                payload.parameter_name,
                payload.context_values,
            )
            return cast(DependentParamsResponse, result)
        raise exc


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
        site_id=siteId,
        record_type=recordType,
        search_name=searchName,
        context_values=payload.context_values or {},
    )
    return cast(SearchValidationResponse, result)


@router.get(
    "/{siteId}/searches/{recordType}/{searchName}/param-specs",
    response_model=list[ParamSpecResponse],
)
async def get_param_specs(
    siteId: str,
    recordType: str,
    searchName: str,
) -> list[ParamSpecResponse]:
    """Return normalized parameter specs for UI consumption."""
    discovery = get_discovery_service()
    details_raw = await discovery.get_search_details(
        siteId, recordType, searchName, expand_params=True
    )
    details: JSONObject
    if isinstance(details_raw, dict):
        search_data_raw = details_raw.get("searchData")
        details = search_data_raw if isinstance(search_data_raw, dict) else details_raw
    else:
        details = {}
    return _build_param_specs(details)


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
    details_raw = await catalog.expand_search_details_with_params(
        site_id=siteId,
        record_type=recordType,
        search_name=searchName,
        context_values=payload.context_values or {},
    )
    details: JSONObject
    if isinstance(details_raw, dict):
        search_data_raw = details_raw.get("searchData")
        details = search_data_raw if isinstance(search_data_raw, dict) else details_raw
    else:
        details = {}
    return _build_param_specs(details)
