"""Worker-side impl for ``run_gene_set_enrichment``.

Moved from ``ai/tools/standalone/workbench.py``. Runs ORA against a workbench
gene set on the verification worker; progress is emitted per enrichment phase
(lookup, dispatch, export, finalise).
"""

from __future__ import annotations

from typing import Any, cast, get_args
from uuid import UUID

from pathfinder.ai.graph.runtime import Context
from pathfinder.assistant_core.memory.store import MemoryStore
from pathfinder.jobs.progress import TaskProgressEmitter
from pathfinder.services.enrichment.types import EnrichmentAnalysisType
from pathfinder.services.gene_sets.enrichment import run_enrichment_for_gene_set
from pathfinder.services.gene_sets.store import get_gene_set_store


async def run_gene_set_enrichment_impl(
    *,
    context: Context,
    task_id: UUID,
    progress: TaskProgressEmitter,
    memory_store: MemoryStore | None,
    gene_set_id: str,
    enrichment_types: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Run enrichment analysis on a workbench gene set."""
    del context, task_id, memory_store

    await progress.update(
        percent=0.0,
        message=f"Loading gene set {gene_set_id}",
        data={"gene_set_id": gene_set_id},
    )
    store = get_gene_set_store()
    gs = await store.aget(gene_set_id)
    if gs is None:
        msg = f"gene set {gene_set_id} does not exist"
        raise LookupError(msg)

    valid_types = get_args(EnrichmentAnalysisType)
    types: list[EnrichmentAnalysisType] = (
        [
            cast("EnrichmentAnalysisType", t)
            for t in enrichment_types
            if t in valid_types
        ]
        if enrichment_types
        else ["go_function", "go_process", "go_component", "pathway", "word"]
    )
    await progress.update(
        percent=0.2,
        message=f"Running enrichment ({len(types)} analyses)",
        data={"analyses": list(types), "gene_count": len(gs.gene_ids)},
    )

    summary = await run_enrichment_for_gene_set(gs, types)
    await progress.update(
        percent=0.9,
        message="Finalising enrichment summary",
        data=None,
    )

    result: dict[str, Any] = dict(summary)
    result["geneSetId"] = gene_set_id
    result["geneSetName"] = gs.name
    result["geneCount"] = len(gs.gene_ids)

    await progress.update(
        percent=1.0,
        message="Enrichment complete",
        data=None,
    )
    return result
