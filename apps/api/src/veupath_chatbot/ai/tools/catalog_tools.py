"""AI tool wrappers for catalog/discovery.

The underlying logic lives in `veupath_chatbot.services.catalog` to keep things DRY.
"""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services import catalog


class CatalogTools:
    """Tools for exploring VEuPathDB catalog."""

    @ai_function()
    async def list_sites(self) -> JSONArray:
        return await catalog.list_sites()

    @ai_function()
    async def get_record_types(
        self,
        site_id: Annotated[
            str,
            AIParam(desc="Site ID (e.g., 'plasmodb', 'toxodb', 'veupathdb')"),
        ],
    ) -> JSONArray:
        return await catalog.get_record_types(site_id)

    @ai_function()
    async def search_for_searches(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID")],
        query: Annotated[str, AIParam(desc="Search term to find relevant searches")],
    ) -> list[dict[str, str]]:
        """Find searches by keyword — returns names, display names, AND descriptions.

        This is the PRIMARY search discovery tool. Always try this FIRST to find
        the right search. Returns up to 20 targeted results with full descriptions
        to help you pick the right search.

        Only fall back to list_searches if this returns no results.
        """
        # Search broadly across record types for better recall.
        return await catalog.search_for_searches(site_id, record_type=None, query=query)

    @ai_function()
    async def list_searches(
        self,
        site_id: Annotated[
            str,
            AIParam(desc="Site ID (e.g., 'plasmodb')"),
        ],
        record_type: Annotated[
            str,
            AIParam(desc="Record type (e.g., 'gene', 'transcript')"),
        ],
    ) -> list[dict[str, str]]:
        """List all search names for a record type (names only, no descriptions).

        Returns a lightweight index of search names. Use search_for_searches first
        for targeted discovery with descriptions. Use get_search_parameters to get
        full details (description + parameters) for a specific search.
        """
        return await catalog.list_searches(site_id, record_type)

    @ai_function()
    async def get_search_parameters(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID")],
        record_type: Annotated[str, AIParam(desc="Record type")],
        search_name: Annotated[str, AIParam(desc="Search name")],
    ) -> JSONObject:
        """Get full details for a specific search: description, parameters, and valid values."""
        return await catalog.get_search_parameters_tool(
            site_id, record_type, search_name
        )

    @ai_function()
    async def lookup_phyletic_codes(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID (e.g., 'plasmodb')")],
        record_type: Annotated[str, AIParam(desc="Record type (usually 'transcript')")],
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Species or clade name to search for "
                    "(e.g., 'falciparum', 'human', 'Apicomplexa'). "
                    "Returns matching codes for use in profile_pattern."
                )
            ),
        ],
    ) -> JSONObject:
        """Look up phyletic species codes by name for GenesByOrthologPattern.

        Returns {code, label} pairs. Use the codes in profile_pattern:
        CODE>=1T (include) or CODE=0T (exclude).
        Example: lookup 'falciparum' → pfal, then use 'pfal>=1T' in profile_pattern.
        """
        return await catalog.lookup_phyletic_codes(site_id, record_type, query)
