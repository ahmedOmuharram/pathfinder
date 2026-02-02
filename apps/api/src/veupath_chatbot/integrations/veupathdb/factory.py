"""Integration entrypoints for WDK clients and services."""

from __future__ import annotations

from veupath_chatbot.integrations.veupathdb.discovery import (
    DiscoveryService,
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo, get_site_router
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI


def get_wdk_client(site_id: str):
    """Get a raw WDK client for a site."""
    router = get_site_router()
    return router.get_client(site_id)


def get_site(site_id: str):
    """Get site metadata by ID."""
    router = get_site_router()
    return router.get_site(site_id)


__all__ = [
    "DiscoveryService",
    "SiteInfo",
    "close_all_clients",
    "get_discovery",
    "get_discovery_service",
    "get_results_api",
    "get_site",
    "get_strategy_api",
    "get_wdk_client",
    "list_sites",
]


def list_sites():
    """List all known sites."""
    router = get_site_router()
    return router.list_sites()


def get_strategy_api(site_id: str) -> StrategyAPI:
    """Get a Strategy API wrapper for a site."""
    return StrategyAPI(get_wdk_client(site_id))


def get_results_api(site_id: str) -> TemporaryResultsAPI:
    """Get a temporary results API wrapper for a site."""
    return TemporaryResultsAPI(get_wdk_client(site_id))


def get_discovery(site_id: str | None = None) -> DiscoveryService:
    """Get the shared discovery service (site_id reserved for future use)."""
    del site_id
    return get_discovery_service()


async def close_all_clients() -> None:
    """Close all cached WDK clients."""
    router = get_site_router()
    await router.close_all()
