"""AI tool wrappers for catalog/discovery.

The underlying logic lives in `veupath_chatbot.services.catalog` to keep things DRY.
"""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services import catalog


class CatalogTools:
    """Tools for exploring VEuPathDB catalog."""

    @ai_function()
    async def list_sites(self) -> list[dict[str, object]]:
        sites = await catalog.list_sites()
        return [
            s.model_dump(by_alias=True, exclude_none=True, mode="json") for s in sites
        ]

    @ai_function()
    async def get_record_types(
        self,
        site_id: Annotated[
            str,
            AIParam(desc="Site ID (e.g., 'plasmodb', 'toxodb', 'veupathdb')"),
        ],
    ) -> list[dict[str, str]]:
        record_types = await catalog.get_record_types(site_id)
        return [
            {
                "name": rt.name,
                "displayName": rt.display_name,
                "description": rt.description,
            }
            for rt in record_types
        ]

    @ai_function()
    async def search_for_searches(
        self,
        site_id: Annotated[str, AIParam(desc="Site ID")],
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Descriptive natural language query about what you're looking for. "
                    "Example: 'gametocyte RNA-Seq expression percentile data'"
                )
            ),
        ],
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
    ) -> list[dict[str, str]]:
        """Find WDK searches by description and/or keywords.

        Returns a ranked list with name, displayName, description, category,
        and what the search returns (genes, SNPs, etc.).

        The query is matched against display names and descriptions.
        Keywords are matched against the internal search name (urlSegment)
        with heavy boosting — use these when you know part of the search
        identifier.
        """
        matches = await catalog.search_for_searches(
            site_id,
            record_type=None,
            query=query,
            keywords=keywords or [],
        )
        return [m.to_dict() for m in matches]

    @ai_function()
    async def list_transforms(
        self,
        site_id: Annotated[
            str,
            AIParam(desc="Site ID (e.g., 'plasmodb')"),
        ],
        record_type: Annotated[
            str,
            AIParam(desc="Record type (e.g., 'transcript')"),
        ],
    ) -> list[dict[str, str]]:
        """List available transform and combine operations (with descriptions).

        Returns searches that chain onto a previous step's results — such as
        ortholog transforms, weight filters, span logic, and boolean combines.
        Use this when you need to transform or combine step results. Always call
        this before attempting to use a transform search in create_step.
        """
        return await catalog.list_transforms(site_id, record_type)

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
            SearchContext(site_id, record_type, search_name)
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
        """Look up phyletic species/group codes by name for GenesByOrthologPattern.

        Returns {code, label, leaf} triples. Use codes in profile_pattern:
        %CODE:Y% (include) or %CODE:N% (exclude).
        Group codes (leaf=false) with :N are auto-expanded to all leaf descendants.
        Example: lookup 'mammal' → MAMM (leaf=false), use '%MAMM:N%pfal:Y%'.
        """
        return await catalog.lookup_phyletic_codes(site_id, record_type, query)
