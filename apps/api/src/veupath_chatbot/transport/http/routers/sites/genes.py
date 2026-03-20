"""Gene search and resolve endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from veupath_chatbot.services.gene_lookup import lookup_genes_by_text, resolve_gene_ids
from veupath_chatbot.services.wdk import query_site_search

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
    data = await query_site_search(
        siteId,
        search_text="*",
        document_type="gene",
        limit=1,
    )
    data_dict = data if isinstance(data, dict) else {}
    org_counts = data_dict.get("organismCounts")
    orgs = sorted(org_counts.keys()) if isinstance(org_counts, dict) else []
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
    data = await lookup_genes_by_text(
        siteId, q, organism=organism or None, limit=limit, offset=offset
    )
    data_dict = data if isinstance(data, dict) else {}
    raw_results = data_dict.get("records")
    if not isinstance(raw_results, list):
        raw_results = []
    total = data_dict.get("totalCount", 0)
    suggested_raw = data_dict.get("suggestedOrganisms")
    suggested_list = suggested_raw if isinstance(suggested_raw, list) else []
    suggested: list[str] = [str(s) for s in suggested_list]

    results: list[GeneSearchResultResponse] = []
    for r in raw_results:
        if not isinstance(r, dict):
            continue
        raw_matched = r.get("matchedFields")
        matched_list = raw_matched if isinstance(raw_matched, list) else []
        matched_str_list: list[str] = [x for x in matched_list if isinstance(x, str)]

        results.append(
            GeneSearchResultResponse(
                geneId=str(r.get("geneId", "")),
                displayName=str(r.get("displayName", "")),
                organism=str(r.get("organism", "")),
                product=str(r.get("product", "")),
                geneName=str(r.get("geneName", "")),
                geneType=str(r.get("geneType", "")),
                location=str(r.get("location", "")),
                matchedFields=matched_str_list,
            )
        )

    return GeneSearchResponse(
        results=results,
        totalCount=total if isinstance(total, int) else len(results),
        suggestedOrganisms=suggested,
    )


@router.post("/{siteId}/genes/resolve", response_model=GeneResolveResponse)
async def resolve_genes(
    siteId: str,
    payload: GeneResolveRequest,
) -> GeneResolveResponse:
    """Resolve gene IDs to full records via WDK standard reporter."""
    data = await resolve_gene_ids(siteId, payload.geneIds)

    raw_records = data.get("records") if isinstance(data, dict) else []
    if not isinstance(raw_records, list):
        raw_records = []

    resolved_ids: set[str] = set()
    resolved: list[ResolvedGeneResponse] = []
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue
        gene_id = str(rec.get("geneId", "")).strip()
        if not gene_id:
            continue
        resolved_ids.add(gene_id)
        resolved.append(
            ResolvedGeneResponse(
                geneId=gene_id,
                displayName=str(rec.get("product", gene_id)),
                organism=str(rec.get("organism", "")),
                product=str(rec.get("product", "")),
                geneName=str(rec.get("geneName", "")),
                geneType=str(rec.get("geneType", "")),
                location=str(rec.get("location", "")),
            )
        )

    unresolved = [gid for gid in payload.geneIds if gid not in resolved_ids]

    return GeneResolveResponse(resolved=resolved, unresolved=unresolved)
