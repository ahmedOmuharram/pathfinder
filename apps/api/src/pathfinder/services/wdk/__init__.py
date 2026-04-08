"""WDK service-layer entry points.

Re-exports WDK client factories and types so that AI tools and other
higher-level consumers import from ``services.wdk`` instead of reaching
into ``integrations.veupathdb`` directly.
"""

from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.discovery_service import (
    DiscoveryService,
    get_discovery_service,
)
from pathfinder.integrations.veupathdb.factory import (
    get_results_api,
    get_site,
    get_strategy_api,
    get_wdk_client,
    list_sites,
)
from pathfinder.integrations.veupathdb.site_router import SiteInfo
from pathfinder.integrations.veupathdb.strategy_api import (
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from pathfinder.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from pathfinder.integrations.veupathdb.wdk_models import encode_wdk_params

__all__ = [
    "DiscoveryService",
    "SiteInfo",
    "StrategyAPI",
    "TemporaryResultsAPI",
    "VEuPathDBClient",
    "encode_wdk_params",
    "get_discovery_service",
    "get_results_api",
    "get_site",
    "get_strategy_api",
    "get_wdk_client",
    "is_internal_wdk_strategy_name",
    "list_sites",
    "strip_internal_wdk_strategy_name",
]
