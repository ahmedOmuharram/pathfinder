"""Standalone workbench gene set tools for pydantic-ai agents.

Provides:
- ``create_workbench_gene_set`` -- create a gene set in the user's Workbench
- ``run_gene_set_enrichment`` -- run enrichment analysis on a gene set (durable)
- ``list_workbench_gene_sets`` -- list all gene sets in the user's Workbench
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.durable import durable_tool
from pathfinder.ai.tools.standalone._stream_parts import gene_set_chunk
from pathfinder.ai.tools.standalone._workbench_models import (
    GeneSetCreatedResponse,
    GeneSetCreatedSummary,
    GeneSetListItem,
    GeneSetListResponse,
    WdkSourceSpec,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.gene_sets.store import get_gene_set_store
from pathfinder.services.gene_sets.types import GeneSet, GeneSetSource

logger = get_logger(__name__)


async def create_workbench_gene_set(
    ctx: RunContext[AgentDeps],
    name: str,
    gene_ids: list[str],
    record_type: str = "transcript",
    wdk_source: WdkSourceSpec | None = None,
) -> ToolReturn[GeneSetCreatedResponse]:
    """Create a gene set in the user's Workbench for further analysis.

    Use this tool after building a strategy or collecting gene IDs to send them
    to the Workbench where the user can run enrichment analysis, evaluate
    strategies, compare gene sets, and more.

    The created gene set will appear in the user's Workbench sidebar.

    Args:
        name: Human-readable name for the gene set (e.g. 'Upregulated in gametocytes').
        gene_ids: List of gene IDs to include (e.g. ['PF3D7_1222600', 'PF3D7_1031000']).
        record_type: Record type (default 'transcript').
        wdk_source: Optional WDK provenance (search name, parameters, strategy ID, step ID).
    """
    if not name or not name.strip():
        msg = "VALIDATION_ERROR: Gene set name must be a non-empty string."
        raise ModelRetry(msg)
    if not gene_ids:
        msg = "VALIDATION_ERROR: gene_ids must contain at least one gene ID."
        raise ModelRetry(msg)
    deps = ctx.deps
    src = wdk_source or WdkSourceSpec()
    source: GeneSetSource = (
        "strategy" if src.wdk_strategy_id is not None else "paste"
    )
    gs = GeneSet(
        id=str(uuid4()),
        name=name,
        site_id=deps.site_id,
        gene_ids=gene_ids,
        source=source,
        user_id=deps.user_id,
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
    return ToolReturn(
        return_value=GeneSetCreatedResponse(
            gene_set_created=GeneSetCreatedSummary(
                id=gs.id,
                name=gs.name,
                gene_count=len(gs.gene_ids),
                source=gs.source,
                site_id=gs.site_id,
            ),
            message=f"Gene set '{gs.name}' with {len(gs.gene_ids)} genes has been created in the Workbench.",
        ),
        metadata=[
            gene_set_chunk(
                gene_set_id=gs.id,
                name=gs.name,
                gene_count=len(gs.gene_ids),
                site_id=gs.site_id,
            )
        ],
    )


EnrichmentType = Literal[
    "go_function", "go_process", "go_component", "pathway", "word",
]


@durable_tool(
    tool_name="geneset_enrichment",
    estimated_duration_seconds=120,
)
async def run_gene_set_enrichment(
    ctx: RunContext[AgentDeps],
    gene_set_id: str,
    enrichment_types: list[EnrichmentType] | None = None,
) -> dict[str, Any]:
    """Run enrichment analysis on a gene set in the Workbench.

    Durable: the real analysis runs on the verification worker; the graph
    suspends on ``interrupt()`` while GO/Pathway/Word ORA phases complete
    and progress streams back through ``task_progress``. The resumed value
    is the summary dict (``geneSetId``, ``geneCount``, ``enrichmentResults``,
    ``downloads``).

    Requires the gene set to have a WDK step ID or search parameters so the
    enrichment service can recover the full background gene universe.

    Args:
        gene_set_id: ID of the gene set to run enrichment on (from
            ``create_workbench_gene_set`` result).
        enrichment_types: Types of enrichment to run. Options: ``go_function``,
            ``go_process``, ``go_component``, ``pathway``, ``word``. Default:
            all five types.
    """
    del ctx, gene_set_id, enrichment_types
    msg = "run_gene_set_enrichment runs on the worker via @durable_tool"
    raise NotImplementedError(msg)


async def list_workbench_gene_sets(
    ctx: RunContext[AgentDeps],
) -> GeneSetListResponse:
    """List all gene sets currently in the user's Workbench.

    Returns a summary of each gene set including name, gene count,
    source, and ID. Use this to check what's available before
    running analyses.
    """
    deps = ctx.deps
    store = get_gene_set_store()
    if deps.user_id is not None:
        sets = await store.alist_for_user(deps.user_id, site_id=deps.site_id)
    else:
        sets = await store.alist_all(site_id=deps.site_id)
    return GeneSetListResponse(
        gene_sets=[
            GeneSetListItem(
                id=gs.id,
                name=gs.name,
                gene_count=len(gs.gene_ids),
                source=gs.source,
                search_name=gs.search_name,
                has_wdk_step=gs.wdk_step_id is not None,
            )
            for gs in sets
        ],
        total_sets=len(sets),
    )
