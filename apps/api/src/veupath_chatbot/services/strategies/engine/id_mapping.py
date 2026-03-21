"""WDK ID <-> local ID mapping and record-type resolution."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.discovery import (
    SearchCatalog,
    get_discovery_service,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.wdk.record_types import resolve_record_type

from .base import StrategyToolsBase

logger = get_logger(__name__)


class IdMappingMixin(StrategyToolsBase):
    def _infer_record_type(self, step: PlanStepNode) -> str | None:
        # Plan steps no longer store record_type; prefer graph-level context when available.
        graph = self._get_graph(None)
        return graph.record_type if graph else None

    async def _get_catalog(self) -> SearchCatalog:
        """Get the search catalog for the current site."""
        discovery = get_discovery_service()
        return await discovery.get_catalog(self.session.site_id)

    async def _resolve_record_type(self, record_type: str | None) -> str | None:
        if not record_type:
            return record_type
        catalog = await self._get_catalog()
        return (
            resolve_record_type(catalog.get_record_types(), record_type) or record_type
        )

    async def _find_record_type_for_search(
        self,
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = True,
    ) -> str | None:
        resolved = await self._resolve_record_type(record_type)
        if not search_name:
            return resolved
        return await self._lookup_record_type_for_search(
            search_name,
            resolved,
            require_match=require_match,
            allow_fallback=allow_fallback,
        )

    async def _lookup_record_type_for_search(
        self,
        search_name: str,
        resolved: str | None,
        *,
        require_match: bool,
        allow_fallback: bool,
    ) -> str | None:
        catalog = await self._get_catalog()
        # Fast path: search exists in the resolved record type.
        if resolved and catalog.find_search(resolved, search_name):
            return resolved
        if not allow_fallback:
            return None if require_match else resolved
        # Global lookup across all record types.
        found = catalog.find_record_type_for_search(search_name)
        return found or (None if require_match else resolved)

    def _scan_record_type_excluding(
        self, catalog: SearchCatalog, search_name: str, exclude: str
    ) -> str | None:
        """Scan all record types except *exclude* for a search match."""
        for rt_name in catalog._searches:
            if rt_name != exclude and catalog.find_search(rt_name, search_name):
                return rt_name
        return None

    async def _find_record_type_hint(
        self, search_name: str, exclude: str | None = None
    ) -> str | None:
        try:
            catalog = await self._get_catalog()
        except AppError as exc:
            logger.warning(
                "Failed to fetch search catalog for record type hint",
                search_name=search_name,
                error=str(exc),
            )
            return None

        found = catalog.find_record_type_for_search(search_name)
        # If the result matches the excluded record type, fall back to
        # manual scanning (the catalog only returns the first match).
        if found and found == exclude:
            return self._scan_record_type_excluding(catalog, search_name, exclude)
        return found
