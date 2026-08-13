"""Agent tools that read experiment results: records, genes, distributions, and search."""

from typing import cast

from pydantic_ai import RunContext

from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSortDirection,
    WDKSortSpec,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.ai_analysis_helpers import (
    build_primary_key,
    classify_gene,
    fetch_group_records,
    record_matches,
)
from pathfinder.services.experiment.store import get_experiment_store
from pathfinder.services.experiment.types import (
    Experiment,
)
from pathfinder.services.experiment.workbench_deps import WorkbenchDeps
from pathfinder.services.wdk.helpers import extract_pk

# A broad query must not fill the model context or fetch every result page.
_MAX_SEARCH_MATCHES = 20


async def _get_experiment(ctx: RunContext[WorkbenchDeps]) -> Experiment | None:
    """Fetch the current experiment from the store. Return None when it is absent."""
    store = get_experiment_store()
    return await store.aget(ctx.deps.experiment_id)


async def fetch_result_records(
    ctx: RunContext[WorkbenchDeps],
    offset: int = 0,
    limit: int = 20,
    sort_attribute: str | None = None,
    sort_direction: str = "ASC",
) -> JSONObject:
    """Fetch paginated result records from the experiment's WDK search results.

    Each record includes attributes and a classification (TP/FP/FN/TN)
    based on the experiment's control genes.

    Args:
        offset: Page offset (0-based).
        limit: Number of records (max 50).
        sort_attribute: Attribute name to sort by.
        sort_direction: ASC or DESC.
    """
    exp = await _get_experiment(ctx)
    if not exp or not exp.wdk_step_id:
        return {"error": "Experiment has no WDK strategy"}

    api = get_strategy_api(ctx.deps.site_id)
    sorting: list[WDKSortSpec] | None = None
    if sort_attribute:
        direction: WDKSortDirection = (
            "DESC" if sort_direction.upper() == "DESC" else "ASC"
        )
        sorting = [WDKSortSpec(attribute_name=sort_attribute, direction=direction)]

    answer = await api.get_step_records(
        step_id=exp.wdk_step_id,
        pagination={"offset": offset, "numRecords": min(limit, 50)},
        sorting=sorting,
    )

    tp_ids, fp_ids, fn_ids, tn_ids = exp.classification_id_sets()

    classified: list[JSONObject] = []
    for rec in answer.records:
        gene_id = extract_pk(rec)
        classification = classify_gene(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
        classified.append(
            {
                "geneId": gene_id,
                "classification": classification,
                "attributes": rec.attributes,
            }
        )

    total = answer.meta.records_returned()
    return cast(
        "JSONObject",
        {
            "records": classified[:50],
            "totalCount": total,
            "offset": offset,
        },
    )


async def lookup_gene_detail(
    ctx: RunContext[WorkbenchDeps],
    gene_id: str,
) -> JSONObject:
    """Get the full record details for a specific gene by its ID.

    Returns all attributes and tables for the gene from WDK.

    Args:
        gene_id: Gene ID to look up.
    """
    exp = await _get_experiment(ctx)
    if not exp:
        return {"error": "Experiment not found"}

    api = get_strategy_api(ctx.deps.site_id)
    try:
        pk_parts = await build_primary_key(
            api, ctx.deps.site_id, exp.config.record_type, gene_id
        )
        record = await api.get_single_record(
            record_type=exp.config.record_type,
            primary_key=pk_parts,
        )
        tp_ids, fp_ids, fn_ids, tn_ids = exp.classification_id_sets()
        classification = classify_gene(gene_id, tp_ids, fp_ids, fn_ids, tn_ids)
    except AppError as exc:
        return {"error": str(exc), "geneId": gene_id}
    else:
        return {
            "geneId": gene_id,
            "classification": classification,
            "record": record.model_dump(by_alias=True),
        }


async def get_attribute_distribution(
    ctx: RunContext[WorkbenchDeps],
    attribute_name: str,
) -> JSONObject:
    """Get the distribution of values for a given attribute across all results.

    Useful for understanding patterns in the data.

    Args:
        attribute_name: Attribute name to get distribution for.
    """
    exp = await _get_experiment(ctx)
    if not exp or not exp.wdk_step_id:
        return {"error": "Experiment has no WDK strategy"}

    api = get_strategy_api(ctx.deps.site_id)
    try:
        dist = await api.get_column_distribution(exp.wdk_step_id, attribute_name)
        return dist.model_dump(by_alias=True)
    except AppError as exc:
        return {"error": str(exc), "attribute": attribute_name}


async def compare_gene_groups(
    ctx: RunContext[WorkbenchDeps],
    group_a_ids: list[str],
    group_b_ids: list[str],
) -> JSONObject:
    """Compare attributes of two groups of genes to find distinguishing features.

    Fetches records for both groups and identifies attribute differences.

    Args:
        group_a_ids: Gene IDs for group A.
        group_b_ids: Gene IDs for group B.
    """
    exp = await _get_experiment(ctx)
    if not exp or not exp.wdk_step_id:
        return {"error": "Experiment has no WDK strategy"}

    api = get_strategy_api(ctx.deps.site_id)
    group_a_attrs = await fetch_group_records(
        api, exp.config.record_type, group_a_ids, site_id=ctx.deps.site_id
    )
    group_b_attrs = await fetch_group_records(
        api, exp.config.record_type, group_b_ids, site_id=ctx.deps.site_id
    )

    return cast(
        "JSONObject",
        {
            "groupA": group_a_attrs,
            "groupB": group_b_attrs,
            "groupACount": len(group_a_attrs),
            "groupBCount": len(group_b_attrs),
        },
    )


async def search_results(
    ctx: RunContext[WorkbenchDeps],
    query: str,
    attribute: str | None = None,
) -> JSONObject:
    """Search through result records for a text pattern.

    Iterates through result pages looking for records whose attributes
    match the query string.

    Args:
        query: Text pattern to search for.
        attribute: Specific attribute to search in.
    """
    exp = await _get_experiment(ctx)
    if not exp or not exp.wdk_step_id:
        return {"error": "Experiment has no WDK strategy"}

    api = get_strategy_api(ctx.deps.site_id)
    matches: list[JSONObject] = []
    query_lower = query.lower()
    total_scanned = 0

    for page_offset in range(0, 500, 100):
        answer = await api.get_step_records(
            step_id=exp.wdk_step_id,
            pagination={"offset": page_offset, "numRecords": 100},
        )
        records = answer.records
        if not records:
            break
        total_scanned = page_offset + len(records)

        for rec in records:
            if record_matches(rec.attributes, query_lower, attribute):
                gene_id = extract_pk(rec)
                matches.append({"geneId": gene_id, "attributes": rec.attributes})
                if len(matches) >= _MAX_SEARCH_MATCHES:
                    return cast(
                        "JSONObject",
                        {
                            "matches": matches,
                            "totalScanned": total_scanned,
                        },
                    )

    return cast("JSONObject", {"matches": matches, "totalScanned": total_scanned})
