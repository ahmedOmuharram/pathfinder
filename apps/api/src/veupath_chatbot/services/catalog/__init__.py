"""Catalog services: sites, record types, searches, parameter metadata.

Single source of truth for catalog/discovery logic used by both:
- HTTP transport (`transport/http/routers/sites.py`)
- AI tools (`ai/tools/catalog_tools.py`)
"""

from veupath_chatbot.services.catalog.parameters import (
    expand_search_details_with_params,
    get_search_parameters,
    get_search_parameters_tool,
    validate_search_params,
)
from veupath_chatbot.services.catalog.searches import (
    list_searches,
    search_for_searches,
)
from veupath_chatbot.services.catalog.sites import (
    get_record_types,
    list_sites,
)

__all__ = [
    "expand_search_details_with_params",
    "get_record_types",
    "get_search_parameters",
    "get_search_parameters_tool",
    "list_searches",
    "list_sites",
    "search_for_searches",
    "validate_search_params",
]
