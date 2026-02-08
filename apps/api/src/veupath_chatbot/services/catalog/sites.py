"""Sites and record types catalog functions."""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import list_sites as list_wdk_sites
from veupath_chatbot.platform.types import JSONArray


async def list_sites() -> JSONArray:
    """List all available VEuPathDB sites."""
    return [site.to_dict() for site in list_wdk_sites()]


async def get_record_types(site_id: str) -> JSONArray:
    """Get record types for a specific site."""
    discovery = get_discovery_service()
    record_types = await discovery.get_record_types(site_id)
    result: JSONArray = []
    for rt in record_types:
        if not isinstance(rt, dict):
            continue
        url_segment_raw = rt.get("urlSegment")
        name_raw = rt.get("name")
        url_segment = url_segment_raw if isinstance(url_segment_raw, str) else None
        name = name_raw if isinstance(name_raw, str) else None
        display_name_raw = rt.get("displayName")
        display_name = display_name_raw if isinstance(display_name_raw, str) else None
        description_raw = rt.get("description")
        description = description_raw if isinstance(description_raw, str) else ""
        result.append(
            {
                "name": url_segment or name or "",
                "displayName": display_name,
                "description": description,
            }
        )
    return result
