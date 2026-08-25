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
from pathfinder.services.catalog.search_inspection import (
    SearchInspection,
    UnknownSearchError,
    inspect_search,
    read_parameter_options,
)
from pathfinder.services.catalog.searches import (
    SearchQueryRejection,
    VagueSearchQueryError,
    browse_search_categories,
    get_raw_record_types,
    get_raw_searches,
    list_searches,
    list_transforms,
    read_search_definition,
    resolve_search_record_type,
    search_for_searches,
)
from pathfinder.services.catalog.sites import (
    get_record_types,
    list_sites,
)

__all__ = [
    "RecordTypeInfo",
    "SearchInspection",
    "SearchMatch",
    "SearchQueryRejection",
    "UnknownSearchError",
    "VagueSearchQueryError",
    "browse_search_categories",
    "expand_search_details_with_params",
    "get_raw_record_types",
    "get_raw_searches",
    "get_record_types",
    "get_refreshed_dependent_params",
    "get_search_parameters",
    "get_search_parameters_tool",
    "inspect_search",
    "list_searches",
    "list_sites",
    "list_transforms",
    "lookup_phyletic_codes",
    "read_parameter_options",
    "read_search_definition",
    "resolve_search_record_type",
    "search_for_searches",
    "validate_search_params",
]
