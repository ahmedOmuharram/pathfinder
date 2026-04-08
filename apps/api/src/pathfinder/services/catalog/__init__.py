"""Catalog services: sites, record types, searches, parameter metadata.

Single source of truth for catalog/discovery logic used by both:
- HTTP transport (`transport/http/routers/sites.py`)
- AI tools (`ai/tools/catalog_tools.py`, etc.)
"""

from pathfinder.services.catalog.models import RecordTypeInfo, SearchMatch
from pathfinder.services.catalog.parameters import (
    expand_search_details_with_params,
    get_refreshed_dependent_params,
    get_search_parameters,
    get_search_parameters_tool,
    lookup_phyletic_codes,
    validate_search_params,
)
from pathfinder.services.catalog.searches import (
    browse_search_categories,
    get_raw_record_types,
    get_raw_searches,
    list_searches,
    list_transforms,
    search_for_searches,
)
from pathfinder.services.catalog.sites import (
    get_record_types,
    list_sites,
)

__all__ = [
    "RecordTypeInfo",
    "SearchMatch",
    "browse_search_categories",
    "expand_search_details_with_params",
    "get_raw_record_types",
    "get_raw_searches",
    "get_record_types",
    "get_refreshed_dependent_params",
    "get_search_parameters",
    "get_search_parameters_tool",
    "list_searches",
    "list_sites",
    "list_transforms",
    "lookup_phyletic_codes",
    "search_for_searches",
    "validate_search_params",
]
