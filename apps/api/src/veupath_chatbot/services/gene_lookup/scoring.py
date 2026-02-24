"""Gene-specific relevance scoring for text search results."""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.search_rerank import (
    score_field_quality,
    score_text_match,
)

from .organism import score_organism_match

_W_GENE_ID = 100.0
_W_GENE_NAME = 40.0
_W_ORGANISM = 60.0
_W_PRODUCT = 15.0
_W_FIELD_QUALITY = 20.0


def score_gene_relevance(query: str, result: JSONObject) -> float:
    """Score a gene result's relevance to *query*.

    Higher is better.  The score is an additive combination of how well
    the query matches the gene ID, gene name, organism, and product,
    plus a bonus/penalty based on which site-search fields matched.
    """
    gene_id = str(result.get("geneId", ""))
    gene_name = str(result.get("geneName", ""))
    organism = str(result.get("organism", ""))
    product = str(result.get("product", ""))
    matched_fields = result.get("matchedFields")
    mf_list = matched_fields if isinstance(matched_fields, list) else []

    score = 0.0
    score += _W_GENE_ID * score_text_match(query, gene_id)
    score += _W_GENE_NAME * score_text_match(query, gene_name)
    score += _W_ORGANISM * score_organism_match(query, organism)
    score += _W_PRODUCT * score_text_match(query, product)
    score += _W_FIELD_QUALITY * score_field_quality(mf_list)
    return score
