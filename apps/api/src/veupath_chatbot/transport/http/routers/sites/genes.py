"""Gene search and resolve endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
)
from veupath_chatbot.services.gene_lookup import lookup_genes_by_text, resolve_gene_ids

router = APIRouter(prefix="/api/v1/sites", tags=["sites"])


class GeneSearchResultResponse(BaseModel):
    """A single gene result from site-search."""

    geneId: str
    displayName: str = ""
    organism: str = ""
    product: str = ""
    geneName: str = ""
    geneType: str = ""
    location: str = ""
    matchedFields: list[str] = []


class GeneSearchResponse(BaseModel):
    """Paginated gene search response."""

    results: list[GeneSearchResultResponse]
    totalCount: int
    suggestedOrganisms: list[str] = []


class GeneResolveRequest(BaseModel):
    """Request body for gene ID resolution."""

    geneIds: list[str]


class ResolvedGeneResponse(BaseModel):
    """A resolved gene record."""

    geneId: str
    displayName: str = ""
    organism: str = ""
    product: str = ""
    geneName: str = ""
    geneType: str = ""
    location: str = ""


class GeneResolveResponse(BaseModel):
    """Gene ID resolution response."""

    resolved: list[ResolvedGeneResponse]
    unresolved: list[str]


class OrganismsResponse(BaseModel):
    """Available organisms for a site."""

    organisms: list[str]


@router.get("/{siteId}/organisms", response_model=OrganismsResponse)
async def list_organisms(siteId: str) -> OrganismsResponse:
    """Return all available organism names for a site via site-search."""
    site_router = get_site_router()
    client = site_router.get_site_search_client(siteId)
    response = await client.search(
        search_text="*",
        document_type_filter=DocumentTypeFilter(document_type="gene"),
        limit=1,
    )
    orgs = sorted(response.organism_counts.keys())
    return OrganismsResponse(organisms=orgs)


@router.get("/{siteId}/genes/search", response_model=GeneSearchResponse)
async def search_genes(
    siteId: str,
    q: str = "",
    organism: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> GeneSearchResponse:
    """Search genes by text using multi-strategy gene lookup."""
    result = await lookup_genes_by_text(
        siteId, q, organism=organism or None, limit=limit, offset=offset
    )
    return GeneSearchResponse(
        results=[
            GeneSearchResultResponse(
                geneId=r.gene_id,
                displayName=r.display_name or r.product or r.gene_id,
                organism=r.organism,
                product=r.product,
                geneName=r.gene_name,
                geneType=r.gene_type,
                location=r.location,
                matchedFields=r.matched_fields or [],
            )
            for r in result.records
        ],
        totalCount=result.total_count,
        suggestedOrganisms=result.suggested_organisms or [],
    )


@router.post("/{siteId}/genes/resolve", response_model=GeneResolveResponse)
async def resolve_genes(
    siteId: str,
    payload: GeneResolveRequest,
) -> GeneResolveResponse:
    """Resolve gene IDs to full records via WDK standard reporter."""
    result = await resolve_gene_ids(siteId, payload.geneIds)
    resolved_ids: set[str] = set()
    resolved: list[ResolvedGeneResponse] = []
    for rec in result.records:
        if not rec.gene_id:
            continue
        resolved_ids.add(rec.gene_id)
        resolved.append(
            ResolvedGeneResponse(
                geneId=rec.gene_id,
                displayName=rec.product or rec.gene_id,
                organism=rec.organism,
                product=rec.product,
                geneName=rec.gene_name,
                geneType=rec.gene_type,
                location=rec.location,
            )
        )
    unresolved = [gid for gid in payload.geneIds if gid not in resolved_ids]
    return GeneResolveResponse(resolved=resolved, unresolved=unresolved)
