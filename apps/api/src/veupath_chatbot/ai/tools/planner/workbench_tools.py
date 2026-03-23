"""AI tools for workbench gene set operations."""

from typing import Annotated, cast, get_args
from uuid import UUID, uuid4

from kani import AIParam, ai_function
from pydantic import BaseModel

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types import EnrichmentAnalysisType
from veupath_chatbot.services.gene_sets.enrichment import run_enrichment_for_gene_set
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.gene_sets.types import GeneSet, GeneSetSource

logger = get_logger(__name__)


class WdkSourceSpec(BaseModel):
    """Optional WDK provenance for a gene set.

    Groups the WDK-linked fields into a single parameter so the
    ``create_workbench_gene_set`` AI function stays within the
    six-argument limit.
    """

    search_name: Annotated[
        str | None,
        AIParam(desc="WDK search name if this gene set comes from a strategy search"),
    ] = None
    parameters: Annotated[
        dict[str, str] | None,
        AIParam(desc="WDK search parameters if from a strategy search"),
    ] = None
    wdk_strategy_id: Annotated[
        int | None,
        AIParam(desc="WDK strategy ID if this gene set is from a built strategy"),
    ] = None
    wdk_step_id: Annotated[
        int | None,
        AIParam(desc="WDK step ID if this gene set is from a specific step"),
    ] = None


class WorkbenchToolsMixin:
    """Kani tool mixin for workbench gene set operations."""

    site_id: str = ""
    user_id: UUID | None = None

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
        record_type: Annotated[
            str,
            AIParam(desc="Record type (default 'transcript')"),
        ] = "transcript",
        *,
        wdk_source: Annotated[
            WdkSourceSpec | None,
            AIParam(
                desc="Optional WDK provenance (search name, parameters, strategy ID, step ID)"
            ),
        ] = None,
    ) -> JSONObject:
        """Create a gene set in the user's Workbench for further analysis.

        Use this tool after building a strategy or collecting gene IDs to send them
        to the Workbench where the user can run enrichment analysis, evaluate
        strategies, compare gene sets, and more.

        The created gene set will appear in the user's Workbench sidebar.
        """
        if not name or not name.strip():
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Gene set name must be a non-empty string.",
            )
        if not gene_ids:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "gene_ids must contain at least one gene ID.",
            )
        src = wdk_source or WdkSourceSpec()
        source: GeneSetSource = (
            "strategy" if src.wdk_strategy_id is not None else "paste"
        )
        gs = GeneSet(
            id=str(uuid4()),
            name=name,
            site_id=self.site_id,
            gene_ids=gene_ids,
            source=source,
            user_id=self.user_id,
            wdk_strategy_id=src.wdk_strategy_id,
            wdk_step_id=src.wdk_step_id,
            search_name=src.search_name,
            record_type=record_type,
            parameters=src.parameters,
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
        store = get_gene_set_store()
        gs = await store.aget(gene_set_id)
        if gs is None:
            if self.user_id is not None:
                available = await store.alist_for_user(self.user_id, site_id=self.site_id)
            else:
                available = await store.alist_all(site_id=self.site_id)
            return {
                "error": f"Gene set '{gene_set_id}' not found. Use one of the available IDs below.",
                "availableGeneSets": [
                    {"id": g.id, "name": g.name, "geneCount": len(g.gene_ids)}
                    for g in available[:10]
                ],
            }

        _valid_types = get_args(EnrichmentAnalysisType)
        types: list[EnrichmentAnalysisType] = (
            [
                cast("EnrichmentAnalysisType", t)
                for t in enrichment_types
                if t in _valid_types
            ]
            if enrichment_types
            else ["go_function", "go_process", "go_component", "pathway", "word"]
        )

        summary = await run_enrichment_for_gene_set(gs, types)
        summary["geneSetId"] = gene_set_id
        summary["geneSetName"] = gs.name
        summary["geneCount"] = len(gs.gene_ids)
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
            sets = await store.alist_for_user(self.user_id, site_id=self.site_id)
        else:
            sets = await store.alist_all(site_id=self.site_id)
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
