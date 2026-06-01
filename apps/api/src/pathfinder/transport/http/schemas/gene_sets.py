"""HTTP request/response schemas for gene sets."""

from pydantic import Field

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.enrichment.types import EnrichmentAnalysisType
from pathfinder.services.gene_sets.types import GeneSetSource
from pathfinder.services.gene_sets.wdk_helpers import SetOperation


class CreateGeneSetRequest(CamelModel):
    """Create a gene set from IDs, strategy, or upload."""

    name: str = Field(min_length=1, max_length=200)
    site_id: str
    gene_ids: list[str]
    source: GeneSetSource = "paste"
    wdk_strategy_id: int | None = Field(None)
    wdk_step_id: int | None = Field(None)
    search_name: str | None = Field(None)
    record_type: str | None = Field(None)
    parameters: dict[str, ParamValue] | None = None


class GeneSetResponse(CamelModel):
    """Gene set response DTO."""

    id: str
    name: str
    site_id: str
    gene_ids: list[str]
    source: GeneSetSource
    gene_count: int
    wdk_strategy_id: int | None = Field(None)
    wdk_step_id: int | None = Field(None)
    search_name: str | None = Field(None)
    record_type: str | None = Field(None)
    parameters: dict[str, ParamValue] | None = None
    parent_set_ids: list[str] = Field(default_factory=list)
    operation: SetOperation | None = None
    created_at: str
    step_count: int = Field(1)


class SetOperationRequest(CamelModel):
    """Perform set operations between two gene sets."""

    set_a_id: str
    set_b_id: str
    operation: SetOperation
    name: str = Field(min_length=1, max_length=200)


class GeneSetEnrichRequest(CamelModel):
    """Run enrichment on a gene set."""

    enrichment_types: list[EnrichmentAnalysisType]


class EnsembleScoringRequest(CamelModel):
    """Compute ensemble frequency scores across multiple gene sets."""

    gene_set_ids: list[str] = Field(min_length=2)
    positive_controls: list[str] | None = Field(None)


class ReverseSearchRequest(CamelModel):
    """Rank user's gene sets by recall of given positive genes."""

    positive_gene_ids: list[str] = Field(min_length=1)
    negative_gene_ids: list[str] | None = Field(None)
    site_id: str


class ReverseSearchResultItem(CamelModel):
    """A single ranked gene set in reverse search results."""

    gene_set_id: str
    name: str
    search_name: str | None = Field(None)
    recall: float
    precision: float
    f1: float
    estimated_size: int
    overlap_count: int


class RunGeneSetAnalysisRequest(CamelModel):
    """Run a WDK step analysis on a gene set."""

    analysis_name: str = Field(min_length=1)
    parameters: JSONObject = Field(default_factory=dict)


class GeneConfidenceRequest(CamelModel):
    """Compute per-gene confidence scores from classification data."""

    tp_ids: list[str]
    fp_ids: list[str]
    fn_ids: list[str]
    tn_ids: list[str]
    ensemble_scores: dict[str, float] | None = Field(None)
    enrichment_gene_counts: dict[str, int] | None = Field(None)
    max_enrichment_terms: int = Field(1, ge=1)


class GeneConfidenceScoreResponse(CamelModel):
    """Single gene confidence score in the response."""

    gene_id: str
    composite_score: float
    classification_score: float
    ensemble_score: float
    enrichment_score: float
