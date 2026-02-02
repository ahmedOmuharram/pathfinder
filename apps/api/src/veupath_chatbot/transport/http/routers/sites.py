"""VEuPathDB sites and discovery endpoints."""

from typing import Annotated

from fastapi import APIRouter, Query

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, WDKError
from veupath_chatbot.services import catalog
from veupath_chatbot.transport.http.schemas import (
    DependentParamsResponse,
    DependentParamsRequest,
    ParamSpecResponse,
    RecordTypeResponse,
    SearchResponse,
    SearchDetailsResponse,
    SearchValidationRequest,
    SearchValidationResponse,
    SiteResponse,
)
from veupath_chatbot.integrations.veupathdb.factory import get_wdk_client
from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


@router.get("", response_model=list[SiteResponse])
async def list_sites() -> list[SiteResponse]:
    """List all available VEuPathDB sites."""
    sites = await catalog.list_sites()
    return [
        SiteResponse(
            id=s.get("id", ""),
            name=s.get("name", ""),
            displayName=s.get("displayName", ""),
            baseUrl=s.get("baseUrl", ""),
            projectId=s.get("projectId", ""),
            isPortal=bool(s.get("isPortal", False)),
        )
        for s in sites
    ]


@router.get("/{siteId}", response_model=SiteResponse)
async def get_site(siteId: str) -> SiteResponse:
    """Get a single site by ID."""
    sites = await catalog.list_sites()
    match = next((s for s in sites if s.get("id") == siteId), None)
    if not match:
        raise NotFoundError(
            code=ErrorCode.SITE_NOT_FOUND,
            title="Site not found",
            detail=f"Unknown siteId '{siteId}'.",
        )
    return SiteResponse(
        id=match.get("id", ""),
        name=match.get("name", ""),
        displayName=match.get("displayName", ""),
        baseUrl=match.get("baseUrl", ""),
        projectId=match.get("projectId", ""),
        isPortal=bool(match.get("isPortal", False)),
    )


@router.get("/{siteId}/record-types", response_model=list[RecordTypeResponse])
async def get_record_types(siteId: str) -> list[RecordTypeResponse]:
    """Get record types available on a site."""
    record_types = await catalog.get_record_types(siteId)
    return [
        RecordTypeResponse(
            name=rt.get("name", ""),
            displayName=rt.get("displayName", ""),
            description=rt.get("description"),
        )
        for rt in record_types
    ]


@router.get("/{siteId}/searches", response_model=list[SearchResponse])
async def get_searches(
    siteId: str,
    record_type: Annotated[str | None, Query(alias="recordType")] = None,
) -> list[SearchResponse]:
    """Get searches available on a site.

    Optionally filter by record type.
    """
    if record_type:
        searches = await catalog.list_searches(siteId, record_type)
        return [
            SearchResponse(
                name=s.get("name", ""),
                displayName=s.get("displayName", ""),
                description=s.get("description", ""),
                recordType=record_type,
            )
            for s in searches
        ]

    # Get all searches across all record types
    discovery = get_discovery_service()
    record_types = await discovery.get_record_types(siteId)
    all_searches: list[SearchResponse] = []

    for rt in record_types:
        rt_name = rt.get("urlSegment", rt.get("name", ""))
        if rt_name:
            searches = await catalog.list_searches(siteId, rt_name)
            for s in searches:
                all_searches.append(
                    SearchResponse(
                        name=s.get("name", ""),
                        displayName=s.get("displayName", ""),
                        description=s.get("description", ""),
                        recordType=rt_name,
                    )
                )

    return all_searches


@router.get("/{siteId}/searches/{recordType}/{searchName}", response_model=SearchDetailsResponse)
async def get_search_details(
    siteId: str,
    recordType: str,
    searchName: str,
):
    """Get detailed search configuration with parameters."""
    discovery = get_discovery_service()
    return await discovery.get_search_details(siteId, recordType, searchName)


@router.post(
    "/{siteId}/searches/{recordType}/{searchName}/dependent-params",
    response_model=DependentParamsResponse,
)
async def get_dependent_params(
    siteId: str,
    recordType: str,
    searchName: str,
    payload: DependentParamsRequest,
):
    """Get dependent parameter vocabulary values."""
    client = get_wdk_client(siteId)
    try:
        return await client.get_refreshed_dependent_params(
            recordType,
            searchName,
            payload.parameter_name,
            payload.context_values,
        )
    except WDKError as exc:
        if siteId != "veupathdb":
            portal_client = get_wdk_client("veupathdb")
            return await portal_client.get_refreshed_dependent_params(
                recordType,
                searchName,
                payload.parameter_name,
                payload.context_values,
            )
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
):
    """Validate search parameters (UI-friendly)."""
    return await catalog.validate_search_params(
        site_id=siteId,
        record_type=recordType,
        search_name=searchName,
        context_values=payload.context_values or {},
    )


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
    details = await discovery.get_search_details(siteId, recordType, searchName, expand_params=True)
    if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
        details = details["searchData"]
    payload = details if isinstance(details, dict) else {}
    from veupath_chatbot.domain.parameters.specs import adapt_param_specs, extract_param_specs

    spec_map = adapt_param_specs(payload)
    raw_specs = extract_param_specs(payload)
    by_name = {s.get("name"): s for s in raw_specs if isinstance(s, dict) and s.get("name")}
    results: list[ParamSpecResponse] = []
    for name, normalized in spec_map.items():
        raw = by_name.get(name, {})
        results.append(
            ParamSpecResponse(
                name=name,
                displayName=raw.get("displayName") or raw.get("display") or raw.get("label"),
                type=normalized.param_type,
                allowEmptyValue=normalized.allow_empty_value,
                minSelectedCount=normalized.min_selected_count,
                maxSelectedCount=normalized.max_selected_count,
                countOnlyLeaves=normalized.count_only_leaves,
                vocabulary=raw.get("vocabulary"),
            )
        )
    results.sort(key=lambda s: s.name)
    return results

