"""Enrichment analysis dataclasses for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.services.experiment.types.core import EnrichmentAnalysisType


@dataclass(frozen=True, slots=True)
class EnrichmentTerm:
    """Single enriched term from WDK analysis."""

    term_id: str
    term_name: str
    gene_count: int
    background_count: int
    fold_enrichment: float
    odds_ratio: float
    p_value: float
    fdr: float
    bonferroni: float
    genes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """Results for a single enrichment analysis type."""

    analysis_type: EnrichmentAnalysisType
    terms: list[EnrichmentTerm]
    total_genes_analyzed: int
    background_size: int
