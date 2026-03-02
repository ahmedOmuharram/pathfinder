"""Site listing, record types, and search catalog endpoints."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Query

from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services import catalog
from veupath_chatbot.transport.http.schemas import (
    RecordTypeResponse,
    SearchDetailsResponse,
    SearchResponse,
    SiteResponse,
)

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


@router.get("", response_model=list[SiteResponse])
async def list_sites() -> list[SiteResponse]:
    """List all available VEuPathDB sites."""
    sites = await catalog.list_sites()
    result: list[SiteResponse] = []
    for s in sites:
        if not isinstance(s, dict):
            continue
        id_raw = s.get("id")
        name_raw = s.get("name")
        display_name_raw = s.get("displayName")
        base_url_raw = s.get("baseUrl")
        project_id_raw = s.get("projectId")
        is_portal_raw = s.get("isPortal")
        result.append(
            SiteResponse(
                id=id_raw if isinstance(id_raw, str) else "",
                name=name_raw if isinstance(name_raw, str) else "",
                displayName=display_name_raw
                if isinstance(display_name_raw, str)
                else "",
                baseUrl=base_url_raw if isinstance(base_url_raw, str) else "",
                projectId=project_id_raw if isinstance(project_id_raw, str) else "",
                isPortal=bool(is_portal_raw)
                if isinstance(is_portal_raw, bool)
                else False,
            )
        )
    return result


@router.get("/{siteId}", response_model=SiteResponse)
async def get_site(siteId: str) -> SiteResponse:
    """Get a single site by ID."""
    sites = await catalog.list_sites()
    match: JSONObject | None = None
    for s in sites:
        if not isinstance(s, dict):
            continue
        id_raw = s.get("id")
        if isinstance(id_raw, str) and id_raw == siteId:
            match = s
            break
    if not match:
        raise NotFoundError(
            code=ErrorCode.SITE_NOT_FOUND,
            title="Site not found",
            detail=f"Unknown siteId '{siteId}'.",
        )
    id_raw = match.get("id")
    name_raw = match.get("name")
    display_name_raw = match.get("displayName")
    base_url_raw = match.get("baseUrl")
    project_id_raw = match.get("projectId")
    is_portal_raw = match.get("isPortal")
    return SiteResponse(
        id=id_raw if isinstance(id_raw, str) else "",
        name=name_raw if isinstance(name_raw, str) else "",
        displayName=display_name_raw if isinstance(display_name_raw, str) else "",
        baseUrl=base_url_raw if isinstance(base_url_raw, str) else "",
        projectId=project_id_raw if isinstance(project_id_raw, str) else "",
        isPortal=bool(is_portal_raw) if isinstance(is_portal_raw, bool) else False,
    )


@router.get("/{siteId}/record-types", response_model=list[RecordTypeResponse])
async def get_record_types(siteId: str) -> list[RecordTypeResponse]:
    """Get record types available on a site."""
    record_types = await catalog.get_record_types(siteId)
    result: list[RecordTypeResponse] = []
    for rt in record_types:
        if not isinstance(rt, dict):
            continue
        name_raw = rt.get("name")
        display_name_raw = rt.get("displayName")
        description_raw = rt.get("description")
        result.append(
            RecordTypeResponse(
                name=name_raw if isinstance(name_raw, str) else "",
                displayName=display_name_raw
                if isinstance(display_name_raw, str)
                else "",
                description=description_raw
                if isinstance(description_raw, str)
                else None,
            )
        )
    return result


@router.get("/{siteId}/searches", response_model=list[SearchResponse])
async def get_searches(
    siteId: str,
    record_type: Annotated[str | None, Query(alias="recordType")] = None,
) -> list[SearchResponse]:
    """Get searches available on a site, optionally filtered by record type."""
    if record_type:
        searches = await catalog.list_searches(siteId, record_type)
        result: list[SearchResponse] = []
        for s in searches:
            if not isinstance(s, dict):
                continue
            name_raw = s.get("name")
            display_name_raw = s.get("displayName")
            description_raw = s.get("description")
            result.append(
                SearchResponse(
                    name=name_raw if isinstance(name_raw, str) else "",
                    displayName=display_name_raw
                    if isinstance(display_name_raw, str)
                    else "",
                    description=description_raw
                    if isinstance(description_raw, str)
                    else "",
                    recordType=record_type,
                )
            )
        return result

    discovery = get_discovery_service()
    record_types = await discovery.get_record_types(siteId)
    all_searches: list[SearchResponse] = []

    for rt in record_types:
        if not isinstance(rt, dict):
            continue
        rt_url_seg_raw: JSONValue | None = rt.get("urlSegment")
        rt_name_raw: JSONValue | None = rt.get("name")
        url_seg = rt_url_seg_raw if isinstance(rt_url_seg_raw, str) else None
        name = rt_name_raw if isinstance(rt_name_raw, str) else None
        rt_name = url_seg or name or ""
        if rt_name:
            searches = await catalog.list_searches(siteId, rt_name)
            for s in searches:
                if not isinstance(s, dict):
                    continue
                name_raw = s.get("name")
                display_name_raw = s.get("displayName")
                description_raw = s.get("description")
                all_searches.append(
                    SearchResponse(
                        name=name_raw if isinstance(name_raw, str) else "",
                        displayName=display_name_raw
                        if isinstance(display_name_raw, str)
                        else "",
                        description=description_raw
                        if isinstance(description_raw, str)
                        else "",
                        recordType=rt_name,
                    )
                )

    return all_searches


@router.get(
    "/{siteId}/searches/{recordType}/{searchName}", response_model=SearchDetailsResponse
)
async def get_search_details(
    siteId: str,
    recordType: str,
    searchName: str,
) -> SearchDetailsResponse:
    """Get detailed search configuration with parameters."""
    discovery = get_discovery_service()
    result = await discovery.get_search_details(siteId, recordType, searchName)
    return cast(SearchDetailsResponse, result)
