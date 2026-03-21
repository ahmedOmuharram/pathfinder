"""WDK service-layer entry points.

Re-exports WDK client factories and types so that AI tools and other
higher-level consumers import from ``services.wdk`` instead of reaching
into ``integrations.veupathdb`` directly.
"""

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.discovery import (
    DiscoveryService,
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.factory import (
    get_results_api,
    get_site,
    get_strategy_api,
    get_wdk_client,
    list_sites,
)
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI

__all__ = [
    "DiscoveryService",
    "SiteInfo",
    "StrategyAPI",
    "TemporaryResultsAPI",
    "VEuPathDBClient",
    "encode_context_param_values_for_wdk",
    "get_discovery_service",
    "get_results_api",
    "get_site",
    "get_strategy_api",
    "get_wdk_client",
    "is_internal_wdk_strategy_name",
    "list_sites",
    "strip_internal_wdk_strategy_name",
]
