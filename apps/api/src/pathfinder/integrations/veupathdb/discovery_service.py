"""Global DiscoveryService: manages per-site SearchCatalog instances."""

import asyncio
import threading

from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.discovery import SearchCatalog
from pathfinder.integrations.veupathdb.site_router import SiteInfo, get_site_router
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tasks import spawn

logger = get_logger(__name__)


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
        router = get_site_router()
        client = router.get_client(site_id)
        await catalog.load(client)

        return catalog

    async def get_record_types(self, site_id: str) -> list[WDKRecordType]:
        """Get record types for a site."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_record_types()

    async def get_searches(self, site_id: str, record_type: str) -> list[WDKSearch]:
        """Get searches for a record type."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_searches(record_type)

    async def get_search_details(
        self,
        ctx: SearchContext,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Get detailed search configuration."""
        catalog = await self.get_catalog(ctx.site_id)
        router = get_site_router()
        client = router.get_client(ctx.site_id)
        return await catalog.get_search_details(
            client,
            ctx.record_type,
            ctx.search_name,
            expand_params=expand_params,
        )

    async def preload_all(self) -> None:
        """Preload catalogs for all sites.

        Component sites are loaded in parallel (blocking). The portal
        is deferred to a background task since its 2400+ search catalog
        takes ~90s to fetch and would block startup.
        """
        router = get_site_router()
        sites = router.list_sites()

        component: list[SiteInfo] = []
        portal: list[SiteInfo] = []
        for s in sites:
            (portal if s.is_portal else component).append(s)

        async def load_site(site_id: str) -> None:
            try:
                logger.info("[warm-up] Preloading %s", site_id)
                await self.get_catalog(site_id)
                logger.info("[warm-up] Preloaded %s", site_id)
            except (AppError, OSError, RuntimeError) as e:
                logger.warning("[warm-up] Failed %s: %s", site_id, e)

        # Component sites: load sequentially to avoid OOM during embedding.
        for s in component:
            await load_site(s.id)

        # Portal: slow, run in background so the API is ready immediately.
        for s in portal:
            spawn(load_site(s.id), name=f"preload-{s.id}")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_discovery_holder: dict[str, DiscoveryService] = {}
_discovery_lock = threading.Lock()


def get_discovery_service() -> DiscoveryService:
    """Get the global discovery service."""
    if "v" in _discovery_holder:
        return _discovery_holder["v"]
    with _discovery_lock:
        if "v" not in _discovery_holder:
            _discovery_holder["v"] = DiscoveryService()
        return _discovery_holder["v"]
