"""AI tools for workbench gene set operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from kani import AIParam, ai_function

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.gene_sets.types import GeneSet

logger = get_logger(__name__)


class WorkbenchToolsMixin:
    """Kani tool mixin for workbench gene set operations."""

    site_id: str
    user_id: UUID | None

    @ai_function()
    async def create_workbench_gene_set(
        self,
        name: Annotated[
            str,
            AIParam(
                desc="Human-readable name for the gene set (e.g. 'Upregulated in gametocytes')"
            ),
        ],
        gene_ids: Annotated[
            list[str],
            AIParam(
                desc=(
                    "List of gene IDs to include (e.g. "
                    "['PF3D7_1222600', 'PF3D7_1031000']). "
                    "Can be from search results, literature, or user input."
                )
            ),
        ],
        search_name: Annotated[
            str | None,
            AIParam(
                desc="WDK search name if this gene set comes from a strategy search"
            ),
        ] = None,
        record_type: Annotated[
            str | None,
            AIParam(desc="Record type (default 'gene')"),
        ] = None,
        parameters: Annotated[
            dict[str, str] | None,
            AIParam(desc="WDK search parameters if from a strategy search"),
        ] = None,
        wdk_strategy_id: Annotated[
            int | None,
            AIParam(desc="WDK strategy ID if this gene set is from a built strategy"),
        ] = None,
        wdk_step_id: Annotated[
            int | None,
            AIParam(desc="WDK step ID if this gene set is from a specific step"),
        ] = None,
    ) -> JSONObject:
        """Create a gene set in the user's Workbench for further analysis.

        Use this tool after building a strategy or collecting gene IDs to send them
        to the Workbench where the user can run enrichment analysis, evaluate
        strategies, compare gene sets, and more.

        The created gene set will appear in the user's Workbench sidebar.
        """
        source = "strategy" if wdk_strategy_id is not None else "paste"
        gs = GeneSet(
            id=str(uuid4()),
            name=name,
            site_id=self.site_id,
            gene_ids=gene_ids,
            source=source,
            user_id=self.user_id,
            wdk_strategy_id=wdk_strategy_id,
            wdk_step_id=wdk_step_id,
            search_name=search_name,
            record_type=record_type or "gene",
            parameters=parameters,
        )
        get_gene_set_store().save(gs)
        logger.info(
            "AI created workbench gene set",
            gene_set_id=gs.id,
            name=gs.name,
            gene_count=len(gs.gene_ids),
        )
        return {
            "geneSetCreated": {
                "id": gs.id,
                "name": gs.name,
                "geneCount": len(gs.gene_ids),
                "source": gs.source,
                "siteId": gs.site_id,
            },
            "message": f"Gene set '{gs.name}' with {len(gs.gene_ids)} genes has been created in the Workbench.",
        }

    @ai_function()
    async def run_gene_set_enrichment(
        self,
        gene_set_id: Annotated[
            str,
            AIParam(
                desc="ID of the gene set to run enrichment on (from create_workbench_gene_set result)"
            ),
        ],
        enrichment_types: Annotated[
            list[str],
            AIParam(
                desc=(
                    "Types of enrichment to run. Options: "
                    "'go_function', 'go_process', 'go_component', 'pathway', 'word'. "
                    "Default: all five types."
                )
            ),
        ]
        | None = None,
    ) -> JSONObject:
        """Run enrichment analysis on a gene set in the Workbench.

        This performs over-representation analysis (ORA) to find enriched
        GO terms, pathways, or word patterns in the gene set. Requires
        the gene set to have a WDK step ID or search parameters.
        """
        from veupath_chatbot.services.experiment.types import to_json
        from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

        store = get_gene_set_store()
        gs = store.get(gene_set_id)
        if gs is None:
            return {"error": f"Gene set '{gene_set_id}' not found."}

        types = enrichment_types or [
            "go_function",
            "go_process",
            "go_component",
            "pathway",
            "word",
        ]

        svc = EnrichmentService()
        results, errors = await svc.run_batch(
            site_id=gs.site_id,
            analysis_types=types,
            step_id=gs.wdk_step_id,
            search_name=gs.search_name,
            record_type=gs.record_type or "gene",
            parameters=gs.parameters,
        )

        serialized = [to_json(r) for r in results]
        summary: JSONObject = {
            "geneSetId": gene_set_id,
            "geneSetName": gs.name,
            "geneCount": len(gs.gene_ids),
            "enrichmentResults": serialized,
            "analysisTypesRun": [r.get("analysisType", "unknown") for r in serialized],
            "totalSignificantTerms": sum(
                sum(
                    1
                    for t in r.get("terms", [])
                    if isinstance(t, dict) and t.get("pValue", 1) < 0.05
                )
                for r in serialized
            ),
        }
        if errors:
            summary["errors"] = errors

        return summary

    @ai_function()
    async def list_workbench_gene_sets(self) -> JSONObject:
        """List all gene sets currently in the user's Workbench.

        Returns a summary of each gene set including name, gene count,
        source, and ID. Use this to check what's available before
        running analyses.
        """
        store = get_gene_set_store()
        if self.user_id is not None:
            sets = store.list_for_user(self.user_id, site_id=self.site_id)
        else:
            sets = store.list_all(site_id=self.site_id)
        return {
            "geneSets": [
                {
                    "id": gs.id,
                    "name": gs.name,
                    "geneCount": len(gs.gene_ids),
                    "source": gs.source,
                    "searchName": gs.search_name,
                    "hasWdkStep": gs.wdk_step_id is not None,
                }
                for gs in sets
            ],
            "totalSets": len(sets),
        }
