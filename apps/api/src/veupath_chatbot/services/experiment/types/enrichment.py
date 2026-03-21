"""Enrichment analysis types for the Experiment Lab."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat
from veupath_chatbot.services.experiment.types.core import EnrichmentAnalysisType


class EnrichmentTerm(CamelModel):
    """Single enriched term from WDK analysis."""

    model_config = ConfigDict(frozen=True)

    term_id: str
    term_name: str
    gene_count: int
    background_count: int
    fold_enrichment: RoundedFloat
    odds_ratio: RoundedFloat
    p_value: float
    fdr: float
    bonferroni: float
    genes: list[str] = Field(default_factory=list)


class EnrichmentResult(CamelModel):
    """Results for a single enrichment analysis type."""

    model_config = ConfigDict(frozen=True)

    analysis_type: EnrichmentAnalysisType
    terms: list[EnrichmentTerm]
    total_genes_analyzed: int = 0
    background_size: int = 0
    error: str | None = None
