"""Parameter-related endpoints: dependent params, validation, param specs."""

from fastapi import APIRouter

from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    extract_param_specs,
)
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services import catalog
from veupath_chatbot.transport.http.schemas import (
    ParamSpecResponse,
    ParamSpecsRequest,
    SearchValidationRequest,
    SearchValidationResponse,
)

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


def _build_param_specs(payload: JSONObject) -> list[ParamSpecResponse]:
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

        # WDK UI metadata
        display_type_raw = raw.get("displayType")
        display_type = (
            str(display_type_raw) if isinstance(display_type_raw, str) else None
        )
        is_visible_raw = raw.get("isVisible")
        is_visible = bool(is_visible_raw) if isinstance(is_visible_raw, bool) else True
        group_raw = raw.get("group")
        group_str = str(group_raw) if isinstance(group_raw, str) else None
        dependent_params_raw = raw.get("dependentParams")
        dependent_params = (
            [str(p) for p in dependent_params_raw]
            if isinstance(dependent_params_raw, list)
            else []
        )
        help_raw = raw.get("help")
        help_text = str(help_raw) if isinstance(help_raw, str) else None

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
                displayType=display_type,
                isVisible=is_visible,
                group=group_str,
                dependentParams=dependent_params,
                help=help_text,
            )
        )
    results.sort(key=lambda s: s.name)
    return results


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
    search_dict = response.search_data.model_dump(by_alias=True)
    return _build_param_specs(search_dict)
