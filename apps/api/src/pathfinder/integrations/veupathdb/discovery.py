"""SearchCatalog: cached catalog of searches, parameters, and metadata for a site."""

import asyncio
from collections.abc import Sequence

from pathfinder.integrations.veupathdb.catalog_metadata import (
    load_dataset_metadata,
    load_ontology_categories,
    load_searches_for_rt,
    process_record_type_entry,
)
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.disk_cache import (
    CatalogSnapshot,
    save_catalog_cache,
    try_load_catalog_cache,
)
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tasks import spawn

logger = get_logger(__name__)


class SearchCatalog:
    """Cached catalog of searches for a site."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self._record_types: list[WDKRecordType] = []
        self._searches: dict[str, list[WDKSearch]] = {}
        self._search_details: dict[str, WDKSearchResponse] = {}
        self._dataset_summaries: dict[str, str] = {}
        self._dataset_contacts: dict[str, str] = {}
        self._semantic_index: object | None = None
        self._search_categories: dict[str, str] = {}
        self._available_categories: set[str] = set()
        self._loaded = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def _restore_from_snapshot(self, snapshot: CatalogSnapshot) -> None:
        """Populate in-memory state from a cached snapshot."""
        self._record_types = snapshot.record_types
        self._searches = snapshot.searches
        self._dataset_summaries = snapshot.dataset_summaries
        self._dataset_contacts = snapshot.dataset_contacts
        self._search_categories = snapshot.search_categories
        self._available_categories = set(snapshot.available_categories)

    def _to_snapshot(self) -> CatalogSnapshot:
        """Capture current in-memory state as a serializable snapshot."""
        return CatalogSnapshot(
            record_types=self._record_types,
            searches=self._searches,
            dataset_summaries=self._dataset_summaries,
            dataset_contacts=self._dataset_contacts,
            search_categories=self._search_categories,
            available_categories=sorted(self._available_categories),
        )

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    async def _fetch_from_api(self, client: VEuPathDBClient) -> None:
        """Fetch catalog data from the live WDK API and save to disk cache."""
        record_types = await client.get_record_types(expanded=True)
        expanded_supported = any(rt.searches is not None for rt in record_types)

        self._record_types = []
        self._searches = {}
        await self._populate_from_record_types(
            client, record_types, expanded_supported=expanded_supported
        )

        ds = await load_dataset_metadata(client, self.site_id)
        self._dataset_summaries = ds.summaries
        self._dataset_contacts = ds.contacts

        onto = await load_ontology_categories(client, self.site_id)
        self._search_categories = onto.search_categories
        self._available_categories = onto.available_categories

        self._semantic_index = self._build_semantic_index()
        save_catalog_cache(self.site_id, self._to_snapshot())

    async def load(self, client: VEuPathDBClient) -> None:
        """Load catalog -- from disk cache if fresh, otherwise from VEuPathDB.

        Fresh cache (< 1 week): serve immediately, no API calls.
        Stale cache (>= 1 week): serve immediately for fast startup,
            then refresh from the API in the background.
        No cache: fetch from API synchronously (blocks until ready).
        """
        async with self._lock:
            if self._loaded:
                return

            snapshot = try_load_catalog_cache(self.site_id)

            if snapshot is not None:
                self._restore_from_snapshot(snapshot)
                self._build_semantic_index()
                self._loaded = True

                if snapshot.is_stale:
                    logger.info(
                        "Search catalog restored from stale cache, refreshing in background",
                        site_id=self.site_id,
                    )
                    spawn(self._background_refresh(client), name=f"catalog-refresh-{self.site_id}")
                else:
                    logger.info(
                        "Search catalog restored from cache",
                        site_id=self.site_id,
                        record_types=len(self._record_types),
                        total_searches=sum(len(s) for s in self._searches.values()),
                    )
                return

            # Cache miss -- must fetch synchronously.
            logger.info("Loading search catalog from API", site_id=self.site_id)
            try:
                await self._fetch_from_api(client)
                self._loaded = True
                logger.info(
                    "Search catalog loaded from API and cached",
                    site_id=self.site_id,
                    record_types=len(self._record_types),
                    total_searches=sum(len(s) for s in self._searches.values()),
                    datasets=len(self._dataset_summaries),
                )
            except (AppError, OSError, RuntimeError) as e:
                logger.exception(
                    "Failed to load catalog", site_id=self.site_id, error=str(e)
                )
                raise

    async def _background_refresh(self, client: VEuPathDBClient) -> None:
        """Re-fetch catalog from the API in the background, replacing in-memory state."""
        try:
            await self._fetch_from_api(client)
            logger.info(
                "Search catalog background refresh complete",
                site_id=self.site_id,
                record_types=len(self._record_types),
                total_searches=sum(len(s) for s in self._searches.values()),
            )
        except (AppError, OSError, RuntimeError):
            logger.warning(
                "Background catalog refresh failed (serving stale cache)",
                site_id=self.site_id,
                exc_info=True,
            )

    def _build_semantic_index(self) -> None:
        """Build semantic search index from cached searches + dataset metadata."""
        # Deferred import: services.catalog.__init__ re-exports param_resolution
        # which imports discovery_service, creating a circular dependency at
        # module load time.  Safe here because this only runs at catalog-load time.
        from pathfinder.services.catalog.semantic_index import (  # noqa: PLC0415
            SemanticSearchIndex,
        )

        try:
            index = SemanticSearchIndex(site_id=self.site_id)
            index.build(
                self._searches,
                dataset_summaries=self._dataset_summaries,
                dataset_contacts=self._dataset_contacts,
            )
        except (AppError, OSError, ValueError, TypeError):
            logger.warning(
                "Failed to build semantic index (non-fatal)",
                site_id=self.site_id,
                exc_info=True,
            )
        else:
            self._semantic_index = index

    # ------------------------------------------------------------------
    # Record type / search population
    # ------------------------------------------------------------------

    async def _populate_from_record_types(
        self,
        client: VEuPathDBClient,
        record_types: Sequence[WDKRecordType],
        *,
        expanded_supported: bool,
    ) -> None:
        """Populate internal caches from the record types array."""
        for rt in record_types:
            result = process_record_type_entry(
                rt, expanded_supported=expanded_supported
            )
            if result is None:
                continue

            typed_rt, searches = result
            rt_name = typed_rt.url_segment
            self._record_types.append(typed_rt)

            if searches is not None and len(searches) > 0:
                self._searches[rt_name] = searches
            else:
                fetched = await load_searches_for_rt(client, rt_name)
                if fetched is not None:
                    self._searches[rt_name] = fetched

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def get_record_types(self) -> list[WDKRecordType]:
        """Get all record types."""
        return self._record_types

    def get_searches(self, record_type: str) -> list[WDKSearch]:
        """Get searches for a record type."""
        return self._searches.get(record_type, [])

    def get_semantic_index(self) -> object | None:
        """Get the semantic search index, or None if not available."""
        return self._semantic_index

    def find_search(self, record_type: str, search_name: str) -> WDKSearch | None:
        """Find a specific search."""
        for search in self.get_searches(record_type):
            if search.url_segment == search_name:
                return search
        return None

    def find_record_type_for_search(self, search_name: str) -> str | None:
        """Find which record type owns a search (global lookup).

        Mirrors WDK's ``WdkModel.getQuestionByName()`` -- iterates all cached
        record types to find the one containing the given search.
        """
        for rt_name, searches in self._searches.items():
            if any(s.url_segment == search_name for s in searches):
                return rt_name
        return None

    def get_search_category(self, search_name: str) -> str | None:
        """Get the ontology subcategory for a search, or None if universal."""
        return self._search_categories.get(search_name)

    def get_available_categories(self) -> set[str]:
        """Get all available searchCategory-* subcategories for this site."""
        return self._available_categories

    async def get_search_details(
        self,
        client: VEuPathDBClient,
        record_type: str,
        search_name: str,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Get detailed search config with caching."""
        cache_key = f"{record_type}/{search_name}?expand={int(expand_params)}"
        if cache_key not in self._search_details:
            details = await client.get_search_details(
                record_type, search_name, expand_params=expand_params
            )
            self._search_details[cache_key] = details
        return self._search_details[cache_key]
