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
        return await catalog.list_searches(site_id, record_type)

    @ai_function()
    async def get_search_parameters(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID")],
        record_type: Annotated[str, AIParam(desc="Record type")],
        search_name: Annotated[str, AIParam(desc="Search name")],
    ) -> JSONObject:
        return await catalog.get_search_parameters_tool(
            site_id, record_type, search_name
        )

    @ai_function()
    async def search_for_searches(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID")],
        query: Annotated[str, AIParam(desc="Search term to find relevant searches")],
    ) -> list[dict[str, str]]:
        # Search broadly across record types for better recall.
        return await catalog.search_for_searches(site_id, record_type=None, query=query)
