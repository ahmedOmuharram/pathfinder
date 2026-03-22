"""Catalog services: sites, record types, searches, parameter metadata, RAG.

Single source of truth for catalog/discovery logic used by both:
- HTTP transport (`transport/http/routers/sites.py`)
- AI tools (`ai/tools/catalog_tools.py`, `ai/tools/catalog_rag_tools.py`, etc.)
"""

from veupath_chatbot.services.catalog.models import RecordTypeInfo
from veupath_chatbot.services.catalog.parameters import (
    expand_search_details_with_params,
    get_refreshed_dependent_params,
    get_search_parameters,
    get_search_parameters_tool,
    lookup_phyletic_codes,
    validate_search_params,
)
from veupath_chatbot.services.catalog.rag_search import RagSearchService
from veupath_chatbot.services.catalog.searches import (
    get_raw_record_types,
    get_raw_searches,
    list_searches,
    list_transforms,
    search_for_searches,
)
from veupath_chatbot.services.catalog.sites import (
    get_record_types,
    list_sites,
)

__all__ = [
    "RagSearchService",
    "RecordTypeInfo",
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
