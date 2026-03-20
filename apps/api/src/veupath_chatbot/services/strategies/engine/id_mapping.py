"""WDK ID <-> local ID mapping and record-type resolution."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.discovery import (
    SearchCatalog,
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_search_matches
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

        catalog = await self._get_catalog()

        # Fast path: search exists in the resolved record type.
        if resolved:
            searches = catalog.get_searches(resolved)
            if any(wdk_search_matches(s, search_name) for s in searches):
                return resolved
            if not allow_fallback:
                return None if require_match else resolved

        if not allow_fallback:
            return None if require_match else resolved

        # Global lookup across all record types.
        found = catalog.find_record_type_for_search(search_name)
        if found:
            return found

        return None if require_match else resolved

    async def _find_record_type_hint(
        self, search_name: str, exclude: str | None = None
    ) -> str | None:
        try:
            catalog = await self._get_catalog()
        except (AppError, ValueError, TypeError) as exc:
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
            for rt_name, searches in catalog._searches.items():
                if rt_name == exclude:
                    continue
                if any(wdk_search_matches(s, search_name) for s in searches):
                    return rt_name
            return None

        return found
