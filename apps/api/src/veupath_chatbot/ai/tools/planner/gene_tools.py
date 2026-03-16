"""Planner-mode tools for gene record lookup and resolution.

Provides :class:`GeneToolsMixin` with tools for searching and resolving
gene records via VEuPathDB site-search.
"""

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.gene_lookup import (
    lookup_genes_by_text,
    resolve_gene_ids,
)


class GeneToolsMixin:
    """Kani tool mixin for gene record lookup."""

    site_id: str = ""

    @ai_function()
    async def lookup_gene_records(
        self,
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Free-text query to search for gene records — gene name, symbol, "
                    "locus tag, product description, or keyword (e.g. 'PfAP2-G', "
                    "'gametocyte surface antigen', 'Pfs25')."
                )
            ),
        ],
        organism: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Organism filter (e.g. 'Plasmodium falciparum 3D7'). "
                    "Omit to search across all organisms on the site."
                )
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results to return (default 10)")] = 10,
    ) -> JSONObject:
        """Look up gene records by name, symbol, or description using VEuPathDB site-search.

        Use this to resolve human-readable gene names (from literature or user input)
        to VEuPathDB gene IDs.  The returned IDs can then be used as positive/negative
        controls in `run_control_tests` or `optimize_search_parameters`.
        """
        return await lookup_genes_by_text(
            self.site_id,
            query,
            organism=organism,
            limit=max(1, min(limit, 50)),
        )

    @ai_function()
    async def resolve_gene_ids_to_records(
        self,
        gene_ids: Annotated[
            list[str],
            AIParam(
                desc=(
                    "List of gene/locus tag IDs to resolve (e.g. "
                    "['PF3D7_1222600', 'PF3D7_1031000'])."
                )
            ),
        ],
        record_type: Annotated[
            str, AIParam(desc="WDK record type (default 'transcript')")
        ] = "transcript",
        search_name: Annotated[
            str,
            AIParam(desc="WDK search that accepts ID lists (default 'GeneByLocusTag')"),
        ] = "GeneByLocusTag",
        param_name: Annotated[
            str,
            AIParam(desc="Parameter name for the ID list (default 'ds_gene_ids')"),
        ] = "ds_gene_ids",
    ) -> JSONObject:
        """Resolve known gene IDs to full records (product name, organism, gene type).

        Use this to validate gene IDs or fetch metadata for IDs you already have
        (e.g. from literature).  For discovering genes by name, use `lookup_gene_records` instead.
        """
        ids = [str(x).strip() for x in (gene_ids or []) if str(x).strip()]
        if not ids:
            return {"records": [], "totalCount": 0, "error": "No gene IDs provided."}
        if len(ids) > 200:
            return {
                "records": [],
                "totalCount": 0,
                "error": "Too many IDs (max 200). Reduce the list.",
            }
        return await resolve_gene_ids(
            self.site_id,
            ids,
            record_type=record_type,
            search_name=search_name,
            param_name=param_name,
        )
