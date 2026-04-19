"""Gene set management endpoints.

Thin transport layer: parse HTTP request, call service, return HTTP response.
All business logic lives in ``services.gene_sets.operations``.
"""

import re
from dataclasses import dataclass
from typing import Annotated, Literal, cast, get_args

from fastapi import APIRouter, Depends, Query, Request
from pydantic import JsonValue

from pathfinder.platform.errors import (
    InternalError,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.security import limiter
from pathfinder.platform.types import JSONObject
from pathfinder.services.export import get_export_service
from pathfinder.services.gene_sets.confidence import (
    GeneClassification,
    compute_gene_confidence,
)
from pathfinder.services.gene_sets.ensemble import (
    EnsembleScore,
    compute_ensemble_scores,
)
from pathfinder.services.gene_sets.operations import GeneSetService
from pathfinder.services.gene_sets.reverse_search import (
    GeneSetCandidate,
    rank_gene_sets_by_recall,
)
from pathfinder.services.gene_sets.store import get_gene_set_store
from pathfinder.services.gene_sets.types import GeneSet
from pathfinder.services.gene_sets.wdk_helpers import (
    GeneSetWdkContext,
    SetOperation,
)
from pathfinder.services.wdk import WDKSortDirection
from pathfinder.transport.http.deps import CurrentUser
from pathfinder.transport.http.schemas.gene_sets import (
    CreateGeneSetRequest,
    EnsembleScoringRequest,
    GeneConfidenceRequest,
    GeneConfidenceScoreResponse,
    GeneSetEnrichRequest,
    GeneSetResponse,
    ReverseSearchRequest,
    ReverseSearchResultItem,
    SetOperationRequest,
)
from pathfinder.transport.http.schemas.steps import RecordDetailRequest

router = APIRouter(prefix="/api/v1/gene-sets", tags=["gene-sets"])
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Query parameter groups
# ---------------------------------------------------------------------------

@dataclass
class RecordQueryParams:
    """Grouped query parameters for record listing endpoints."""

    offset: int = Query(0, ge=0)
    limit: int = Query(50, ge=1, le=500)
    sort: str | None = None
    sort_dir: Annotated[WDKSortDirection, Query(alias="dir")] = "ASC"
    attributes: str | None = None
    filter_attribute: str | None = Query(None, alias="filterAttribute")
    filter_value: str | None = Query(None, alias="filterValue")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc() -> GeneSetService:
    return GeneSetService(get_gene_set_store())

def _to_response(gs: GeneSet) -> GeneSetResponse:
    valid_ops = get_args(SetOperation)
    operation: SetOperation | None = (
        cast("SetOperation", gs.operation) if gs.operation in valid_ops else None
    )
    return GeneSetResponse(
        id=gs.id,
        site_id=gs.site_id,
        name=gs.name,
        gene_ids=gs.gene_ids,
        source=gs.source,
        gene_count=len(gs.gene_ids),
        wdk_strategy_id=gs.wdk_strategy_id,
        wdk_step_id=gs.wdk_step_id,
        search_name=gs.search_name,
        record_type=gs.record_type,
        parameters=gs.parameters,
        parent_set_ids=gs.parent_set_ids,
        operation=operation,
        created_at=gs.created_at.isoformat(),
        step_count=gs.step_count,
    )

def _not_found(exc: KeyError) -> NotFoundError:
    return NotFoundError(title=str(exc))

def _no_strategy(exc: ValueError) -> NotFoundError:
    return NotFoundError(title="No WDK strategy", detail=str(exc))

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
    gs = await _svc().create(
        user_id=user_id,
        name=body.name,
        site_id=body.site_id,
        gene_ids=body.gene_ids,
        source=body.source,
        wdk=GeneSetWdkContext(
            wdk_strategy_id=body.wdk_strategy_id,
            wdk_step_id=body.wdk_step_id,
            search_name=body.search_name,
            record_type=body.record_type,
            parameters=body.parameters,
        ),
    )
    return _to_response(gs)

@router.get("")
async def list_gene_sets(
    user_id: CurrentUser,
    site_id: str | None = Query(None, alias="siteId"),
) -> list[GeneSetResponse]:
    """List all gene sets for the current user, optionally filtered by site."""
    sets = await _svc().list_for_user(user_id, site_id=site_id)
    return [_to_response(gs) for gs in sets]

@router.get("/{gene_set_id}")
async def get_gene_set(
    gene_set_id: str,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Get a gene set by ID."""
    try:
        gs = await _svc().get_for_user(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    return _to_response(gs)

@router.delete("/{gene_set_id}")
async def delete_gene_set(
    gene_set_id: str,
    user_id: CurrentUser,
) -> dict[str, bool]:
    """Delete a gene set."""
    try:
        await _svc().delete(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    return {"ok": True}

class GeneSetExportResponse(CamelModel):
    export_id: str
    filename: str
    content_type: str
    url: str

class GeneSetImportRequest(CamelModel):
    name: str
    site_id: str
    raw_text: str

_ID_SPLIT_RE = re.compile(r"[\s,;\t]+")

def _parse_gene_id_blob(raw: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tok in _ID_SPLIT_RE.split(raw):
        cleaned = tok.strip().strip('"').strip("'")
        if cleaned == "" or cleaned.lower() == "gene_id":
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out

@router.post("/{gene_set_id}/export")
@limiter.limit("30/minute")
async def export_gene_set_endpoint(
    request: Request,
    gene_set_id: str,
    user_id: CurrentUser,
    fmt: str = Query("csv", alias="format"),
) -> GeneSetExportResponse:
    """Export a gene set as CSV or TXT. Returns a short-lived download URL."""
    del request
    if fmt not in ("csv", "txt"):
        msg = "format must be 'csv' or 'txt'"
        raise ValidationError(title=msg)
    try:
        gs = await _svc().get_for_user(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    svc = get_export_service()
    result = await svc.export_gene_set(gs, cast("Literal['csv', 'txt']", fmt))
    return GeneSetExportResponse(
        export_id=result.export_id,
        filename=result.filename,
        content_type=result.content_type,
        url=result.url,
    )

@router.post("/import", status_code=201)
@limiter.limit("30/minute")
async def import_gene_set(
    request: Request,
    body: GeneSetImportRequest,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Create a gene set from a raw pasted text blob (CSV/TSV/newline list)."""
    del request
    ids = _parse_gene_id_blob(body.raw_text)
    if len(ids) == 0:
        msg = "No gene IDs parsed from input"
        raise ValidationError(title=msg)
    gs = await _svc().create(
        user_id=user_id,
        name=body.name,
        site_id=body.site_id,
        gene_ids=ids,
        source="paste",
    )
    return _to_response(gs)

@router.post("/operations")
async def set_operations(
    request: SetOperationRequest,
    user_id: CurrentUser,
) -> GeneSetResponse:
    """Perform set operations (intersect, union, minus) between two gene sets."""
    try:
        gs = await _svc().perform_set_operation(
            user_id=user_id,
            set_a_id=request.set_a_id,
            set_b_id=request.set_b_id,
            operation=request.operation,
            name=request.name,
        )
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise ValidationError(title="Invalid operation", detail=str(exc)) from exc
    return _to_response(gs)

# ---------------------------------------------------------------------------
# Reverse search
# ---------------------------------------------------------------------------

@router.post("/reverse-search")
async def reverse_search(
    body: ReverseSearchRequest,
    user_id: CurrentUser,
) -> list[ReverseSearchResultItem]:
    """Rank the user's gene sets by how well they recover the given positive genes."""
    sets = await _svc().list_for_user(user_id, site_id=body.site_id)
    candidates = [
        GeneSetCandidate(
            id=gs.id,
            name=gs.name,
            gene_ids=gs.gene_ids,
            search_name=gs.search_name,
        )
        for gs in sets
    ]
    ranked = rank_gene_sets_by_recall(
        candidates,
        body.positive_gene_ids,
        body.negative_gene_ids,
    )
    return [
        ReverseSearchResultItem(
            gene_set_id=r.gene_set_id,
            name=r.name,
            search_name=r.search_name,
            recall=r.recall,
            precision=r.precision,
            f1=r.f1,
            estimated_size=r.estimated_size,
            overlap_count=r.overlap_count,
        )
        for r in ranked
    ]

# ---------------------------------------------------------------------------
# Ensemble scoring
# ---------------------------------------------------------------------------

@router.post("/ensemble")
async def ensemble_scoring(
    body: EnsembleScoringRequest,
    user_id: CurrentUser,
) -> list[EnsembleScore]:
    """Score genes by frequency across multiple gene sets."""
    service = _svc()
    gene_sets: list[list[str]] = []
    for gs_id in body.gene_set_ids:
        try:
            gs = await service.get_for_user(user_id, gs_id)
        except KeyError as exc:
            raise _not_found(exc) from exc
        gene_sets.append(gs.gene_ids)

    return compute_ensemble_scores(gene_sets, body.positive_controls)

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
    try:
        results = await _svc().run_enrichment(
            user_id, gene_set_id, request.enrichment_types
        )
    except KeyError as exc:
        raise _not_found(exc) from exc
    except RuntimeError as exc:
        raise InternalError(
            title="Enrichment analysis failed", detail=str(exc)
        ) from exc
    return [r.model_dump(by_alias=True) for r in results]

# ---------------------------------------------------------------------------
# Result browsing endpoints (attributes, records, distributions)
# ---------------------------------------------------------------------------

@router.get("/{gene_set_id}/results/attributes")
async def get_gene_set_attributes(
    gene_set_id: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get available attributes for a gene set's record type."""
    try:
        svc = await _svc().get_step_results_service(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _no_strategy(exc) from exc
    return await svc.get_attributes()

@router.get("/{gene_set_id}/results/records")
async def get_gene_set_records(
    gene_set_id: str,
    user_id: CurrentUser,
    params: Annotated[RecordQueryParams, Depends()],
) -> JSONObject:
    """Get paginated result records for a gene set."""
    try:
        svc = await _svc().get_step_results_service(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _no_strategy(exc) from exc

    attr_list: list[str] | None = None
    if params.attributes:
        attr_list = [a.strip() for a in params.attributes.split(",") if a.strip()]

    # When filtering, fetch all records for the step and filter server-side.
    if params.filter_attribute and params.filter_value is not None:
        answer = await svc.get_records(
            offset=0,
            limit=10_000,
            sort=params.sort,
            direction=params.sort_dir,
            attributes=attr_list,
        )
        filtered: list[JsonValue] = []
        for rec in answer.records:
            val = rec.attributes.get(params.filter_attribute)
            if val == params.filter_value:
                filtered.append(rec.model_dump(by_alias=True))
        page = filtered[params.offset : params.offset + params.limit]
        return {
            "records": cast("JsonValue", page),
            "meta": {
                "totalCount": len(filtered),
                "displayTotalCount": len(filtered),
                "responseCount": len(page),
                "pagination": {"offset": params.offset, "numRecords": params.limit},
                "attributes": cast("JsonValue", attr_list or []),
                "tables": cast("JsonValue", []),
            },
        }

    answer = await svc.get_records(
        offset=params.offset,
        limit=params.limit,
        sort=params.sort,
        direction=params.sort_dir,
        attributes=attr_list,
    )
    meta = answer.meta.model_dump(by_alias=True)
    meta["pagination"] = {"offset": params.offset, "numRecords": params.limit}
    return {
        "records": [r.model_dump(by_alias=True) for r in answer.records],
        "meta": meta,
    }

@router.get("/{gene_set_id}/results/distributions/{attribute_name}")
async def get_gene_set_distribution(
    gene_set_id: str,
    attribute_name: str,
    user_id: CurrentUser,
) -> JSONObject:
    """Get distribution data for an attribute using the byValue column reporter."""
    try:
        svc = await _svc().get_step_results_service(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _no_strategy(exc) from exc
    dist = await svc.get_distribution(attribute_name)
    return dist.model_dump(by_alias=True)

@router.post("/{gene_set_id}/results/record")
async def get_gene_set_record_detail(
    gene_set_id: str,
    body: RecordDetailRequest,
    user_id: CurrentUser,
) -> JSONObject:
    """Get a single record's full details by primary key."""
    service = _svc()
    try:
        gs = await service.get_for_user(user_id, gene_set_id)
        svc = await service.get_step_results_service(user_id, gene_set_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _no_strategy(exc) from exc

    pk_parts: list[dict[str, str]] = [
        {"name": part.name, "value": part.value} for part in body.primary_key
    ]
    return await svc.get_record_detail(pk_parts, gs.site_id)

# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

@router.post("/confidence")
async def gene_confidence(
    body: GeneConfidenceRequest,
) -> list[GeneConfidenceScoreResponse]:
    """Compute per-gene composite confidence scores from classification data."""
    scores = compute_gene_confidence(
        GeneClassification(
            tp_ids=body.tp_ids,
            fp_ids=body.fp_ids,
            fn_ids=body.fn_ids,
            tn_ids=body.tn_ids,
        ),
        ensemble_scores=body.ensemble_scores,
        enrichment_gene_counts=body.enrichment_gene_counts,
        max_enrichment_terms=body.max_enrichment_terms,
    )
    return [
        GeneConfidenceScoreResponse(
            gene_id=s.gene_id,
            composite_score=s.composite_score,
            classification_score=s.classification_score,
            ensemble_score=s.ensemble_score,
            enrichment_score=s.enrichment_score,
        )
        for s in scores
    ]
