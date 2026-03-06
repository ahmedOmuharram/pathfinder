"""Gene set management endpoints."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Request

from veupath_chatbot.platform.errors import (
    InternalError,
    NotFoundError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import limiter
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.gene_sets.store import get_gene_set_store
from veupath_chatbot.services.gene_sets.types import GeneSet
from veupath_chatbot.services.wdk.helpers import extract_record_ids
from veupath_chatbot.services.wdk.step_results import StepResultsService
from veupath_chatbot.transport.http.deps import CurrentUser
from veupath_chatbot.transport.http.schemas.gene_sets import (
    CreateGeneSetRequest,
    GeneSetEnrichRequest,
    GeneSetResponse,
    RunGeneSetAnalysisRequest,
    SetOperationRequest,
)

router = APIRouter(prefix="/api/v1/gene-sets", tags=["gene-sets"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(gs: GeneSet) -> GeneSetResponse:
    return GeneSetResponse(
        id=gs.id,
        siteId=gs.site_id,
        name=gs.name,
        geneIds=gs.gene_ids,
        source=gs.source,
        geneCount=len(gs.gene_ids),
        wdkStrategyId=gs.wdk_strategy_id,
        wdkStepId=gs.wdk_step_id,
        searchName=gs.search_name,
        recordType=gs.record_type,
        parameters=gs.parameters,
        parentSetIds=gs.parent_set_ids,
        operation=gs.operation,
        createdAt=gs.created_at.isoformat(),
        stepCount=gs.step_count,
    )


async def _get_gene_set_or_404(user_id: UUID, gene_set_id: str) -> GeneSet:
    """Look up a gene set owned by user, raising 404 if missing."""
    gs = await get_gene_set_store().aget(gene_set_id)
    if gs is None or gs.user_id != user_id:
        raise NotFoundError(title="Gene set not found")
    return gs


async def _fetch_gene_ids_from_step(site_id: str, step_id: int) -> list[str]:
    """Fetch gene IDs from a WDK step via the standard report endpoint."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    api = get_strategy_api(site_id)
    answer = await api.get_step_answer(
        step_id,
        attributes=["primary_key"],
        pagination={"offset": 0, "numRecords": 10_000},
    )
    records = answer.get("records", [])
    if not isinstance(records, list):
        return []
    return extract_record_ids(records)


async def _resolve_root_step_id(site_id: str, strategy_id: int) -> int | None:
    """Get the root step ID from a WDK strategy."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    api = get_strategy_api(site_id)
    strategy = await api.get_strategy(strategy_id)
    root_step_id = strategy.get("rootStepId")
    if isinstance(root_step_id, int):
        return root_step_id
    return None


def _count_steps_in_tree(node: object) -> int:
    """Recursively count steps in a WDK strategy step tree."""
    if not isinstance(node, dict):
        return 0
    count = 1
    if "primaryInput" in node and isinstance(node["primaryInput"], dict):
        count += _count_steps_in_tree(node["primaryInput"])
    if "secondaryInput" in node and isinstance(node["secondaryInput"], dict):
        count += _count_steps_in_tree(node["secondaryInput"])
    return count


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
@limiter.limit("30/minute")
async def create_gene_set(
    request: Request,
    body: CreateGeneSetRequest,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Create a new gene set."""
    gene_ids = body.gene_ids
    wdk_step_id = body.wdk_step_id
    step_count = 1

    # Auto-resolve root step and fetch gene IDs when creating from a strategy
    if not gene_ids and body.wdk_strategy_id is not None:
        from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

        # Resolve the root step ID if not provided
        if wdk_step_id is None:
            try:
                wdk_step_id = await _resolve_root_step_id(
                    body.site_id, body.wdk_strategy_id
                )
                logger.info(
                    "Resolved root step from strategy",
                    strategy_id=body.wdk_strategy_id,
                    step_id=wdk_step_id,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to resolve root step from strategy",
                    strategy_id=body.wdk_strategy_id,
                    error=str(exc),
                )

        # Fetch gene IDs from the step
        if wdk_step_id is not None:
            try:
                gene_ids = await _fetch_gene_ids_from_step(body.site_id, wdk_step_id)
                logger.info(
                    "Fetched gene IDs from WDK step",
                    step_id=wdk_step_id,
                    gene_count=len(gene_ids),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch gene IDs from WDK step",
                    step_id=wdk_step_id,
                    error=str(exc),
                )

        # Count steps in the strategy
        try:
            api = get_strategy_api(body.site_id)
            strategy = await api.get_strategy(body.wdk_strategy_id)
            step_tree = strategy.get("stepTree")
            step_count = _count_steps_in_tree(step_tree)
        except Exception as exc:
            logger.warning(
                "Failed to count strategy steps",
                strategy_id=body.wdk_strategy_id,
                error=str(exc),
            )

    gs = GeneSet(
        id=str(uuid4()),
        name=body.name,
        site_id=body.site_id,
        gene_ids=gene_ids,
        source=body.source,
        user_id=user_id,
        wdk_strategy_id=body.wdk_strategy_id,
        wdk_step_id=wdk_step_id,
        search_name=body.search_name,
        record_type=body.record_type,
        parameters=body.parameters,
        step_count=step_count,
    )
    get_gene_set_store().save(gs)
    logger.info(
        "Gene set created", gene_set_id=gs.id, name=gs.name, gene_count=len(gs.gene_ids)
    )
    return _to_response(gs)


@router.get("")
async def list_gene_sets(
    user_id: CurrentUser,
    site_id: str | None = Query(None, alias="siteId"),
) -> list[GeneSetResponse]:
    """List all gene sets for the current user, optionally filtered by site."""
    sets = await get_gene_set_store().alist_for_user(user_id, site_id=site_id)
    return [_to_response(gs) for gs in sets]


@router.get("/{gene_set_id}")
async def get_gene_set(
    gene_set_id: str,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Get a gene set by ID."""
    return _to_response(await _get_gene_set_or_404(user_id, gene_set_id))


@router.delete("/{gene_set_id}")
async def delete_gene_set(
    gene_set_id: str,
    user_id: CurrentUser,
) -> dict[str, bool]:
    """Delete a gene set."""
    await _get_gene_set_or_404(user_id, gene_set_id)
    if not get_gene_set_store().delete(gene_set_id):
        raise NotFoundError(title="Gene set not found")
    logger.info("Gene set deleted", gene_set_id=gene_set_id)
    return {"ok": True}


@router.post("/operations")
async def set_operations(
    request: SetOperationRequest,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Perform set operations (intersect, union, minus) between two gene sets."""
    set_a = await _get_gene_set_or_404(user_id, request.set_a_id)
    set_b = await _get_gene_set_or_404(user_id, request.set_b_id)

    ids_a = set(set_a.gene_ids)
    ids_b = set(set_b.gene_ids)

    match request.operation:
        case "intersect":
            result_ids = ids_a & ids_b
        case "union":
            result_ids = ids_a | ids_b
        case "minus":
            result_ids = ids_a - ids_b
        case _:
            raise ValidationError(
                title="Invalid operation",
                detail=f"Operation must be 'intersect', 'union', or 'minus', got '{request.operation}'",
            )

    gs = GeneSet(
        id=str(uuid4()),
        name=request.name,
        site_id=set_a.site_id,
        gene_ids=sorted(result_ids),
        source="derived",
        user_id=user_id,
        parent_set_ids=[set_a.id, set_b.id],
        operation=request.operation,
    )
    get_gene_set_store().save(gs)
    logger.info(
        "Gene set derived via set operation",
        gene_set_id=gs.id,
        operation=request.operation,
        gene_count=len(gs.gene_ids),
    )
    return _to_response(gs)


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


@router.post("/{gene_set_id}/enrich")
async def enrich_gene_set(
    gene_set_id: str,
    request: GeneSetEnrichRequest,
    user_id: CurrentUser,
) -> list[JSONObject]:
    """Run enrichment analysis on a gene set."""
    from veupath_chatbot.services.experiment.types import to_json
    from veupath_chatbot.services.wdk.enrichment_service import EnrichmentService

    gs = await _get_gene_set_or_404(user_id, gene_set_id)

    svc = EnrichmentService()
    results, errors = await svc.run_batch(
        site_id=gs.site_id,
        analysis_types=request.enrichment_types,
        step_id=gs.wdk_step_id,
        search_name=gs.search_name,
        record_type=gs.record_type or "gene",
        parameters=gs.parameters,
    )

    if not results and errors:
        raise InternalError(
            title="Enrichment analysis failed",
            detail="; ".join(errors),
        )

    return [to_json(r) for r in results]


# ---------------------------------------------------------------------------
# Result browsing endpoints (attributes, records, distributions)
# ---------------------------------------------------------------------------


def _require_svc(gs: GeneSet) -> StepResultsService:
    """Create a StepResultsService for the gene set, raising 404 if no WDK step."""
    from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api

    if not gs.wdk_step_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This gene set has no associated WDK strategy for result browsing.",
        )
    api = get_strategy_api(gs.site_id)
    return StepResultsService(
        api, step_id=gs.wdk_step_id, record_type=gs.record_type or "gene"
    )


@router.get("/{gene_set_id}/results/attributes")
async def get_gene_set_attributes(
    gene_set_id: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get available attributes for a gene set's record type."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)
    return await svc.get_attributes()


@router.get("/{gene_set_id}/results/records")
async def get_gene_set_records(
    gene_set_id: str,
    user_id: CurrentUser,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    dir: str = "ASC",
    attributes: str | None = None,
    filter_attribute: str | None = Query(None, alias="filterAttribute"),
    filter_value: str | None = Query(None, alias="filterValue"),
) -> JSONObject:
    """Get paginated result records for a gene set."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)

    attr_list: list[str] | None = None
    if attributes:
        attr_list = [a.strip() for a in attributes.split(",") if a.strip()]

    # When filtering, fetch all records for the step and filter server-side.
    if filter_attribute and filter_value is not None:
        answer = await svc.get_records(
            offset=0,
            limit=10_000,
            sort=sort,
            direction=dir,
            attributes=attr_list,
        )
        records = answer.get("records", [])
        if not isinstance(records, list):
            records = []
        filtered = [
            r
            for r in records
            if isinstance(r, dict)
            and isinstance(r.get("attributes"), dict)
            and r["attributes"].get(filter_attribute) == filter_value
        ]
        page = filtered[offset : offset + limit]
        return {
            "records": cast(JSONValue, page),
            "meta": {
                "totalCount": len(filtered),
                "displayTotalCount": len(filtered),
                "responseCount": len(page),
                "pagination": {"offset": offset, "numRecords": limit},
                "attributes": attr_list or [],
                "tables": [],
            },
        }

    return await svc.get_records(
        offset=offset,
        limit=limit,
        sort=sort,
        direction=dir,
        attributes=attr_list,
    )


@router.post("/{gene_set_id}/results/record")
async def get_gene_set_record_detail(
    gene_set_id: str,
    request_body: dict[str, object],
    user_id: CurrentUser,
) -> JSONObject:
    """Get a single record's full details by primary key."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)

    raw_pk = request_body.get("primaryKey") or request_body.get("primary_key") or []
    if not isinstance(raw_pk, list) or not raw_pk:
        raise ValidationError(title="Invalid primary key: must be a non-empty array")

    pk_parts: list[JSONObject] = [
        {"name": str(part.get("name", "")), "value": str(part.get("value", ""))}
        for part in raw_pk
        if isinstance(part, dict)
    ]

    return await svc.get_record_detail(pk_parts, gs.site_id)


@router.get("/{gene_set_id}/results/distributions/{attribute_name}")
async def get_gene_set_distribution(
    gene_set_id: str,
    attribute_name: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get distribution data for an attribute using the byValue column reporter."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)
    return await svc.get_distribution(attribute_name)


# ---------------------------------------------------------------------------
# WDK step analysis endpoints
# ---------------------------------------------------------------------------


@router.get("/{gene_set_id}/analyses/types")
async def get_gene_set_analysis_types(
    gene_set_id: str,
    user_id: CurrentUser,
) -> JSONObject:
    """List available WDK step analysis types for a gene set."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)
    return await svc.list_analysis_types()


@router.post("/{gene_set_id}/analyses/run")
async def run_gene_set_analysis(
    gene_set_id: str,
    request: RunGeneSetAnalysisRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Run a WDK step analysis on a gene set."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    svc = _require_svc(gs)
    return await svc.run_analysis(request.analysis_name, dict(request.parameters))


@router.get("/{gene_set_id}/strategy")
async def get_gene_set_strategy(
    gene_set_id: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get the WDK strategy tree for a gene set."""
    gs = await _get_gene_set_or_404(user_id, gene_set_id)
    if not gs.wdk_strategy_id:
        raise NotFoundError(
            title="No WDK strategy",
            detail="This gene set has no associated WDK strategy.",
        )
    svc = _require_svc(gs)
    return await svc.get_strategy(gs.wdk_strategy_id)
