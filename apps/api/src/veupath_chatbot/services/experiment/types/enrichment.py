"""Enrichment analysis types for the Experiment Lab."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import (
    CamelModel,
    SafeFiniteFloat,
    SafeFiniteRoundedFloat,
)
from veupath_chatbot.services.experiment.types.core import EnrichmentAnalysisType


class EnrichmentTerm(CamelModel):
    """Single enriched term from WDK analysis.

    WDK returns numeric fields as JSON strings (``"3.48"``, ``"3.40e-13"``,
    ``"Infinity"``).  Pydantic lax mode coerces str→int/float; SafeFiniteFloat
    clamps inf/nan to 0.0.
    """

    model_config = ConfigDict(frozen=True)

    term_id: str
    term_name: str
    gene_count: int
    background_count: int
    fold_enrichment: SafeFiniteRoundedFloat
    odds_ratio: SafeFiniteRoundedFloat
    p_value: SafeFiniteFloat
    fdr: SafeFiniteFloat
    bonferroni: SafeFiniteFloat
    genes: list[str] = Field(default_factory=list)


class EnrichmentResult(CamelModel):
    """Results for a single enrichment analysis type."""

    model_config = ConfigDict(frozen=True)

    analysis_type: EnrichmentAnalysisType
    terms: list[EnrichmentTerm]
    total_genes_analyzed: int = 0
    background_size: int = 0
    error: str | None = None
