"""Discovery and caching of record types, searches, and parameters."""

import asyncio
import threading
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo, get_site_router
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger

# ---------------------------------------------------------------------------
# Models for parsing the WDK dataset report (AllDatasets/reports/standard)
# ---------------------------------------------------------------------------


class _PkPart(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    value: str = ""


class _DatasetAttributes(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str | None = None
    contact: str | None = None


class _DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: list[_PkPart] = Field(default_factory=list)
    attributes: _DatasetAttributes = Field(default_factory=_DatasetAttributes)

    @property
    def dataset_id(self) -> str:
        for part in self.id:
            if part.name == "dataset_id":
                return part.value
        return self.id[0].value if self.id else ""

    def populate(
        self,
        summaries: dict[str, str],
        contacts: dict[str, str],
    ) -> None:
        """Write this record's summary/contact into the provided dicts."""
        ds_id = self.dataset_id
        if not ds_id:
            return
        if self.attributes.summary:
            summaries[ds_id] = self.attributes.summary
        if self.attributes.contact:
            contacts[ds_id] = self.attributes.contact


class _DatasetReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    records: list[_DatasetRecord] = Field(default_factory=list)

logger = get_logger(__name__)


async def _load_searches_for_rt(
    client: VEuPathDBClient, rt_name: str
) -> list[WDKSearch] | None:
    """Fetch searches for a record type, returning None on error."""
    try:
        return await client.get_searches(rt_name)
    except AppError as e:
        logger.warning(
            "Failed to load searches",
            record_type=rt_name,
            error=str(e),
        )
        return None


def _process_record_type_entry(
    rt: WDKRecordType,
    *,
    expanded_supported: bool,
) -> tuple[WDKRecordType, list[WDKSearch] | None] | None:
    """Extract (typed_rt, inline_searches) from a record type entry.

    Returns None if the entry should be skipped. Returns (model, None) when
    searches need to be fetched separately.
    """
    if not rt.url_segment:
        return None

    if expanded_supported and rt.searches is not None:
        return rt, rt.searches
    return rt, None


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
        self._loaded = False
        self._lock = asyncio.Lock()

    async def load(self, client: VEuPathDBClient) -> None:
        """Load catalog from VEuPathDB."""
        async with self._lock:
            if self._loaded:
                return

            logger.info("Loading search catalog", site_id=self.site_id)

            try:
                record_types = await client.get_record_types(expanded=True)
                expanded_supported = any(rt.searches is not None for rt in record_types)

                await self._populate_from_record_types(
                    client, record_types, expanded_supported=expanded_supported
                )

                await self._load_dataset_metadata(client)
                self._build_semantic_index()

                self._loaded = True
                logger.info(
                    "Search catalog loaded",
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

    async def _load_dataset_metadata(self, client: VEuPathDBClient) -> None:
        """Fetch all dataset summaries and contacts in one call."""
        try:
            report_config = {
                "attributes": ["primary_key", "summary", "contact"],
            }
            answer = await client.post(
                "/record-types/dataset/searches/AllDatasets/reports/standard",
                json={"searchConfig": {"parameters": {}}, "reportConfig": report_config},
            )
            report = _DatasetReport.model_validate(answer)
            for rec in report.records:
                rec.populate(self._dataset_summaries, self._dataset_contacts)
            logger.info(
                "Dataset metadata loaded",
                site_id=self.site_id,
                datasets=len(self._dataset_summaries),
            )
        except (AppError, OSError, ValueError, TypeError):
            logger.warning(
                "Failed to load dataset metadata (non-fatal)",
                site_id=self.site_id,
                exc_info=True,
            )

    def _build_semantic_index(self) -> None:
        """Build semantic search index from cached searches + dataset metadata."""
        try:
            from veupath_chatbot.services.catalog.semantic_index import (
                SemanticSearchIndex,
            )

            index = SemanticSearchIndex(site_id=self.site_id)
            index.build(
                self._searches,
                dataset_summaries=self._dataset_summaries,
                dataset_contacts=self._dataset_contacts,
            )
            self._semantic_index = index
        except (AppError, OSError, ValueError, TypeError):
            logger.warning(
                "Failed to build semantic index (non-fatal)",
                site_id=self.site_id,
                exc_info=True,
            )

    def get_semantic_index(self) -> object | None:
        """Get the semantic search index, or None if not available."""
        return self._semantic_index

    async def _populate_from_record_types(
        self,
        client: VEuPathDBClient,
        record_types: Sequence[WDKRecordType],
        *,
        expanded_supported: bool,
    ) -> None:
        """Populate internal caches from the record types array."""
        for rt in record_types:
            result = _process_record_type_entry(
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
                fetched = await _load_searches_for_rt(client, rt_name)
                if fetched is not None:
                    self._searches[rt_name] = fetched

    def get_record_types(self) -> list[WDKRecordType]:
        """Get all record types."""
        return self._record_types

    def get_searches(self, record_type: str) -> list[WDKSearch]:
        """Get searches for a record type.

        :param record_type: WDK record type.

        """
        return self._searches.get(record_type, [])

    def find_search(self, record_type: str, search_name: str) -> WDKSearch | None:
        """Find a specific search.

        :param record_type: WDK record type.
        :param search_name: WDK search name.

        """
        for search in self.get_searches(record_type):
            if search.url_segment == search_name:
                return search
        return None

    def find_record_type_for_search(self, search_name: str) -> str | None:
        """Find which record type owns a search (global lookup).

        Mirrors WDK's ``WdkModel.getQuestionByName()`` — iterates all cached
        record types to find the one containing the given search.

        :param search_name: WDK search name (urlSegment).
        :returns: The record type name, or None if not found.
        """
        for rt_name, searches in self._searches.items():
            if any(s.url_segment == search_name for s in searches):
                return rt_name
        return None

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
                print(f"[warm-up] Preloading {site_id}", flush=True)
                await self.get_catalog(site_id)
                print(f"[warm-up] Preloaded {site_id}", flush=True)
            except (AppError, OSError, RuntimeError) as e:
                print(f"[warm-up] Failed {site_id}: {e}", flush=True)

        # Component sites: fast, block startup.
        await asyncio.gather(*[load_site(s.id) for s in component])

        # Portal: slow, run in background so the API is ready immediately.
        for s in portal:
            asyncio.create_task(load_site(s.id))


# Global discovery service
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
