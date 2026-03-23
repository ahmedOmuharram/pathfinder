"""AI tool wrappers for catalog/discovery — single layer, WDK-direct.

Every tool operates on the session's site. The model never passes site_id.
"""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.query_validation import (
    search_query_error,
)
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.factory import (
    get_strategy_api,
    get_wdk_client,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services import catalog
from veupath_chatbot.services.catalog.public_strategy_search import (
    rank_public_strategies,
)

logger = get_logger(__name__)


class CatalogTools:
    """Tools for exploring VEuPathDB catalog.

    Constructed with the session's ``site_id`` — every tool uses it implicitly.
    """

    def __init__(self, site_id: str) -> None:
        self.site_id = site_id

    # -- Sites & record types --------------------------------------------------

    @ai_function()
    async def list_sites(self) -> list[dict[str, object]]:
        """List all available VEuPathDB sites."""
        sites = await catalog.list_sites()
        return [
            s.model_dump(by_alias=True, exclude_none=True, mode="json") for s in sites
        ]

    @ai_function()
    async def get_record_types(self) -> list[dict[str, str]]:
        """List available record types for this site."""
        record_types = await catalog.get_record_types(self.site_id)
        return [
            {
                "name": rt.name,
                "displayName": rt.display_name,
                "description": rt.description,
            }
            for rt in record_types
        ]

    # -- Search discovery ------------------------------------------------------

    @ai_function()
    async def search_for_searches(
        self,
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Descriptive natural language query about what you're looking for. "
                    "Must include 2+ specific keywords. "
                    "Example: 'gametocyte RNA-Seq expression percentile data'"
                )
            ),
        ],
        record_type: Annotated[
            str | None,
            AIParam(desc="Filter to a specific record type (e.g., 'transcript'). Omit for all."),
        ] = None,
        keywords: Annotated[
            list[str] | None,
            AIParam(
                desc=(
                    "Optional exact identifiers to match against search names (urlSegment). "
                    "These get massive score boost. Extract from dataset names, search "
                    "name fragments, or organism codes mentioned in the user's request. "
                    "Example: ['Su_strand_specific', 'Percentile', 'pfal3D7']"
                )
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results to return.")] = 20,
    ) -> list[dict[str, str]]:
        """Find WDK searches by description and/or keywords.

        Returns a ranked list with name, displayName, description, category,
        and what the search returns (genes, SNPs, etc.).
        """
        kw = keywords or []
        err = search_query_error(query, has_keywords=bool(kw))
        if err is not None:
            return []
        matches = await catalog.search_for_searches(
            self.site_id,
            record_type=record_type,
            query=query,
            keywords=kw,
            limit=limit,
        )
        return [m.to_dict() for m in matches]

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (e.g., 'gene', 'transcript')")],
    ) -> list[dict[str, str]]:
        """List all search names for a record type (names only, no descriptions).

        Use search_for_searches first for targeted discovery with descriptions.
        """
        return await catalog.list_searches(self.site_id, record_type)

    @ai_function()
    async def list_transforms(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (e.g., 'transcript')")],
    ) -> list[dict[str, str]]:
        """List available transform and combine operations (with descriptions).

        Returns searches that chain onto a previous step's results — such as
        ortholog transforms, weight filters, span logic, and boolean combines.
        """
        return await catalog.list_transforms(self.site_id, record_type)

    # -- Search details --------------------------------------------------------

    @ai_function()
    async def get_search_parameters(
        self,
        record_type: Annotated[str, AIParam(desc="Record type (e.g., 'transcript')")],
        search_name: Annotated[str, AIParam(desc="Search name")],
    ) -> JSONObject:
        """Get full details for a specific search: description, parameters, and valid values."""
        return await catalog.get_search_parameters_tool(
            SearchContext(self.site_id, record_type, search_name)
        )

    @ai_function()
    async def get_dependent_vocab(
        self,
        record_type: Annotated[str, AIParam(desc="Record type")],
        search_name: Annotated[str, AIParam(desc="Search name")],
        param_name: Annotated[str, AIParam(desc="Dependent parameter name to refresh")],
        context_values: Annotated[
            JSONObject | None,
            AIParam(desc="Current contextParamValues (paramName -> value)"),
        ] = None,
    ) -> JSONObject:
        """Get dependent vocab for a parameter.

        WDK's refreshed-dependent-params requires a changed param value.
        If context_values does not include param_name, falls back to
        expanded search details.
        """
        ctx = context_values or {}
        has_context = any(v is not None and v != "" for v in ctx.values())

        if has_context:
            client = get_wdk_client(self.site_id)
            result = await client.get_search_details_with_params(
                record_type, search_name, context=ctx, expand_params=True,
            )
            for p in result.search_data.parameters or []:
                if p.name == param_name:
                    return p.model_dump(by_alias=True)
            return {"error": "param_not_found", "paramName": param_name}

        # Fallback: fetch expanded search details
        client = get_wdk_client(self.site_id)
        details = await client.get_search_details(
            record_type, search_name, expand_params=True,
        )
        for p in details.search_data.parameters or []:
            if p.name == param_name:
                return p.model_dump(by_alias=True)
        return {"error": "param_not_found", "paramName": param_name}

    # -- Phyletic codes --------------------------------------------------------

    @ai_function()
    async def lookup_phyletic_codes(
        self,
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
        """Look up phyletic species/group codes by name for GenesByOrthologPattern.

        Returns {code, label, leaf} triples. Use codes in profile_pattern:
        %CODE:Y% (include) or %CODE:N% (exclude).
        """
        return await catalog.lookup_phyletic_codes(self.site_id, record_type, query)

    # -- Example plans ---------------------------------------------------------

    @ai_function()
    async def search_example_plans(
        self,
        query: Annotated[
            str, AIParam(desc="User goal / query to match against public strategies")
        ],
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 3,
    ) -> list[JSONObject]:
        """Retrieve relevant public strategies from WDK matched by text relevance."""
        try:
            api = get_strategy_api(self.site_id)
            public_strategies = await api.list_public_strategies()
            return rank_public_strategies(public_strategies, query=query, limit=limit)
        except (AppError, OSError) as exc:
            logger.warning("Failed to fetch public strategies", error=str(exc))
            return []
