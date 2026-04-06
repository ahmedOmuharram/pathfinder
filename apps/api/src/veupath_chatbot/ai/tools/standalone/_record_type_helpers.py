"""Record type resolution and search catalog lookup helpers.

Functions that resolve record types from user input, find which
record type owns a given search, and interact with the discovery
service catalog.
"""

from veupath_chatbot.ai.tools.standalone._validation_helpers import get_graph
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.discovery import SearchCatalog
from veupath_chatbot.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.wdk.record_types import resolve_record_type

logger = get_logger(__name__)


def infer_record_type(session: StrategySession, step: PlanStepNode) -> str | None:
    # Plan steps no longer store record_type; prefer graph-level context when available.
    graph = get_graph(session, None)
    return graph.record_type if graph else None


async def get_catalog(site_id: str) -> SearchCatalog:
    """Get the search catalog for the given site."""
    discovery = get_discovery_service()
    return await discovery.get_catalog(site_id)


async def resolve_record_type_value(
    site_id: str, record_type: str | None
) -> str | None:
    if not record_type:
        return record_type
    catalog = await get_catalog(site_id)
    return resolve_record_type(catalog.get_record_types(), record_type) or record_type


async def find_record_type_for_search(
    site_id: str,
    record_type: str | None,
    search_name: str | None,
    *,
    require_match: bool = False,
    allow_fallback: bool = True,
) -> str | None:
    resolved = await resolve_record_type_value(site_id, record_type)
    if not search_name:
        return resolved
    return await lookup_record_type_for_search(
        site_id,
        search_name,
        resolved,
        require_match=require_match,
        allow_fallback=allow_fallback,
    )


async def lookup_record_type_for_search(
    site_id: str,
    search_name: str,
    resolved: str | None,
    *,
    require_match: bool,
    allow_fallback: bool,
) -> str | None:
    catalog = await get_catalog(site_id)
    # Prefer "transcript" over "gene" when the search exists under both.
    # In VEuPathDB, transcript is the superset record type — gene searches
    # that live under both types produce correct results only under
    # transcript for strategy building.
    if resolved == "gene" and catalog.find_search("transcript", search_name):
        return "transcript"
    # Fast path: search exists in the resolved record type.
    if resolved and catalog.find_search(resolved, search_name):
        return resolved
    if not allow_fallback:
        return None if require_match else resolved
    # Global lookup across all record types.
    found = catalog.find_record_type_for_search(search_name)
    return found or (None if require_match else resolved)


def scan_record_type_excluding(
    catalog: SearchCatalog, search_name: str, exclude: str
) -> str | None:
    """Scan all record types except *exclude* for a search match."""
    for rt_name in catalog._searches:
        if rt_name != exclude and catalog.find_search(rt_name, search_name):
            return rt_name
    return None


async def find_record_type_hint(
    site_id: str, search_name: str, exclude: str | None = None
) -> str | None:
    try:
        catalog = await get_catalog(site_id)
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
    if found and exclude and found == exclude:
        return scan_record_type_excluding(catalog, search_name, exclude)
    return found
