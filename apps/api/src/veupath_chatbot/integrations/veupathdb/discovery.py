"""Discovery and caching of record types, searches, and parameters."""

import asyncio
import threading

import httpx

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.param_utils import (
    wdk_entity_name,
    wdk_search_matches,
)
from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


def _unwrap_record_types(raw_record_types: JSONArray | JSONObject) -> JSONArray:
    """Unwrap record types from the WDK response.

    WDK's record-types endpoint returns an array directly, but some
    deployments wrap it under ``"recordTypes"``.

    :raises DataParsingError: If the response is a dict without a ``recordTypes`` list.
    """
    if isinstance(raw_record_types, dict):
        wrapped = raw_record_types.get("recordTypes")
        if isinstance(wrapped, list):
            return wrapped
        msg = (
            f"Unexpected record-types response shape: "
            f"dict without 'recordTypes' list (keys: {list(raw_record_types.keys())})"
        )
        raise DataParsingError(msg)
    return raw_record_types


async def _load_searches_for_rt(
    client: VEuPathDBClient, rt_name: str
) -> JSONArray | None:
    """Fetch searches for a record type, returning None on error."""
    try:
        return await client.get_searches(rt_name)
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as e:
        logger.warning(
            "Failed to load searches",
            record_type=rt_name,
            error=str(e),
        )
        return None


def _process_record_type_entry(
    rt: object,
    *,
    expanded_supported: bool,
) -> tuple[str, JSONArray | None] | None:
    """Extract (rt_name, inline_searches) from a record type entry.

    Returns None if the entry should be skipped. Returns (name, None) when
    searches need to be fetched separately.
    """
    if isinstance(rt, str):
        return rt, []
    if isinstance(rt, dict):
        rt_name = wdk_entity_name(rt)
        if not rt_name:
            return None
        searches_raw = rt.get("searches") if expanded_supported else None
        if isinstance(searches_raw, list):
            return rt_name, searches_raw
        return rt_name, None
    return None


class SearchCatalog:
    """Cached catalog of searches for a site."""

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self._record_types: JSONArray = []
        self._searches: dict[str, JSONArray] = {}
        self._search_details: dict[str, JSONObject] = {}
        self._loaded = False
        self._lock = asyncio.Lock()

    async def load(self, client: VEuPathDBClient) -> None:
        """Load catalog from VEuPathDB."""
        async with self._lock:
            if self._loaded:
                return

            logger.info("Loading search catalog", site_id=self.site_id)

            try:
                raw_record_types = await client.get_record_types(expanded=True)
                unwrapped = _unwrap_record_types(raw_record_types)
                expanded_supported = any(
                    isinstance(rt, dict) and "searches" in rt for rt in unwrapped
                )

                await self._populate_from_record_types(
                    client, unwrapped, expanded_supported=expanded_supported
                )

                self._loaded = True
                logger.info(
                    "Search catalog loaded",
                    site_id=self.site_id,
                    record_types=len(self._record_types),
                    total_searches=sum(len(s) for s in self._searches.values()),
                )
            except (
                httpx.HTTPError,
                OSError,
                RuntimeError,
                TypeError,
                DataParsingError,
            ) as e:
                logger.exception(
                    "Failed to load catalog", site_id=self.site_id, error=str(e)
                )
                raise

    async def _populate_from_record_types(
        self,
        client: VEuPathDBClient,
        record_types: JSONArray,
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

            rt_name, searches = result
            if isinstance(rt, str):
                self._record_types.append({"urlSegment": rt, "name": rt})
            elif isinstance(rt, dict):
                self._record_types.append(rt)

            if searches is not None and searches != []:
                self._searches[rt_name] = searches
            else:
                fetched = await _load_searches_for_rt(client, rt_name)
                if fetched is not None:
                    self._searches[rt_name] = fetched

    def get_record_types(self) -> JSONArray:
        """Get all record types."""
        return self._record_types

    def get_searches(self, record_type: str) -> JSONArray:
        """Get searches for a record type.

        :param record_type: WDK record type.

        """
        return self._searches.get(record_type, [])

    def find_search(self, record_type: str, search_name: str) -> JSONObject | None:
        """Find a specific search.

        :param record_type: WDK record type.
        :param search_name: WDK search name.

        """
        searches = self.get_searches(record_type)
        for search in searches:
            if not isinstance(search, dict):
                continue
            if wdk_entity_name(search) == search_name:
                return search
        return None

    def find_record_type_for_search(self, search_name: str) -> str | None:
        """Find which record type owns a search (global lookup).

        Mirrors WDK's ``WdkModel.getQuestionByName()`` — iterates all cached
        record types to find the one containing the given search.

        :param search_name: WDK search name (urlSegment or name).
        :returns: The record type name, or None if not found.
        """
        for rt_name, searches in self._searches.items():
            if any(wdk_search_matches(s, search_name) for s in searches):
                return rt_name
        return None

    async def get_search_details(
        self,
        client: VEuPathDBClient,
        record_type: str,
        search_name: str,
        *,
        expand_params: bool = True,
    ) -> JSONObject:
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

    async def get_record_types(self, site_id: str) -> JSONArray:
        """Get record types for a site."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_record_types()

    async def get_searches(self, site_id: str, record_type: str) -> JSONArray:
        """Get searches for a record type."""
        catalog = await self.get_catalog(site_id)
        return catalog.get_searches(record_type)

    async def get_search_details(
        self,
        ctx: SearchContext,
        *,
        expand_params: bool = True,
    ) -> JSONObject:
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
        """Preload catalogs for all sites."""
        router = get_site_router()
        sites = router.list_sites()

        async def load_site(site_id: str) -> None:
            try:
                await self.get_catalog(site_id)
            except (
                httpx.HTTPError,
                OSError,
                RuntimeError,
                TypeError,
                DataParsingError,
            ) as e:
                logger.warning("Failed to preload site", site_id=site_id, error=str(e))

        await asyncio.gather(*[load_site(s.id) for s in sites])


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
