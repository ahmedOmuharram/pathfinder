"""Organism listing via site-search."""

from pathfinder.integrations.veupathdb.site_router import get_site_router
from pathfinder.integrations.veupathdb.site_search_client import DocumentTypeFilter


async def list_organisms(site_id: str) -> list[str]:
    """Return sorted organism names for a site."""
    site_router = get_site_router()
    client = site_router.get_site_search_client(site_id)
    response = await client.search(
        search_text="*",
        document_type_filter=DocumentTypeFilter(document_type="gene"),
        limit=1,
    )
    return sorted(response.organism_counts.keys())
