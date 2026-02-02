"""Discovery and caching of record types, searches, and parameters."""

import asyncio
from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router

logger = get_logger(__name__)


class SearchCatalog:
    """Cached catalog of searches for a site."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self._record_types: list[dict[str, Any]] = []
        self._searches: dict[str, list[dict[str, Any]]] = {}
        self._search_details: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._lock = asyncio.Lock()

    async def load(self, client: VEuPathDBClient) -> None:
        """Load catalog from VEuPathDB."""
        async with self._lock:
            if self._loaded:
                return

            logger.info("Loading search catalog", site_id=self.site_id)

            try:
                # Load record types with expanded searches when possible
                raw_record_types = await client.get_record_types(expanded=True)
                if isinstance(raw_record_types, dict):
                    raw_record_types = (
                        raw_record_types.get("recordTypes")
                        or raw_record_types.get("records")
                        or raw_record_types.get("result")
                        or []
                    )
                expanded_supported = any(
                    isinstance(rt, dict) and "searches" in rt for rt in raw_record_types
                )

                # Handle both list of strings and list of dicts
                for rt in raw_record_types:
                    if isinstance(rt, str):
                        rt_name = rt
                        self._record_types.append({"urlSegment": rt, "name": rt})
                        searches = []
                    else:
                        rt_name = rt.get("urlSegment", rt.get("name", ""))
                        self._record_types.append(rt)
                        searches = rt.get("searches") if expanded_supported else None

                    if rt_name:
                        if searches is not None and searches != []:
                            self._searches[rt_name] = searches
                        else:
                            try:
                                searches = await client.get_searches(rt_name)
                                self._searches[rt_name] = searches
                            except Exception as e:
                                logger.warning(
                                    "Failed to load searches",
                                    record_type=rt_name,
                                    error=str(e),
                                )

                self._loaded = True
                logger.info(
                    "Search catalog loaded",
                    site_id=self.site_id,
                    record_types=len(self._record_types),
                    total_searches=sum(len(s) for s in self._searches.values()),
                )
            except Exception as e:
                logger.error("Failed to load catalog", site_id=self.site_id, error=str(e))
                raise

    def get_record_types(self) -> list[dict[str, Any]]:
        """Get all record types."""
        return self._record_types

    def get_searches(self, record_type: str) -> list[dict[str, Any]]:
        """Get searches for a record type."""
        return self._searches.get(record_type, [])

    def find_search(
        self, record_type: str, search_name: str
    ) -> dict[str, Any] | None:
        """Find a specific search."""
        searches = self.get_searches(record_type)
        for search in searches:
            if search.get("urlSegment") == search_name:
                return search
        return None

    async def get_search_details(
        self,
        client: VEuPathDBClient,
        record_type: str,
        search_name: str,
        expand_params: bool = True,
    ) -> dict[str, Any]:
        """Get detailed search config with caching."""
        cache_key = f"{record_type}/{search_name}?expand={int(expand_params)}"

        if cache_key not in self._search_details:
            details = await client.get_search_details(
                record_type, search_name, expand_params=expand_params
            )
            self._search_details[cache_key] = details

        return self._search_details[cache_key]


class DiscoveryService:
    """Service for discovering and caching site metadata."""

    def __init__(self) -> None:
        self._catalogs: dict[str, SearchCatalog] = {}
        self._lock = asyncio.Lock()

    async def get_catalog(self, site_id: str) -> SearchCatalog:
        """Get or create catalog for a site."""
        async with self._lock:
            if site_id not in self._catalogs:
                self._catalogs[site_id] = SearchCatalog(site_id)

        catalog = self._catalogs[site_id]

        if not catalog._loaded:
            router = get_site_router()
            client = router.get_client(site_id)
            await catalog.load(client)

        return catalog

    async def get_record_types(self, site_id: str) -> list[dict[str, Any]]:
        """Get record types for a site."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_record_types()

    async def get_searches(
        self, site_id: str, record_type: str
    ) -> list[dict[str, Any]]:
        """Get searches for a record type."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_searches(record_type)

    async def get_search_details(
        self,
        site_id: str,
        record_type: str,
        search_name: str,
        expand_params: bool = True,
    ) -> dict[str, Any]:
        """Get detailed search configuration."""
        catalog = await self.get_catalog(site_id)
        router = get_site_router()
        client = router.get_client(site_id)
        return await catalog.get_search_details(
            client,
            record_type,
            search_name,
            expand_params=expand_params,
        )

    async def preload_all(self) -> None:
        """Preload catalogs for all sites."""
        router = get_site_router()
        sites = router.list_sites()

        async def load_site(site_id: str) -> None:
            try:
                await self.get_catalog(site_id)
            except Exception as e:
                logger.warning("Failed to preload site", site_id=site_id, error=str(e))

        await asyncio.gather(*[load_site(s.id) for s in sites])


# Global discovery service
_discovery: DiscoveryService | None = None


def get_discovery_service() -> DiscoveryService:
    """Get the global discovery service."""
    global _discovery
    if _discovery is None:
        _discovery = DiscoveryService()
    return _discovery

