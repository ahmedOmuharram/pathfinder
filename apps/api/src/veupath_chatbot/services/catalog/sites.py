"""Sites and record types catalog functions."""

from veupath_chatbot.integrations.veupathdb.discovery import get_discovery_service
from veupath_chatbot.integrations.veupathdb.factory import list_sites as list_wdk_sites
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.services.catalog.models import RecordTypeInfo


async def list_sites() -> list[SiteInfo]:
    """List all available VEuPathDB sites."""
    return list_wdk_sites()


async def get_record_types(site_id: str) -> list[RecordTypeInfo]:
    """Get record types for a specific site."""
    discovery = get_discovery_service()
    record_types = await discovery.get_record_types(site_id)
    return [
        RecordTypeInfo(
            name=rt.url_segment,
            display_name=rt.display_name,
            description=rt.description,
        )
        for rt in record_types
    ]
